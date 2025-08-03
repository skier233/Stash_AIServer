# =============================================================================
# StashAI Server - Clean Database Schema
# =============================================================================

from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Float, Boolean, ForeignKey, Index, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from pydantic import BaseModel

Base = declarative_base()

# =============================================================================
# Enums
# =============================================================================

class EntityType(str, Enum):
    SCENE = "scene"
    GALLERY = "gallery" 
    IMAGE = "image"
    PERFORMER = "performer"
    STUDIO = "studio"
    TAG = "tag"

class AIActionType(str, Enum):
    FACIAL_RECOGNITION = "facial_recognition"
    SCENE_IDENTIFICATION = "scene_identification"
    GALLERY_IDENTIFICATION = "gallery_identification"
    IMAGE_IDENTIFICATION = "image_identification"
    FACE_COMPARISON = "face_comparison"
    CONTENT_ANALYSIS = "content_analysis"

class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL_COMPLETE = "partial_complete"

class TestResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    PENDING = "pending"
    ERROR = "error"

class AIModel(str, Enum):
    VISAGE = "visage"
    OPENAI_VISION = "openai_vision"
    CUSTOM = "custom"

# =============================================================================
# Database Tables
# =============================================================================

class Job(Base):
    """Processing jobs with lifecycle tracking"""
    __tablename__ = "processing_jobs"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String(36), unique=True, index=True, nullable=False)
    
    # Job Definition
    job_name = Column(String(200), nullable=True)
    entity_type = Column(String(20), index=True, nullable=False)
    entity_id = Column(String(50), index=True, nullable=False)
    entity_name = Column(String(500), nullable=True)
    action_type = Column(String(30), index=True, nullable=False)
    
    # Job Status & Lifecycle
    status = Column(String(20), index=True, default=JobStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    
    # Job Configuration & Context
    job_config = Column(JSON, nullable=True)
    service_name = Column(String(100), nullable=True)
    ai_model = Column(String(50), nullable=True)
    
    # Pre-defined Test List
    total_tests_planned = Column(Integer, default=0, nullable=False)
    test_entity_list = Column(JSON, nullable=True)
    
    # Progress Tracking
    tests_completed = Column(Integer, default=0, nullable=False)
    tests_passed = Column(Integer, default=0, nullable=False)
    tests_failed = Column(Integer, default=0, nullable=False)
    tests_error = Column(Integer, default=0, nullable=False)
    progress_percentage = Column(Float, default=0.0, nullable=False)
    
    # Results Summary (all results stored directly in job table)
    overall_result = Column(String(20), nullable=True)
    performers_found_total = Column(Integer, default=0, nullable=False)
    confidence_scores_summary = Column(JSON, nullable=True)
    tags_applied_summary = Column(JSON, nullable=True)
    results_json = Column(JSON, nullable=True)  # Complete results from AI processing
    results_summary = Column(JSON, nullable=True)  # Summary statistics
    
    # Error Handling
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Relationships
    tests = relationship("Test", back_populates="job", cascade="all, delete-orphan")
    
    # Indexes
    __table_args__ = (
        Index('idx_job_status_created', 'status', 'created_at'),
        Index('idx_job_entity_action', 'entity_type', 'action_type'),
        Index('idx_job_progress', 'status', 'progress_percentage'),
    )

class Test(Base):
    """Individual AI tests within processing jobs"""
    __tablename__ = "processing_tests"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    test_id = Column(String(36), unique=True, index=True, nullable=False)
    
    # Job relationship
    job_id = Column(Integer, ForeignKey("processing_jobs.id", ondelete="CASCADE"), index=True, nullable=False)
    job = relationship("Job", back_populates="tests")
    job_uuid = Column(String(36), index=True, nullable=False)
    
    # Test Target
    entity_type = Column(String(20), index=True, nullable=False)
    entity_id = Column(String(50), index=True, nullable=False)
    entity_filepath = Column(String(1000), nullable=True)
    entity_name = Column(String(500), nullable=True)
    
    # Test Configuration
    test_name = Column(String(200), nullable=True)
    action_type = Column(String(30), index=True, nullable=False)
    ai_model = Column(String(50), nullable=False)
    model_version = Column(String(50), nullable=True)
    test_config = Column(JSON, nullable=True)
    
    # Test Execution
    status = Column(String(20), index=True, default=TestResult.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    processing_time_seconds = Column(Float, nullable=True)
    
    # AI Model Input/Output
    request_data = Column(JSON, nullable=True)
    response_data = Column(JSON, nullable=True)
    
    # Test Results & Evaluation
    result = Column(String(20), nullable=True)
    performers_found = Column(Integer, default=0, nullable=False)
    confidence_scores = Column(JSON, nullable=True)
    max_confidence = Column(Float, nullable=True)
    avg_confidence = Column(Float, nullable=True)
    tags_applied = Column(JSON, nullable=True)
    
    # Model Evaluation Results
    evaluation_criteria = Column(JSON, nullable=True)
    evaluation_reason = Column(Text, nullable=True)
    evaluation_score = Column(Float, nullable=True)
    
    # Error Handling
    error_message = Column(Text, nullable=True)
    error_type = Column(String(50), nullable=True)
    
    # Indexes
    __table_args__ = (
        Index('idx_test_job_status', 'job_id', 'status'),
        Index('idx_test_entity_model', 'entity_type', 'ai_model'),
        Index('idx_test_result_confidence', 'result', 'max_confidence'),
        Index('idx_test_created', 'created_at'),
    )

class Interaction(Base):
    """Unified interaction tracking table following old schema pattern"""
    __tablename__ = "interactions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Core fields following old schema
    entity_type = Column(String(20), index=True, nullable=False)
    entity_id = Column(String(50), index=True, nullable=False)
    session_id = Column(String(100), index=True, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True, nullable=False)
    service = Column(String(50), index=True, nullable=False)
    
    # Additional fields for enhanced tracking
    action_type = Column(String(50), nullable=True)  # What action was performed
    user_id = Column(String(100), nullable=True)
    
    # Metadata stored as JSON for flexibility (renamed to avoid SQLAlchemy reserved word)
    interaction_metadata = Column(JSON, nullable=True)
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_interactions_entity', 'entity_type', 'entity_id'),
        Index('idx_interactions_session', 'session_id', 'timestamp'),
        Index('idx_interactions_service', 'service', 'timestamp'),
        Index('idx_interactions_action', 'action_type', 'timestamp'),
    )

# Removed unnecessary tables: EntityRegistry, JobResult


# =============================================================================
# Pydantic Models for API
# =============================================================================

class JobCreate(BaseModel):
    job_name: Optional[str] = None
    entity_type: EntityType
    entity_id: str
    entity_name: Optional[str] = None
    action_type: AIActionType
    job_config: Optional[Dict[str, Any]] = None
    ai_model: Optional[AIModel] = AIModel.VISAGE
    test_entity_list: Optional[List[Dict[str, Any]]] = None

class JobUpdate(BaseModel):
    status: Optional[JobStatus] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    tests_completed: Optional[int] = None
    tests_passed: Optional[int] = None
    tests_failed: Optional[int] = None
    tests_error: Optional[int] = None
    progress_percentage: Optional[float] = None
    overall_result: Optional[TestResult] = None
    error_message: Optional[str] = None

class JobResponse(BaseModel):
    id: int
    job_id: str
    job_name: Optional[str] = None
    entity_type: str  # Changed from EntityType to str to allow any entity type
    entity_id: str
    entity_name: Optional[str] = None
    action_type: AIActionType
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    progress_percentage: float = 0.0
    total_tests_planned: int = 0
    tests_completed: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_error: int = 0
    performers_found_total: int = 0
    results_json: Optional[Dict[str, Any]] = None
    results_summary: Optional[Dict[str, Any]] = None
    
    class Config:
        from_attributes = True

class TestCreate(BaseModel):
    test_name: Optional[str] = None
    entity_type: EntityType
    entity_id: str
    entity_filepath: Optional[str] = None
    entity_name: Optional[str] = None
    action_type: AIActionType
    ai_model: AIModel
    test_config: Optional[Dict[str, Any]] = None

class TestUpdate(BaseModel):
    status: Optional[TestResult] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    request_data: Optional[Dict[str, Any]] = None
    response_data: Optional[Dict[str, Any]] = None
    result: Optional[TestResult] = None
    performers_found: Optional[int] = None
    confidence_scores: Optional[List[float]] = None
    max_confidence: Optional[float] = None
    avg_confidence: Optional[float] = None
    tags_applied: Optional[List[str]] = None
    evaluation_criteria: Optional[Dict[str, Any]] = None
    evaluation_reason: Optional[str] = None
    evaluation_score: Optional[float] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None

class TestResponse(BaseModel):
    id: int
    test_id: str
    job_uuid: str
    test_name: Optional[str] = None
    entity_type: EntityType
    entity_id: str
    entity_name: Optional[str] = None
    action_type: AIActionType
    status: TestResult
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    processing_time_seconds: Optional[float] = None
    performers_found: int = 0
    max_confidence: Optional[float] = None
    
    class Config:
        from_attributes = True

class InteractionCreate(BaseModel):
    entity_type: EntityType
    entity_id: str
    session_id: str
    service: str
    action_type: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class InteractionResponse(BaseModel):
    id: int
    entity_type: EntityType
    entity_id: str
    session_id: str
    timestamp: datetime
    service: str
    action_type: Optional[str] = None
    user_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def from_orm(cls, obj):
        """Custom from_orm that handles the field name mapping"""
        return cls(
            id=obj.id,
            entity_type=EntityType(obj.entity_type),
            entity_id=obj.entity_id,
            session_id=obj.session_id,
            timestamp=obj.timestamp,
            service=obj.service,
            action_type=obj.action_type,
            user_id=obj.user_id,
            metadata=obj.interaction_metadata
        )
    
    class Config:
        from_attributes = True

# EntityInteractionCreate/Response removed - using unified InteractionCreate/Response instead

class JobHistoryQuery(BaseModel):
    entity_type: Optional[EntityType] = None
    entity_id: Optional[str] = None
    action_type: Optional[AIActionType] = None
    status: Optional[JobStatus] = None
    job_name: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    limit: int = 50
    offset: int = 0

class JobHistoryResponse(BaseModel):
    jobs: List[JobResponse]
    total_count: int
    page: int
    page_size: int
    has_more: bool


# =============================================================================
# Aliases
# =============================================================================

ProcessingJob = Job
ProcessingTest = Test
UserInteraction = Interaction
# Removed AIJobResult alias

ProcessingJobCreate = JobCreate
ProcessingJobUpdate = JobUpdate
ProcessingTestCreate = TestCreate
ProcessingTestUpdate = TestUpdate
UserInteractionCreate = InteractionCreate

AIJob = Job
AITest = Test
EntityInteraction = Interaction

AIJobCreate = JobCreate
AIJobUpdate = JobUpdate
AIJobResponse = JobResponse
AITestCreate = TestCreate
AITestUpdate = TestUpdate
AITestResponse = TestResponse
# EntityInteractionCreate and EntityInteractionResponse are now separate models above
AIJobHistoryQuery = JobHistoryQuery
AIJobHistoryResponse = JobHistoryResponse

ProcessingStatus = JobStatus