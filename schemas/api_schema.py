# =============================================================================
# StashAI Server - Unified API Schema
# =============================================================================

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Optional, Any, Union
from enum import Enum
import base64
from datetime import datetime

# =============================================================================
# Core Types and Enums
# =============================================================================

class ServiceType(str, Enum):
    FACIAL_RECOGNITION = "facial_recognition"
    CONTENT_ANALYSIS = "content_analysis"
    METADATA_EXTRACTION = "metadata_extraction"
    SCENE_ANALYSIS = "scene_analysis"

class EntityType(str, Enum):
    SCENE = "scene"
    GALLERY = "gallery"
    IMAGE = "image"
    PERFORMER = "performer"
    GROUP = "group"

class ProcessingStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

# =============================================================================
# Base Request/Response Models
# =============================================================================

class BaseRequest(BaseModel):
    """Base request model with common fields"""
    request_id: Optional[str] = Field(None, description="Unique request identifier")
    client_id: Optional[str] = Field(None, description="Client identifier for tracking")
    priority: int = Field(1, ge=1, le=10, description="Processing priority (1=highest, 10=lowest)")
    timeout: int = Field(30, ge=5, le=300, description="Request timeout in seconds")

class BaseResponse(BaseModel):
    """Base response model with common fields"""
    success: bool = Field(description="Whether the request was successful")
    message: Optional[str] = Field(None, description="Human-readable message")
    error: Optional[str] = Field(None, description="Error message if failed")
    request_id: Optional[str] = Field(None, description="Original request identifier")
    processing_time: Optional[float] = Field(None, description="Processing time in seconds")
    service_name: Optional[str] = Field(None, description="Name of the service that processed the request")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")

# =============================================================================
# Entity Models
# =============================================================================

class StashEntity(BaseModel):
    """Represents a Stash entity (scene, gallery, etc.)"""
    id: str = Field(description="Stash entity ID")
    type: EntityType = Field(description="Type of entity")
    title: Optional[str] = Field(None, description="Entity title")
    path: Optional[str] = Field(None, description="File path or URL")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class PerformerInfo(BaseModel):
    """Performer information model"""
    id: str = Field(description="Performer ID")
    name: str = Field(description="Performer name")
    confidence: float = Field(ge=0.0, le=1.0, description="Confidence score")
    image_url: Optional[str] = Field(None, description="Performer image URL")
    stash_url: Optional[str] = Field(None, description="Stash performer URL")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="Additional performer metadata")

class FaceInfo(BaseModel):
    """Face detection information"""
    bbox: List[int] = Field(description="Bounding box coordinates [x, y, width, height]")
    confidence: float = Field(ge=0.0, le=1.0, description="Face detection confidence")
    landmarks: Optional[List[List[float]]] = Field(None, description="Facial landmarks")
    age_estimate: Optional[int] = Field(None, description="Estimated age")
    gender: Optional[str] = Field(None, description="Estimated gender")

# =============================================================================
# Facial Recognition API Models
# =============================================================================

class ImageData(BaseModel):
    """Image data for processing"""
    data: str = Field(description="Base64 encoded image data")
    format: str = Field(default="jpeg", description="Image format (jpeg, png, etc.)")
    
    @validator('data')
    def validate_base64(cls, v):
        try:
            # Handle data URLs
            if v.startswith('data:'):
                v = v.split(',')[1]
            base64.b64decode(v)
            return v
        except Exception:
            raise ValueError("Invalid base64 image data")

class FacialRecognitionRequest(BaseRequest):
    """Base facial recognition request"""
    entity: StashEntity = Field(description="Stash entity to process")
    image_data: Optional[ImageData] = Field(None, description="Image data if not using entity path")
    threshold: float = Field(0.5, ge=0.0, le=1.0, description="Recognition confidence threshold")
    max_results: int = Field(5, ge=1, le=50, description="Maximum number of results to return")
    batch_job_id: Optional[str] = Field(None, description="Optional batch job ID to link this test to an existing job")

class SceneIdentificationRequest(FacialRecognitionRequest):
    """Request for scene performer identification"""
    analyze_frames: bool = Field(True, description="Whether to analyze video frames")
    frame_interval: int = Field(10, ge=1, le=60, description="Interval between frame analysis (seconds)")
    use_existing_screenshots: bool = Field(True, description="Use existing scene screenshots")

class GalleryIdentificationRequest(FacialRecognitionRequest):
    """Request for gallery performer identification"""
    batch_size: int = Field(10, ge=1, le=100, description="Number of images to process at once")
    skip_low_quality: bool = Field(True, description="Skip low quality/small faces")
    images: Optional[List[dict]] = Field(None, description="List of gallery images to process")

class FaceComparisonRequest(BaseRequest):
    """Request for face comparison"""
    performer1_id: str = Field(description="First performer ID")
    performer2_id: str = Field(description="Second performer ID")
    comparison_models: List[str] = Field(["arcface", "facenet"], description="Models to use for comparison")

class FacialRecognitionResponse(BaseResponse):
    """Response for facial recognition requests"""
    entity: Optional[StashEntity] = Field(None, description="Processed entity")
    performers: List[PerformerInfo] = Field(default_factory=list, description="Identified performers")
    faces: List[FaceInfo] = Field(default_factory=list, description="Detected faces")
    ai_model_info: Optional[Dict[str, Any]] = Field(None, description="Model information used")
    
    model_config = {"protected_namespaces": ()}

class FaceComparisonResponse(BaseResponse):
    """Response for face comparison"""
    performer1: PerformerInfo = Field(description="First performer")
    performer2: PerformerInfo = Field(description="Second performer")
    similarity: float = Field(ge=0.0, le=1.0, description="Overall similarity score")
    ai_model_scores: Dict[str, float] = Field(description="Individual model similarity scores")
    is_match: bool = Field(description="Whether faces are considered a match")
    
    model_config = {"protected_namespaces": ()}

# =============================================================================
# Content Analysis API Models
# =============================================================================

class ContentAnalysisRequest(BaseRequest):
    """Request for content analysis"""
    entity: StashEntity = Field(description="Entity to analyze")
    analysis_types: List[str] = Field(["tags", "categories", "quality"], description="Types of analysis to perform")
    generate_tags: bool = Field(True, description="Generate content tags")
    extract_metadata: bool = Field(True, description="Extract technical metadata")

class TagInfo(BaseModel):
    """Content tag information"""
    name: str = Field(description="Tag name")
    confidence: float = Field(ge=0.0, le=1.0, description="Tag confidence")
    category: Optional[str] = Field(None, description="Tag category")

class ContentAnalysisResponse(BaseResponse):
    """Response for content analysis"""
    entity: Optional[StashEntity] = Field(None, description="Analyzed entity")
    tags: List[TagInfo] = Field(default_factory=list, description="Generated tags")
    categories: List[str] = Field(default_factory=list, description="Content categories")
    quality_score: Optional[float] = Field(None, description="Content quality score")
    technical_metadata: Optional[Dict[str, Any]] = Field(None, description="Technical metadata")

# =============================================================================
# Batch Processing Models
# =============================================================================

class BatchRequest(BaseRequest):
    """Request for batch processing"""
    entities: List[StashEntity] = Field(description="List of entities to process")
    operation: str = Field(description="Operation to perform")
    batch_size: int = Field(10, ge=1, le=100, description="Batch processing size")
    parallel_processing: bool = Field(True, description="Enable parallel processing")

class BatchJobStatus(BaseModel):
    """Status of a batch job"""
    job_id: str = Field(description="Batch job ID")
    status: ProcessingStatus = Field(description="Current job status")
    total_items: int = Field(description="Total number of items")
    processed_items: int = Field(description="Number of processed items")
    failed_items: int = Field(description="Number of failed items")
    progress_percentage: float = Field(ge=0.0, le=100.0, description="Progress percentage")
    started_at: datetime = Field(description="Job start time")
    estimated_completion: Optional[datetime] = Field(None, description="Estimated completion time")

class BatchResponse(BaseResponse):
    """Response for batch operations"""
    job_status: BatchJobStatus = Field(description="Batch job status")
    results: Optional[List[Any]] = Field(None, description="Batch results if completed")
    partial_results: Optional[List[Any]] = Field(None, description="Partial results for ongoing jobs")

# =============================================================================
# Service Management Models
# =============================================================================

class ServiceInfo(BaseModel):
    """Information about a registered service"""
    name: str = Field(description="Service name")
    type: ServiceType = Field(description="Service type")
    version: str = Field(description="Service version")
    endpoint: str = Field(description="Service endpoint URL")
    health_check_url: str = Field(description="Health check endpoint")
    capabilities: List[str] = Field(description="Service capabilities")
    status: str = Field(description="Current service status")
    last_health_check: Optional[datetime] = Field(None, description="Last health check time")

class HealthCheckResponse(BaseResponse):
    """Health check response"""
    service_name: str = Field(description="Service name")
    status: str = Field(description="Service status")
    version: str = Field(description="Service version")
    uptime: float = Field(description="Service uptime in seconds")
    dependencies: Optional[Dict[str, str]] = Field(None, description="Dependency status")
    metrics: Optional[Dict[str, Any]] = Field(None, description="Service metrics")

# =============================================================================
# Error Models
# =============================================================================

class APIError(BaseModel):
    """API error details"""
    code: str = Field(description="Error code")
    message: str = Field(description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    trace_id: Optional[str] = Field(None, description="Request trace ID")

class ValidationError(APIError):
    """Validation error details"""
    field_errors: Dict[str, List[str]] = Field(description="Field-specific validation errors")

# =============================================================================
# API Endpoint Definitions
# =============================================================================

API_ENDPOINTS = {
    "facial_recognition": {
        "identify_scene": {
            "path": "/api/v1/facial-recognition/identify-scene",
            "method": "POST",
            "request_model": SceneIdentificationRequest,
            "response_model": FacialRecognitionResponse,
            "description": "Identify performers in a scene"
        },
        "identify_gallery": {
            "path": "/api/v1/facial-recognition/identify-gallery", 
            "method": "POST",
            "request_model": GalleryIdentificationRequest,
            "response_model": FacialRecognitionResponse,
            "description": "Identify performers in gallery images"
        },
        "identify_image": {
            "path": "/api/v1/facial-recognition/identify-image",
            "method": "POST", 
            "request_model": FacialRecognitionRequest,
            "response_model": FacialRecognitionResponse,
            "description": "Identify performers in a single image"
        },
        "compare_faces": {
            "path": "/api/v1/facial-recognition/compare-faces",
            "method": "POST",
            "request_model": FaceComparisonRequest, 
            "response_model": FaceComparisonResponse,
            "description": "Compare faces between two performers"
        }
    },
    "content_analysis": {
        "analyze_scene": {
            "path": "/api/v1/content-analysis/analyze-scene",
            "method": "POST",
            "request_model": ContentAnalysisRequest,
            "response_model": ContentAnalysisResponse,
            "description": "Analyze scene content for tags and metadata"
        },
        "extract_metadata": {
            "path": "/api/v1/content-analysis/extract-metadata",
            "method": "POST", 
            "request_model": ContentAnalysisRequest,
            "response_model": ContentAnalysisResponse,
            "description": "Extract technical metadata from content"
        }
    },
    "batch": {
        "submit_job": {
            "path": "/api/v1/batch/submit",
            "method": "POST",
            "request_model": BatchRequest,
            "response_model": BatchResponse,
            "description": "Submit a batch processing job"
        },
        "get_status": {
            "path": "/api/v1/batch/{job_id}/status",
            "method": "GET", 
            "response_model": BatchJobStatus,
            "description": "Get batch job status"
        }
    },
    "system": {
        "health": {
            "path": "/api/v1/health",
            "method": "GET",
            "response_model": HealthCheckResponse,
            "description": "System health check"
        },
        "services": {
            "path": "/api/v1/services",
            "method": "GET",
            "response_model": List[ServiceInfo],
            "description": "List registered services"
        }
    }
}