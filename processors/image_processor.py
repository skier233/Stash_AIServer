# =============================================================================
# Image Processor - Implements image identification with database tracking
# =============================================================================

from typing import Dict, Any, Tuple
import logging
import asyncio

from processors.base_processor import BaseAPIProcessor
from database.models import EntityType, AIActionType
from schemas.api_schema import FacialRecognitionRequest, FacialRecognitionResponse

logger = logging.getLogger(__name__)

class ImageProcessor(BaseAPIProcessor):
    """
    Image identification processor that handles single image performer identification
    with full database tracking and job management.
    """
    
    async def process_request(self, request: FacialRecognitionRequest, **kwargs) -> FacialRecognitionResponse:
        """
        Process image identification request.
        
        Args:
            request: FacialRecognitionRequest object
            **kwargs: Additional parameters like cancellation_check, progress_callback
            
        Returns:
            FacialRecognitionResponse object
        """
        # Import here to avoid circular imports
        from main import identify_image_performers
        
        # Extract kwargs
        progress_callback = kwargs.get('progress_callback')
        cancellation_check = kwargs.get('cancellation_check')
        
        # Call the existing working function
        response = await identify_image_performers(request, progress_callback, cancellation_check)
        
        return response
    
    def get_entity_info(self, request: FacialRecognitionRequest) -> Tuple[EntityType, str, str, str]:
        """
        Extract entity information from image identification request.
        
        Args:
            request: FacialRecognitionRequest object
            
        Returns:
            Tuple of (entity_type, entity_id, entity_name, entity_filepath)
        """
        entity_type = EntityType.IMAGE
        entity_id = str(request.entity.id) if request.entity else request.request_id
        entity_name = getattr(request.entity, 'title', None) if request.entity else None
        entity_filepath = getattr(request.entity, 'path', None) if request.entity else None
        
        return entity_type, entity_id, entity_name, entity_filepath
    
    def get_action_type(self) -> AIActionType:
        """
        Get the AI action type for image processing.
        
        Returns:
            AIActionType.IMAGE_IDENTIFICATION
        """
        return AIActionType.IMAGE_IDENTIFICATION
    
    def extract_results(self, response: FacialRecognitionResponse) -> Dict[str, Any]:
        """
        Extract standardized results from image identification response.
        
        Args:
            response: FacialRecognitionResponse object
            
        Returns:
            Dictionary containing standardized result data
        """
        performers_found = len(response.performers) if response.performers else 0
        
        # Extract confidence scores
        confidence_scores = []
        if response.performers:
            for performer in response.performers:
                if hasattr(performer, 'confidence') and performer.confidence is not None:
                    confidence_scores.append(performer.confidence)
        
        # Calculate confidence statistics
        max_confidence = max(confidence_scores) if confidence_scores else None
        avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else None
        
        # Extract tags/performer names for tracking
        performer_names = []
        if response.performers:
            for performer in response.performers:
                if hasattr(performer, 'name') and performer.name:
                    performer_names.append(performer.name)
        
        return {
            'success': response.success,
            'performers_found': performers_found,
            'confidence_scores': confidence_scores,
            'max_confidence': max_confidence,
            'avg_confidence': avg_confidence,
            'tags_applied': performer_names,
            'processing_time': getattr(response, 'processing_time', 0.0),
            'service_name': getattr(response, 'service_name', 'visage'),
            'ai_model_info': getattr(response, 'ai_model_info', {}),
            'faces_detected': len(response.faces) if response.faces else 0,
            'message': response.message,
            'request_id': response.request_id
        }