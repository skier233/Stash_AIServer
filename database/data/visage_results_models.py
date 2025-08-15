# =============================================================================
# Visage Service-Specific Results Models
# =============================================================================
#
# This module defines Visage-specific result storage separate from the
# universal queue tracking. Results are stored here when tasks complete
# for easy querying and service-specific data analysis.
#
# Flow: queue_tasks (execution) → visage_results (output data)
# =============================================================================

from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text, Float, ForeignKey
from sqlalchemy.orm import relationship

# Use the same Base as the main models
try:
    from Database.models import Base
except ImportError:
    from sqlalchemy.ext.declarative import declarative_base
    Base = declarative_base()

# =============================================================================
# Visage Results Table
# =============================================================================

class VisageResult(Base):
    """
    Service-specific storage for Visage face recognition results
    
    This table stores the actual output data from Visage API calls,
    linked to the universal queue system for tracking and organization.
    """
    __tablename__ = "visage_results"
    
    # Primary identification
    id = Column(Integer, primary_key=True, index=True)
    result_id = Column(String, unique=True, index=True)  # UUID for this specific result
    
    # Links to universal queue system
    task_id = Column(String, index=True)  # References queue_tasks.task_id
    job_id = Column(String, index=True, nullable=True)   # References queue_jobs.job_id
    
    # Visage-specific metadata
    visage_api_url = Column(String, nullable=True)      # Which Visage API was called
    input_image_info = Column(JSON, nullable=True)      # Image metadata (size, format, etc.)
    threshold_used = Column(Float, nullable=True)       # Recognition threshold
    
    # Raw Visage API output (the actual results)
    raw_visage_output = Column(JSON)                     # Complete JSON response from Visage API
    
    # Extracted key metrics for easier querying
    faces_detected = Column(Integer, default=0)
    total_matches = Column(Integer, default=0)
    max_confidence = Column(Float, nullable=True)
    min_confidence = Column(Float, nullable=True)
    
    # Processing metadata
    processing_time_ms = Column(Float, nullable=True)
    api_response_time_ms = Column(Float, nullable=True)
    model_version = Column(String, nullable=True)
    
    # Success/failure tracking
    processing_successful = Column(String, default="true")  # "true", "false", "partial"
    error_details = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert result to dictionary for API responses"""
        return {
            "result_id": self.result_id,
            "task_id": self.task_id,
            "job_id": self.job_id,
            "visage_api_url": self.visage_api_url,
            "faces_detected": self.faces_detected,
            "total_matches": self.total_matches,
            "max_confidence": self.max_confidence,
            "min_confidence": self.min_confidence,
            "threshold_used": self.threshold_used,
            "raw_visage_output": self.raw_visage_output,
            "processing_time_ms": self.processing_time_ms,
            "processing_successful": self.processing_successful,
            "error_details": self.error_details,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def extract_metrics_from_raw_output(self):
        """Extract key metrics from raw Visage output for easier querying"""
        if not self.raw_visage_output:
            return
        
        try:
            output = self.raw_visage_output
            
            # Extract faces detected
            self.faces_detected = output.get("faces_detected", 0)
            
            # Extract match information
            face_matches = output.get("face_matches", [])
            self.total_matches = len(face_matches)
            
            # Extract confidence ranges
            if face_matches:
                confidences = [match.get("confidence", 0) for match in face_matches if match.get("confidence")]
                if confidences:
                    self.max_confidence = max(confidences)
                    self.min_confidence = min(confidences)
            
            # Extract processing info
            processing_info = output.get("processing_info", {})
            self.model_version = processing_info.get("model_version")
            if processing_info.get("processing_time_ms"):
                self.processing_time_ms = processing_info.get("processing_time_ms")
            
        except Exception as e:
            self.error_details = f"Error extracting metrics: {str(e)}"

# =============================================================================
# Query Helper Functions
# =============================================================================

def get_visage_results_by_job(db_session, job_id: str):
    """Get all Visage results for a specific job"""
    return db_session.query(VisageResult).filter(VisageResult.job_id == job_id).all()

def get_visage_results_by_task(db_session, task_id: str):
    """Get Visage result for a specific task"""
    return db_session.query(VisageResult).filter(VisageResult.task_id == task_id).first()

def get_visage_results_by_confidence_range(db_session, min_confidence: float = None, max_confidence: float = None):
    """Get Visage results within a confidence range"""
    query = db_session.query(VisageResult)
    
    if min_confidence is not None:
        query = query.filter(VisageResult.max_confidence >= min_confidence)
    if max_confidence is not None:
        query = query.filter(VisageResult.max_confidence <= max_confidence)
    
    return query.all()

def get_visage_results_with_faces(db_session, min_faces: int = 1):
    """Get Visage results that detected at least N faces"""
    return db_session.query(VisageResult).filter(VisageResult.faces_detected >= min_faces).all()