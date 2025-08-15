# =============================================================================
# General AI Database Adapter - Plugin-style AI Service Support
# =============================================================================

import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from enum import Enum
from sqlalchemy import Column, String, JSON, DateTime, Text, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from Database.database import get_db_session
from Database.data.queue_models import QueueTask

Base = declarative_base()

class GeneralAITaskTypes(Enum):
    """General AI task types"""
    GENERAL_PROCESSING = "general_ai_processing"
    CUSTOM_MODEL = "general_ai_custom_model"
    PLUGIN_TASK = "general_ai_plugin_task"

class GeneralAIResults(Base):
    """Table for storing general AI service results"""
    __tablename__ = 'general_ai_results'
    
    task_id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey('queue_jobs.job_id'), nullable=True)
    service_type = Column(String, nullable=False)  # Type of AI service used
    stash_content_id = Column(String, nullable=True)
    stash_content_title = Column(String, nullable=True)
    
    # Flexible result storage
    result_data = Column(JSON, nullable=True)  # Main results from AI service
    metadata = Column(JSON, nullable=True)    # Service-specific metadata
    raw_response = Column(JSON, nullable=True)  # Raw API response
    
    # Processing info
    api_endpoint = Column(String, nullable=True)
    processing_time_ms = Column(JSON, nullable=True)
    confidence_scores = Column(JSON, nullable=True)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class GeneralAIDatabaseAdapter:
    """Database adapter for general AI tasks and results"""
    
    def __init__(self):
        self.db = get_db_session()
        
        # Create tables if they don't exist
        try:
            engine = self.db.get_bind()
            GeneralAIResults.__table__.create(engine, checkfirst=True)
        except Exception as e:
            print(f"Note: Could not create general_ai_results table: {e}")
    
    def create_task(
        self, 
        task_type: GeneralAITaskTypes,
        service_type: str,
        input_data: Dict[str, Any],
        job_id: Optional[str] = None,
        priority: int = 5
    ) -> str:
        """Create a new general AI task"""
        task_id = str(uuid.uuid4())
        
        # Create queue task entry
        queue_task = QueueTask(
            task_id=task_id,
            job_id=job_id,
            adapter_name="general_ai",
            task_type=task_type.value,
            input_data={
                **input_data,
                "service_type": service_type  # Include service type in input data
            },
            priority=priority,
            status="pending"
        )
        
        self.db.add(queue_task)
        self.db.commit()
        
        return task_id
    
    def update_task_status(self, task_id: str, status: str, output_data: Optional[Dict[str, Any]] = None):
        """Update task status in queue"""
        task = self.db.query(QueueTask).filter(QueueTask.task_id == task_id).first()
        if task:
            task.status = status
            if output_data:
                task.output_json = output_data
            task.updated_at = datetime.now(timezone.utc)
            self.db.commit()
    
    def store_result(
        self,
        task_id: str,
        service_type: str,
        result_data: Dict[str, Any],
        job_id: Optional[str] = None,
        stash_content_id: Optional[str] = None,
        stash_content_title: Optional[str] = None,
        api_endpoint: Optional[str] = None
    ):
        """Store general AI results"""
        
        # Extract common fields
        main_results = result_data.get("results", result_data)
        metadata = result_data.get("metadata", {})
        raw_response = result_data.get("raw_response", result_data)
        processing_time_ms = result_data.get("processing_time_ms")
        confidence_scores = result_data.get("confidence_scores", {})
        
        # Create result record
        result = GeneralAIResults(
            task_id=task_id,
            job_id=job_id,
            service_type=service_type,
            stash_content_id=stash_content_id,
            stash_content_title=stash_content_title,
            result_data=main_results,
            metadata={
                **metadata,
                "service_type": service_type,
                "api_endpoint": api_endpoint,
                "processing_timestamp": datetime.now(timezone.utc).isoformat()
            },
            raw_response=raw_response,
            api_endpoint=api_endpoint,
            processing_time_ms=processing_time_ms,
            confidence_scores=confidence_scores
        )
        
        self.db.add(result)
        self.db.commit()
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get general AI result for a task"""
        result = self.db.query(GeneralAIResults).filter(
            GeneralAIResults.task_id == task_id
        ).first()
        
        if result:
            return {
                "task_id": result.task_id,
                "service_type": result.service_type,
                "stash_content_id": result.stash_content_id,
                "stash_content_title": result.stash_content_title,
                "result_data": result.result_data,
                "metadata": result.metadata,
                "api_endpoint": result.api_endpoint,
                "processing_time_ms": result.processing_time_ms,
                "confidence_scores": result.confidence_scores,
                "created_at": result.created_at.isoformat()
            }
        
        return None
    
    def get_job_results(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all general AI results for a job"""
        results = self.db.query(GeneralAIResults).filter(
            GeneralAIResults.job_id == job_id
        ).all()
        
        return [
            {
                "task_id": result.task_id,
                "service_type": result.service_type,
                "stash_content_id": result.stash_content_id,
                "stash_content_title": result.stash_content_title,
                "result_data": result.result_data,
                "metadata": result.metadata,
                "api_endpoint": result.api_endpoint,
                "processing_time_ms": result.processing_time_ms,
                "confidence_scores": result.confidence_scores,
                "created_at": result.created_at.isoformat()
            }
            for result in results
        ]
    
    def get_results_by_service_type(self, service_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent results for a specific service type"""
        results = self.db.query(GeneralAIResults).filter(
            GeneralAIResults.service_type == service_type
        ).order_by(GeneralAIResults.created_at.desc()).limit(limit).all()
        
        return [
            {
                "task_id": result.task_id,
                "service_type": result.service_type,
                "stash_content_id": result.stash_content_id,
                "stash_content_title": result.stash_content_title,
                "result_data": result.result_data,
                "metadata": result.metadata,
                "api_endpoint": result.api_endpoint,
                "processing_time_ms": result.processing_time_ms,
                "confidence_scores": result.confidence_scores,
                "created_at": result.created_at.isoformat()
            }
            for result in results
        ]
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task information from queue"""
        task = self.db.query(QueueTask).filter(QueueTask.task_id == task_id).first()
        if task:
            return task.to_dict()
        return None
    
    def __del__(self):
        """Clean up database connection"""
        if hasattr(self, 'db') and self.db:
            self.db.close()