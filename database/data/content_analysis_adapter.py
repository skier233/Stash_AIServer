# =============================================================================
# Content Analysis Database Adapter
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

class ContentAnalysisTaskTypes(Enum):
    """Content Analysis task types"""
    ANALYZE_CONTENT = "content_analyze_content"
    GENERATE_TAGS = "content_generate_tags"
    GENERATE_DESCRIPTION = "content_generate_description"
    EXTRACT_TEXT = "content_extract_text"
    DETECT_OBJECTS = "content_detect_objects"

class ContentAnalysisResults(Base):
    """Table for storing content analysis results"""
    __tablename__ = 'content_analysis_results'
    
    task_id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey('queue_jobs.job_id'), nullable=True)
    stash_image_id = Column(String, nullable=True)
    stash_image_title = Column(String, nullable=True)
    
    # Analysis results
    tags = Column(JSON, nullable=True)  # Generated tags with confidence scores
    descriptions = Column(JSON, nullable=True)  # Generated descriptions
    objects = Column(JSON, nullable=True)  # Detected objects
    text_content = Column(JSON, nullable=True)  # Extracted text (OCR)
    colors = Column(JSON, nullable=True)  # Color analysis
    composition = Column(JSON, nullable=True)  # Composition analysis
    
    # Metadata
    confidence_scores = Column(JSON, nullable=True)
    processing_metadata = Column(JSON, nullable=True)
    api_response = Column(JSON, nullable=True)  # Raw API response
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class ContentAnalysisDatabaseAdapter:
    """Database adapter for content analysis tasks and results"""
    
    def __init__(self):
        self.db = get_db_session()
        
        # Create tables if they don't exist
        try:
            engine = self.db.get_bind()
            ContentAnalysisResults.__table__.create(engine, checkfirst=True)
        except Exception as e:
            print(f"Note: Could not create content_analysis_results table: {e}")
    
    def create_task(
        self, 
        task_type: ContentAnalysisTaskTypes, 
        input_data: Dict[str, Any],
        job_id: Optional[str] = None,
        priority: int = 5
    ) -> str:
        """Create a new content analysis task"""
        task_id = str(uuid.uuid4())
        
        # Create queue task entry
        queue_task = QueueTask(
            task_id=task_id,
            job_id=job_id,
            adapter_name="content_analysis",
            task_type=task_type.value,
            input_data=input_data,
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
        result_data: Dict[str, Any],
        job_id: Optional[str] = None,
        stash_image_id: Optional[str] = None,
        stash_image_title: Optional[str] = None
    ):
        """Store content analysis results"""
        
        # Parse result data
        tags = result_data.get("tags", [])
        descriptions = result_data.get("descriptions", [])
        objects = result_data.get("objects", [])
        text_content = result_data.get("text", [])
        colors = result_data.get("colors", [])
        composition = result_data.get("composition", {})
        confidence_scores = result_data.get("confidence_scores", {})
        api_response = result_data.get("raw_response", {})
        
        # Create result record
        result = ContentAnalysisResults(
            task_id=task_id,
            job_id=job_id,
            stash_image_id=stash_image_id,
            stash_image_title=stash_image_title,
            tags=tags,
            descriptions=descriptions,
            objects=objects,
            text_content=text_content,
            colors=colors,
            composition=composition,
            confidence_scores=confidence_scores,
            processing_metadata={
                "total_tags": len(tags) if tags else 0,
                "total_objects": len(objects) if objects else 0,
                "has_text": bool(text_content),
                "processing_time_ms": result_data.get("processing_time_ms"),
                "api_endpoint": result_data.get("api_endpoint")
            },
            api_response=api_response
        )
        
        self.db.add(result)
        self.db.commit()
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get content analysis result for a task"""
        result = self.db.query(ContentAnalysisResults).filter(
            ContentAnalysisResults.task_id == task_id
        ).first()
        
        if result:
            return {
                "task_id": result.task_id,
                "stash_image_id": result.stash_image_id,
                "stash_image_title": result.stash_image_title,
                "tags": result.tags,
                "descriptions": result.descriptions,
                "objects": result.objects,
                "text_content": result.text_content,
                "colors": result.colors,
                "composition": result.composition,
                "confidence_scores": result.confidence_scores,
                "processing_metadata": result.processing_metadata,
                "created_at": result.created_at.isoformat()
            }
        
        return None
    
    def get_job_results(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all content analysis results for a job"""
        results = self.db.query(ContentAnalysisResults).filter(
            ContentAnalysisResults.job_id == job_id
        ).all()
        
        return [
            {
                "task_id": result.task_id,
                "stash_image_id": result.stash_image_id,
                "stash_image_title": result.stash_image_title,
                "tags": result.tags,
                "descriptions": result.descriptions,
                "objects": result.objects,
                "text_content": result.text_content,
                "colors": result.colors,
                "composition": result.composition,
                "confidence_scores": result.confidence_scores,
                "processing_metadata": result.processing_metadata,
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