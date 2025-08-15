# =============================================================================
# Normalized Queue Database Models - Tasks and Jobs Schema
# =============================================================================
# 
# This implements the normalized schema approach:
# - tasks table: Individual task execution tracking (per adapter)
# - jobs table: Job orchestration and batch management
# 
# Benefits:
# - Task-level granularity for detailed tracking
# - Job-level orchestration for batch operations
# - Adapter flexibility - each service can have its own task types
# - Clean separation between execution tracking and business logic
# =============================================================================

from datetime import datetime, timezone
from enum import Enum
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base

# Use the same Base as the main models
try:
    from Database.models import Base
except ImportError:
    # Fallback if there's a circular import
    Base = declarative_base()

# =============================================================================
# Universal Status Enums
# =============================================================================

class TaskStatus(Enum):
    """Universal task status for all adapters"""
    PENDING = "pending"
    RUNNING = "running"
    FINISHED = "finished"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRY = "retry"

class JobStatus(Enum):
    """Universal job status for batch operations"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PARTIAL = "partial"  # Some tasks completed, some failed

# =============================================================================
# Normalized Database Models
# =============================================================================

class QueueTask(Base):
    """
    Universal tasks table - tracks individual task execution for all adapters
    
    This table stores task-level details for any adapter (Visage, Transcription, etc.)
    Each row represents one atomic task execution with its results.
    """
    __tablename__ = "queue_tasks"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(String, unique=True, index=True)  # Huey task ID
    
    # Adapter and service information
    adapter_name = Column(String, index=True)  # "visage", "transcription", etc.
    task_type = Column(String, index=True)     # "face_identify", "transcribe_audio", etc.
    
    # Execution tracking
    status = Column(String, index=True, default=TaskStatus.PENDING.value)
    priority = Column(Integer, default=5)  # 0-9, higher is more priority
    
    # Task data and results
    input_data = Column(JSON, nullable=True)   # Task input parameters
    output_json = Column(JSON, nullable=True)  # Task results/output
    error_message = Column(Text, nullable=True)
    
    # Performance metrics
    processing_time_ms = Column(Float, nullable=True)
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # Optional job association
    job_id = Column(String, index=True, nullable=True)  # Links to QueueJob.job_id if part of batch

    def to_dict(self):
        """Convert task to dictionary for API responses"""
        return {
            "task_id": self.task_id,
            "adapter_name": self.adapter_name,
            "task_type": self.task_type,
            "status": self.status,
            "input_data": self.input_data,
            "output_json": self.output_json,
            "error_message": self.error_message,
            "processing_time_ms": self.processing_time_ms,
            "retry_count": self.retry_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "job_id": self.job_id
        }

class QueueJob(Base):
    """
    Jobs table - orchestrates batch operations and tracks multiple tasks
    
    This table manages job-level orchestration, linking multiple tasks together
    for batch processing and providing aggregate status tracking.
    """
    __tablename__ = "queue_jobs"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)  # UUID for external reference
    
    # Job metadata
    adapter_name = Column(String, index=True)  # Which adapter this job belongs to
    job_type = Column(String, index=True)      # "batch_face_identify", "bulk_transcribe", etc.
    job_name = Column(String, nullable=True)   # Human-readable name
    description = Column(Text, nullable=True)
    
    # Job orchestration
    status = Column(String, index=True, default=JobStatus.PENDING.value)
    priority = Column(Integer, default=5)
    
    # Task management
    task_ids = Column(JSON, nullable=True)     # Array of task_ids belonging to this job
    total_tasks = Column(Integer, default=0)
    completed_tasks = Column(Integer, default=0)
    failed_tasks = Column(Integer, default=0)
    progress_percentage = Column(Float, default=0.0)
    
    # Configuration
    job_config = Column(JSON, nullable=True)   # Job-specific settings
    batch_size = Column(Integer, default=4)    # Parallelism level
    
    # Results and errors
    aggregate_results = Column(JSON, nullable=True)  # Combined results from all tasks
    error_summary = Column(Text, nullable=True)      # Summary of any errors
    
    # Performance metrics
    total_processing_time_ms = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    # User tracking (optional)
    user_id = Column(String, index=True, nullable=True)
    session_id = Column(String, index=True, nullable=True)

    def to_dict(self):
        """Convert job to dictionary for API responses"""
        return {
            "job_id": self.job_id,
            "adapter_name": self.adapter_name,
            "job_type": self.job_type,
            "job_name": self.job_name,
            "status": self.status,
            "task_ids": self.task_ids or [],
            "total_tasks": self.total_tasks,
            "completed_tasks": self.completed_tasks,
            "failed_tasks": self.failed_tasks,
            "progress_percentage": self.progress_percentage,
            "job_config": self.job_config,
            "aggregate_results": self.aggregate_results,
            "error_summary": self.error_summary,
            "total_processing_time_ms": self.total_processing_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None
        }

    def update_progress(self):
        """Calculate and update progress percentage based on task completion"""
        if self.total_tasks > 0:
            self.progress_percentage = (self.completed_tasks / self.total_tasks) * 100.0
        else:
            self.progress_percentage = 0.0