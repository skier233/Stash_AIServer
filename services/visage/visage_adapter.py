# =============================================================================
# StashAI Server - Visage Service Adapter
# =============================================================================

import aiohttp
import base64
import json
import logging
from typing import Dict, List, Optional, Any, Union
from datetime import datetime
import asyncio

from schemas.api_schema import (
    FacialRecognitionRequest, FacialRecognitionResponse, FaceComparisonRequest, 
    FaceComparisonResponse, PerformerInfo, FaceInfo, StashEntity, ImageData,
    SceneIdentificationRequest, GalleryIdentificationRequest, BaseResponse
)

logger = logging.getLogger(__name__)

# =============================================================================
# Visage API Client
# =============================================================================

class VisageAdapter:
    """
    Adapter for interfacing with the Visage facial recognition service
    
    Based on Visage app.py capabilities:
    - Image search (single performer): /api/predict_0
    - Image search (multiple performers): /api/predict_1  
    - Find closest faces: /api/predict_4
    - Face comparison: /api/compare_faces
    - Batch comparisons: /api/batch_compare_one_to_many, /api/batch_compare_many_to_many
    - Person names: /api/person_names
    - Sprite face detection: faces_in_sprite
    """
    
    def __init__(self, base_url: str = "http://visage:8000", timeout: int = 300, max_concurrent_requests: int = 3, request_delay: float = 1.0):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.max_concurrent_requests = max_concurrent_requests
        self.request_delay = request_delay  # Minimum delay between requests
        self.session: Optional[aiohttp.ClientSession] = None
        self._request_semaphore: Optional[asyncio.Semaphore] = None
        self._last_request_time: Optional[datetime] = None
        
    async def __aenter__(self):
        """Async context manager entry"""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=self.timeout)
        )
        self._request_semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        if self.session:
            await self.session.close()
            
    async def _make_request(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Make HTTP request to Visage service with rate limiting and retry logic"""
        if not self.session or not self._request_semaphore:
            raise RuntimeError("VisageAdapter must be used as async context manager")
            
        url = f"{self.base_url}{endpoint}"
        
        # Rate limiting: ensure minimum delay between requests
        if self._last_request_time:
            time_since_last = (datetime.utcnow() - self._last_request_time).total_seconds()
            if time_since_last < self.request_delay:
                await asyncio.sleep(self.request_delay - time_since_last)
        
        # Concurrency limiting
        async with self._request_semaphore:
            self._last_request_time = datetime.utcnow()
            
            # Retry logic for transient failures
            max_retries = 3
            base_delay = 1.0
            
            for attempt in range(max_retries):
                try:
                    async with self.session.post(url, json=data) as response:
                        if response.status == 200:
                            result = await response.json()
                            return result
                        elif response.status == 503 and attempt < max_retries - 1:
                            # Service temporarily unavailable, wait and retry
                            retry_delay = base_delay * (2 ** attempt)  # Exponential backoff
                            logger.warning(f"Visage returned 503, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries})")
                            await asyncio.sleep(retry_delay)
                            continue
                        else:
                            error_text = await response.text()
                            raise Exception(f"Visage API error {response.status}: {error_text}")
                            
                except aiohttp.ClientError as e:
                    if attempt < max_retries - 1:
                        retry_delay = base_delay * (2 ** attempt)
                        logger.warning(f"Connection error to Visage, retrying in {retry_delay}s (attempt {attempt + 1}/{max_retries}): {e}")
                        await asyncio.sleep(retry_delay)
                        continue
                    else:
                        raise Exception(f"Failed to connect to Visage service after {max_retries} attempts: {e}")
                except json.JSONDecodeError as e:
                    raise Exception(f"Invalid JSON response from Visage: {e}")
            
            raise Exception(f"Failed to get valid response from Visage after {max_retries} attempts")
            
    async def health_check(self) -> bool:
        """Check if Visage service is healthy"""
        try:
            if not self.session:
                self.session = aiohttp.ClientSession(
                    timeout=aiohttp.ClientTimeout(total=10)
                )
                
            # Try to get person names as health check
            async with self.session.get(f"{self.base_url}/api/person_names") as response:
                return response.status == 200
                
        except Exception as e:
            logger.warning(f"Visage health check failed: {e}")
            return False
            
    # =========================================================================
    # Core Facial Recognition Methods
    # =========================================================================
    
    async def identify_single_performer(
        self, 
        image_data: str, 
        threshold: float = 0.5, 
        max_results: int = 5
    ) -> List[PerformerInfo]:
        """
        Identify a single performer in an image
        Uses Visage /api/predict_0 endpoint
        """
        request_data = {
            "image_data": image_data,
            "threshold": threshold,
            "results": max_results
        }
        
        response = await self._make_request("/api/predict_0", request_data)
        
        # Parse Visage response format
        performers = []
        if "data" in response and response["data"]:
            visage_results = response["data"][0]  # predict_0 returns single result
            if isinstance(visage_results, list):
                for result in visage_results:
                    performer = self._parse_performer_info(result)
                    if performer:
                        performers.append(performer)
                        
        return performers
        
    async def identify_multiple_performers(
        self, 
        image_data: str, 
        threshold: float = 0.5, 
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Identify multiple performers in an image  
        Uses Visage /api/predict_1 endpoint
        Returns list of faces with their performer matches
        """
        request_data = {
            "image_data": image_data,
            "threshold": threshold,
            "results": max_results
        }
        
        response = await self._make_request("/api/predict_1", request_data)
        
        # Parse Visage response format for multiple faces
        faces_with_performers = []
        if "data" in response and response["data"]:
            visage_results = response["data"][0]  # predict_1 returns face array
            if isinstance(visage_results, list):
                for face_result in visage_results:
                    face_data = {
                        "face_image": face_result.get("image"),  # Base64 cropped face
                        "face_confidence": face_result.get("confidence", 0.0),
                        "performers": []
                    }
                    
                    # Parse performers for this face
                    if "performers" in face_result:
                        for performer_data in face_result["performers"]:
                            performer = self._parse_performer_info(performer_data)
                            if performer:
                                face_data["performers"].append(performer)
                                
                    faces_with_performers.append(face_data)
                    
        return faces_with_performers
        
    async def find_similar_faces(
        self,
        person_name: str,
        num_results: int = 10,
        tolerance: float = 0.3,
        arc_weight: float = 0.5,
        facenet_weight: float = 0.5
    ) -> List[PerformerInfo]:
        """
        Find faces similar to a specific person
        Uses Visage /api/predict_4 endpoint
        """
        request_data = {
            "data": [person_name, num_results, tolerance, arc_weight, facenet_weight]
        }
        
        response = await self._make_request("/api/predict_4", request_data)
        
        performers = []
        if "data" in response and response["data"]:
            visage_results = response["data"][0]
            if isinstance(visage_results, list):
                # Skip metadata if present
                results_to_process = visage_results
                if visage_results and "search_metadata" in str(visage_results[0]):
                    results_to_process = visage_results[1:]  # Skip metadata entry
                    
                for result in results_to_process:
                    if "error" not in result:
                        performer = self._parse_performer_info(result)
                        if performer:
                            performers.append(performer)
                            
        return performers
        
    async def compare_two_faces(
        self, 
        person1: str, 
        person2: str
    ) -> Dict[str, Any]:
        """
        Compare faces between two performers
        Uses Visage /api/compare_faces endpoint
        """
        request_data = {
            "person1": person1,
            "person2": person2
        }
        
        response = await self._make_request("/api/compare_faces", request_data)
        
        if "data" in response:
            return response["data"]
        return {}
        
    async def batch_compare_one_to_many(
        self,
        target_person: str,
        comparison_people: List[str],
        tolerance: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Compare one person against multiple people
        Uses Visage /api/batch_compare_one_to_many endpoint
        """
        request_data = {
            "target_person": target_person,
            "comparison_people": ",".join(comparison_people),
            "tolerance": tolerance
        }
        
        response = await self._make_request("/api/batch_compare_one_to_many", request_data)
        
        if "data" in response:
            return response["data"]
        return []
        
    async def batch_compare_many_to_many(
        self,
        group1_people: List[str],
        group2_people: List[str], 
        tolerance: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        Compare multiple people from group 1 against multiple people from group 2
        Uses Visage /api/batch_compare_many_to_many endpoint
        """
        request_data = {
            "group1_people": ",".join(group1_people),
            "group2_people": ",".join(group2_people),
            "tolerance": tolerance  
        }
        
        response = await self._make_request("/api/batch_compare_many_to_many", request_data)
        
        if "data" in response:
            return response["data"]
        return []
        
    async def get_all_person_names(self) -> List[str]:
        """
        Get all available person names from Visage
        Uses Visage /api/person_names endpoint
        """
        if not self.session:
            raise RuntimeError("VisageAdapter must be used as async context manager")
            
        try:
            async with self.session.get(f"{self.base_url}/api/person_names") as response:
                if response.status == 200:
                    result = await response.json()
                    if "data" in result and isinstance(result["data"], list):
                        return result["data"]
        except Exception as e:
            logger.error(f"Failed to get person names: {e}")
            
        return []
        
    # =========================================================================
    # Sprite and Video Analysis Methods  
    # =========================================================================
    
    async def find_faces_in_sprite(
        self,
        sprite_image: str,  # Base64 image
        vtt_data: str       # Base64 VTT file
    ) -> List[Dict[str, Any]]:
        """
        Find faces in video sprite/preview
        Uses Visage faces_in_sprite functionality
        """
        # Note: This would need to be implemented as a POST endpoint in Visage
        # Currently it's only available via Gradio interface
        logger.warning("Sprite face detection not yet implemented via API")
        return []
        
    # =========================================================================
    # High-level StashAI Integration Methods
    # =========================================================================
    
    async def process_scene_identification(
        self, 
        request: SceneIdentificationRequest
    ) -> FacialRecognitionResponse:
        """
        Process scene identification request using Visage capabilities
        """
        start_time = datetime.utcnow()
        
        try:
            # Extract image data from request
            if not request.image_data:
                return FacialRecognitionResponse(
                    success=False,
                    error="No image data provided for scene identification",
                    request_id=request.request_id,
                    service_name="visage"
                )
                
            # Use multiple performer identification for scenes
            faces_with_performers = await self.identify_multiple_performers(
                image_data=request.image_data.data,
                threshold=request.threshold,
                max_results=request.max_results
            )
            
            # Aggregate all unique performers found
            all_performers = []
            all_faces = []
            performer_ids_seen = set()
            
            for face_data in faces_with_performers:
                # Add face info
                face_info = FaceInfo(
                    bbox=[0, 0, 0, 0],  # Would need actual coordinates from Visage
                    confidence=face_data.get("face_confidence", 0.0)
                )
                all_faces.append(face_info)
                
                # Add unique performers
                for performer in face_data.get("performers", []):
                    if performer.id not in performer_ids_seen:
                        all_performers.append(performer)
                        performer_ids_seen.add(performer.id)
                        
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return FacialRecognitionResponse(
                success=True,
                message=f"Identified {len(all_performers)} performers in scene",
                request_id=request.request_id,
                processing_time=processing_time,
                service_name="visage",
                entity=request.entity,
                performers=all_performers,
                faces=all_faces,
                ai_model_info={
                    "models_used": ["arcface", "facenet"],
                    "ensemble_method": "weighted_voting",
                    "threshold": request.threshold
                }
            )
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Scene identification failed: {e}")
            
            return FacialRecognitionResponse(
                success=False,
                error=f"Scene identification failed: {str(e)}",
                request_id=request.request_id,
                processing_time=processing_time,
                service_name="visage"
            )
            
    async def process_gallery_identification(
        self, 
        request: GalleryIdentificationRequest
    ) -> FacialRecognitionResponse:
        """
        Process gallery identification request
        """
        start_time = datetime.utcnow()
        
        try:
            # For now, treat as single image identification
            # TODO: Implement batch processing for multiple gallery images
            if not request.image_data:
                return FacialRecognitionResponse(
                    success=False,
                    error="No image data provided for gallery identification",
                    request_id=request.request_id,
                    service_name="visage"
                )
                
            performers = await self.identify_single_performer(
                image_data=request.image_data.data,
                threshold=request.threshold,
                max_results=request.max_results
            )
            
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            return FacialRecognitionResponse(
                success=True,
                message=f"Identified {len(performers)} performers in gallery",
                request_id=request.request_id,
                processing_time=processing_time,
                service_name="visage",
                entity=request.entity,
                performers=performers,
                ai_model_info={
                    "models_used": ["arcface", "facenet"],
                    "ensemble_method": "weighted_voting",
                    "threshold": request.threshold
                }
            )
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Gallery identification failed: {e}")
            
            return FacialRecognitionResponse(
                success=False,
                error=f"Gallery identification failed: {str(e)}",
                request_id=request.request_id,
                processing_time=processing_time,
                service_name="visage"
            )
            
    async def process_face_comparison(
        self, 
        request: FaceComparisonRequest
    ) -> FaceComparisonResponse:
        """
        Process face comparison request
        """
        start_time = datetime.utcnow()
        
        try:
            # Get person names to validate IDs
            person_names = await self.get_all_person_names()
            
            # Find person names from IDs (assuming ID maps to name somehow)
            # This would need to be adapted based on how Stash IDs map to Visage names
            person1_name = request.performer1_id  # Placeholder
            person2_name = request.performer2_id  # Placeholder
            
            comparison_result = await self.compare_two_faces(person1_name, person2_name)
            
            if "error" in comparison_result:
                return FaceComparisonResponse(
                    success=False,
                    error=comparison_result["error"],
                    request_id=request.request_id,
                    service_name="visage"
                )
                
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Create performer info objects
            performer1 = PerformerInfo(
                id=request.performer1_id,
                name=comparison_result.get("person1", person1_name),
                confidence=1.0
            )
            
            performer2 = PerformerInfo(
                id=request.performer2_id,
                name=comparison_result.get("person2", person2_name),
                confidence=1.0
            )
            
            return FaceComparisonResponse(
                success=True,
                message="Face comparison completed",
                request_id=request.request_id,
                processing_time=processing_time,
                service_name="visage",
                performer1=performer1,
                performer2=performer2,
                similarity=comparison_result.get("similarity", 0.0),
                ai_model_scores={
                    "arcface": comparison_result.get("arc_similarity", 0.0),
                    "facenet": comparison_result.get("facenet_similarity", 0.0),
                    "average": comparison_result.get("similarity", 0.0)
                },
                is_match=comparison_result.get("similarity", 0.0) > 0.6
            )
            
        except Exception as e:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            logger.error(f"Face comparison failed: {e}")
            
            return FaceComparisonResponse(
                success=False,
                error=f"Face comparison failed: {str(e)}",
                request_id=request.request_id,
                processing_time=processing_time,
                service_name="visage"
            )
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _parse_performer_info(self, visage_result: Dict[str, Any]) -> Optional[PerformerInfo]:
        """
        Parse Visage performer result into standardized PerformerInfo
        
        Visage format:
        {
            'id': '12345',
            'name': 'Performer Name',
            'confidence': 85,
            'image': 'base64_image_data',
            'country': 'Country',
            'performer_url': 'https://stashdb.org/performers/12345'
        }
        """
        try:
            return PerformerInfo(
                id=str(visage_result.get("id", "")),
                name=visage_result.get("name", "Unknown"),
                confidence=float(visage_result.get("confidence", 0)) / 100.0,  # Convert % to 0-1
                image_url=visage_result.get("image"),
                stash_url=visage_result.get("performer_url"),
                additional_info={
                    "country": visage_result.get("country"),
                    "hits": visage_result.get("hits"),
                    "distance": visage_result.get("distance"),
                    "face_id": visage_result.get("face_id"),
                    "avg_similarity": visage_result.get("avg_similarity"),
                    "arc_similarity": visage_result.get("arc_similarity"),
                    "facenet_similarity": visage_result.get("facenet_similarity")
                }
            )
        except Exception as e:
            logger.error(f"Failed to parse performer info: {e}")
            return None

# =============================================================================
# Visage Service Factory
# =============================================================================

def create_visage_adapter(base_url: str = "http://visage:8000") -> VisageAdapter:
    """Create a Visage adapter instance"""
    return VisageAdapter(base_url=base_url)