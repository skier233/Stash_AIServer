# =============================================================================
# Scene Analysis Database Adapter
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

class SceneAnalysisTaskTypes(Enum):
    """Scene Analysis task types"""
    ANALYZE_SCENE = "scene_analyze_scene"
    EXTRACT_KEYFRAMES = "scene_extract_keyframes"
    DETECT_CUTS = "scene_detect_cuts"
    ANALYZE_AUDIO = "scene_analyze_audio"
    GENERATE_SUMMARY = "scene_generate_summary"

class SceneAnalysisResults(Base):
    """Table for storing scene analysis results"""
    __tablename__ = 'scene_analysis_results'
    
    task_id = Column(String, primary_key=True)
    job_id = Column(String, ForeignKey('queue_jobs.job_id'), nullable=True)
    stash_content_id = Column(String, nullable=True)
    stash_content_title = Column(String, nullable=True)
    
    # Scene analysis results
    scenes = Column(JSON, nullable=True)  # Detected scenes with timestamps
    keyframes = Column(JSON, nullable=True)  # Extracted keyframes
    objects = Column(JSON, nullable=True)  # Objects detected across scenes
    activities = Column(JSON, nullable=True)  # Activities/actions detected
    audio_analysis = Column(JSON, nullable=True)  # Audio analysis results
    
    # Technical metadata
    duration_ms = Column(JSON, nullable=True)  # Content duration
    resolution = Column(JSON, nullable=True)  # Video resolution
    frame_rate = Column(JSON, nullable=True)  # Frame rate
    scene_changes = Column(JSON, nullable=True)  # Scene change timestamps
    
    # Summary and insights
    summary = Column(JSON, nullable=True)  # Generated summary
    tags = Column(JSON, nullable=True)  # Scene-based tags
    
    # Metadata
    confidence_scores = Column(JSON, nullable=True)
    processing_metadata = Column(JSON, nullable=True)
    api_response = Column(JSON, nullable=True)  # Raw API response
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

class SceneAnalysisDatabaseAdapter:
    """Database adapter for scene analysis tasks and results"""
    
    def __init__(self):
        self.db = get_db_session()
        
        # Create tables if they don't exist
        try:
            engine = self.db.get_bind()
            SceneAnalysisResults.__table__.create(engine, checkfirst=True)
        except Exception as e:
            print(f"Note: Could not create scene_analysis_results table: {e}")
    
    def create_task(
        self, 
        task_type: SceneAnalysisTaskTypes, 
        input_data: Dict[str, Any],
        job_id: Optional[str] = None,
        priority: int = 5
    ) -> str:
        """Create a new scene analysis task"""
        task_id = str(uuid.uuid4())
        
        # Create queue task entry
        queue_task = QueueTask(
            task_id=task_id,
            job_id=job_id,
            adapter_name="scene_analysis",
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
        stash_content_id: Optional[str] = None,
        stash_content_title: Optional[str] = None
    ):
        """Store scene analysis results"""
        
        # Parse result data
        scenes = result_data.get("scenes", [])
        keyframes = result_data.get("keyframes", [])
        objects = result_data.get("objects", [])
        activities = result_data.get("activities", [])
        audio_analysis = result_data.get("audio", {})
        duration_ms = result_data.get("duration_ms")
        resolution = result_data.get("resolution", {})
        frame_rate = result_data.get("frame_rate")
        scene_changes = result_data.get("scene_changes", [])
        summary = result_data.get("summary", "")
        tags = result_data.get("tags", [])
        confidence_scores = result_data.get("confidence_scores", {})
        api_response = result_data.get("raw_response", {})
        
        # Create result record
        result = SceneAnalysisResults(
            task_id=task_id,
            job_id=job_id,
            stash_content_id=stash_content_id,
            stash_content_title=stash_content_title,
            scenes=scenes,
            keyframes=keyframes,
            objects=objects,
            activities=activities,
            audio_analysis=audio_analysis,
            duration_ms=duration_ms,
            resolution=resolution,
            frame_rate=frame_rate,
            scene_changes=scene_changes,
            summary=summary,
            tags=tags,
            confidence_scores=confidence_scores,
            processing_metadata={
                "total_scenes": len(scenes) if scenes else 0,
                "total_keyframes": len(keyframes) if keyframes else 0,
                "has_audio": bool(audio_analysis),
                "processing_time_ms": result_data.get("processing_time_ms"),
                "api_endpoint": result_data.get("api_endpoint")
            },
            api_response=api_response
        )
        
        self.db.add(result)
        self.db.commit()
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get scene analysis result for a task"""
        result = self.db.query(SceneAnalysisResults).filter(
            SceneAnalysisResults.task_id == task_id
        ).first()
        
        if result:
            return {
                "task_id": result.task_id,
                "stash_content_id": result.stash_content_id,
                "stash_content_title": result.stash_content_title,
                "scenes": result.scenes,
                "keyframes": result.keyframes,
                "objects": result.objects,
                "activities": result.activities,
                "audio_analysis": result.audio_analysis,
                "duration_ms": result.duration_ms,
                "resolution": result.resolution,
                "frame_rate": result.frame_rate,
                "scene_changes": result.scene_changes,
                "summary": result.summary,
                "tags": result.tags,
                "confidence_scores": result.confidence_scores,
                "processing_metadata": result.processing_metadata,
                "created_at": result.created_at.isoformat()
            }
        
        return None
    
    def get_job_results(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all scene analysis results for a job"""
        results = self.db.query(SceneAnalysisResults).filter(
            SceneAnalysisResults.job_id == job_id
        ).all()
        
        return [
            {
                "task_id": result.task_id,
                "stash_content_id": result.stash_content_id,
                "stash_content_title": result.stash_content_title,
                "scenes": result.scenes,
                "keyframes": result.keyframes,
                "objects": result.objects,
                "activities": result.activities,
                "audio_analysis": result.audio_analysis,
                "duration_ms": result.duration_ms,
                "resolution": result.resolution,
                "frame_rate": result.frame_rate,
                "scene_changes": result.scene_changes,
                "summary": result.summary,
                "tags": result.tags,
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