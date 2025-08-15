# =============================================================================
# Visage Database Queue Adapter - Template for API Service Integration
# =============================================================================
# 
# This adapter demonstrates how to integrate any API service with the StashAI
# Queue Manager to add batch processing and parallel execution capabilities.
#
# TEMPLATE USAGE:
# 1. Copy this file and rename it for your service (e.g., YourServiceDatabaseQueueAdapter.py)
# 2. Update the enums to match your service's operations
# 3. Modify the Job and Task models to include service-specific fields
# 4. Create corresponding Celery tasks in Services/queue/tasks/
# 5. Add API endpoints in api/endpoints.py
#
# This example shows Visage facial recognition service integration.
# =============================================================================

from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, ForeignKey, Float
from sqlalchemy.orm import relationship
from Database.models import Base

# =============================================================================
# TEMPLATE SECTION 1: Status Enums (Universal - can be reused for any service)
# =============================================================================

class JobStatus(Enum):
    """Universal job status - reusable for any service adapter"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Some tasks completed, some failed

class TaskStatus(Enum):
    """Universal task status - reusable for any service adapter"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"

# =============================================================================
# TEMPLATE SECTION 2: Service-Specific Enums (Customize for your service)
# =============================================================================

class VisageJobType(Enum):
    """Visage-specific job types - TEMPLATE: Replace with your service operations"""
    BATCH_FACE_IDENTIFICATION = "visage_batch_face_identification"
    BATCH_FACE_COMPARISON = "visage_batch_face_comparison"
    BATCH_ONE_TO_MANY_COMPARE = "visage_batch_one_to_many_compare"
    BATCH_MANY_TO_MANY_COMPARE = "visage_batch_many_to_many_compare"
    BATCH_FACE_SEARCH = "visage_batch_face_search"
    BULK_PERFORMER_ANALYSIS = "visage_bulk_performer_analysis"

class VisageTaskType(Enum):
    """Visage-specific task types - TEMPLATE: Replace with your service's atomic operations"""
    SINGLE_FACE_IDENTIFY = "visage_single_face_identify"
    SINGLE_FACE_COMPARE = "visage_single_face_compare"
    SINGLE_FACE_SEARCH = "visage_single_face_search"
    EXTRACT_FACE_EMBEDDING = "visage_extract_face_embedding"
    PERFORMER_FACE_ANALYSIS = "visage_performer_face_analysis"

# =============================================================================
# TEMPLATE SECTION 3: Database Models (Universal structure, customize fields)
# =============================================================================

class VisageJob(Base):
    """
    Visage Job Model - TEMPLATE: Rename to YourServiceJob for other services
    
    A Job represents a batch operation that consists of multiple Tasks.
    Example: "Identify faces in 100 images" = 1 Job with 100 Tasks
    """
    __tablename__ = "visage_jobs"  # TEMPLATE: Rename to your_service_jobs
    
    # Universal fields (keep these for any service)
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)  # UUID for external reference
    job_type = Column(String, index=True)  # VisageJobType enum value
    status = Column(String, index=True, default=JobStatus.PENDING.value)
    
    # Job metadata (universal)
    name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    priority = Column(Integer, default=5)  # 0-9, higher is more priority
    
    # Configuration (universal)
    job_config = Column(JSON, nullable=True)  # Job-specific configuration
    batch_size = Column(Integer, default=4)  # Number of parallel tasks
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Float, default=60.0)  # seconds
    
    # Progress tracking (universal)
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    progress_percentage = Column(Float, default=0.0)
    
    # Results (universal)
    result_data = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # TEMPLATE: Visage-specific fields (customize for your service)
    face_threshold = Column(Float, default=0.5)  # Visage face recognition threshold
    model_type = Column(String, default="arc")  # "arc" or "facenet"
    return_face_locations = Column(String, default="true")  # Return bounding boxes
    performer_database_version = Column(String, nullable=True)  # DB version used
    
    # Timestamps (universal)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # User/session tracking (universal)
    user_id = Column(String, index=True, nullable=True)
    session_id = Column(String, index=True, nullable=True)
    
    # Relationships (universal)
    tasks = relationship("VisageTask", back_populates="job", cascade="all, delete-orphan")

class VisageTask(Base):
    """
    Visage Task Model - TEMPLATE: Rename to YourServiceTask for other services
    
    A Task represents a single atomic operation within a Job.
    Example: "Identify face in image_001.jpg" = 1 Task within a Job
    """
    __tablename__ = "visage_tasks"  # TEMPLATE: Rename to your_service_tasks
    
    # Universal fields (keep these for any service)
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)  # UUID for external reference
    celery_task_id = Column(String, index=True, nullable=True)  # Celery task ID
    task_type = Column(String, index=True)  # VisageTaskType enum value
    status = Column(String, index=True, default=TaskStatus.PENDING.value)
    
    # Task data (universal)
    input_data = Column(JSON, nullable=True)  # Input parameters
    result_data = Column(JSON, nullable=True)  # Task result
    error_message = Column(Text, nullable=True)
    
    # Execution tracking (universal)
    priority = Column(Integer, default=5)
    attempt_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # TEMPLATE: Visage-specific fields (customize for your service)
    image_path = Column(String, nullable=True)  # Path to image being processed
    image_hash = Column(String, nullable=True)  # Hash for duplicate detection
    face_count = Column(Integer, default=0)  # Number of faces found
    confidence_score = Column(Float, nullable=True)  # Highest confidence match
    processing_time_ms = Column(Float, nullable=True)  # Task execution time
    
    # Timestamps (universal)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Relationships (universal)
    job_id = Column(Integer, ForeignKey("visage_jobs.id"), index=True)  # TEMPLATE: Update FK
    job = relationship("VisageJob", back_populates="tasks")

# =============================================================================
# TEMPLATE SECTION 4: Helper Classes (Optional - add service-specific utilities)
# =============================================================================

class VisageJobConfig:
    """
    TEMPLATE: Configuration helper for Visage jobs
    Create similar classes for other services
    """
    @staticmethod
    def batch_face_identification_config(
        threshold: float = 0.5,
        model_type: str = "arc",
        batch_size: int = 4,
        return_locations: bool = True
    ) -> dict:
        """Configuration for batch face identification jobs"""
        return {
            "face_threshold": threshold,
            "model_type": model_type,
            "batch_size": batch_size,
            "return_face_locations": return_locations,
            "job_type": VisageJobType.BATCH_FACE_IDENTIFICATION.value
        }
    
    @staticmethod
    def batch_face_comparison_config(
        threshold: float = 0.5,
        batch_size: int = 4,
        comparison_mode: str = "one_to_many"
    ) -> dict:
        """Configuration for batch face comparison jobs"""
        return {
            "face_threshold": threshold,
            "batch_size": batch_size,
            "comparison_mode": comparison_mode,
            "job_type": VisageJobType.BATCH_FACE_COMPARISON.value
        }