# =============================================================================
# Visage Database Adapter - Uses Normalized Queue Schema
# =============================================================================
# 
# This adapter demonstrates how to integrate the Visage service with the
# normalized queue database schema using QueueTask and QueueJob tables.
# 
# ADAPTER PATTERN:
# 1. Uses universal QueueTask table for task tracking
# 2. Uses universal QueueJob table for batch orchestration
# 3. Service-specific logic in helper classes and task processors
# 4. Clean separation between queue management and business logic
# =============================================================================

import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from Database.data.queue_models import QueueTask, QueueJob, TaskStatus, JobStatus
from Database.data.visage_results_models import VisageResult
from Database.database import get_db_session

# Import WebSocket broadcaster for real-time updates
try:
    from Services.websocket.broadcaster import queue_broadcaster
except ImportError:
    # Handle case where websocket module is not available
    queue_broadcaster = None

logger = logging.getLogger(__name__)

# =============================================================================
# Visage-Specific Configuration
# =============================================================================

class VisageTaskTypes:
    """Visage-specific task type constants"""
    FACE_IDENTIFY = "visage_face_identify"
    FACE_COMPARE = "visage_face_compare"
    FACE_SEARCH = "visage_face_search"
    BATCH_FACE_IDENTIFY = "visage_batch_face_identify"
    BATCH_FACE_COMPARE = "visage_batch_face_compare"

class VisageJobTypes:
    """Visage-specific job type constants"""
    SINGLE_FACE_IDENTIFICATION = "visage_single_face_identification"
    BULK_FACE_IDENTIFICATION = "visage_bulk_face_identification"
    BULK_FACE_COMPARISON = "visage_bulk_face_comparison"
    PERFORMER_ANALYSIS_BATCH = "visage_performer_analysis_batch"

# =============================================================================
# Visage Database Adapter
# =============================================================================

class VisageDatabaseAdapter:
    """
    Database adapter for Visage service using normalized queue schema
    
    This adapter manages Visage tasks and jobs using the universal
    QueueTask and QueueJob tables, providing Visage-specific functionality
    while maintaining schema consistency.
    """
    
    ADAPTER_NAME = "visage"
    
    def __init__(self):
        self.adapter_name = self.ADAPTER_NAME
        
    # =========================================================================
    # Task Management Methods
    # =========================================================================
    
    def create_task(
        self, 
        task_type: str,
        input_data: Dict[str, Any],
        job_id: Optional[str] = None,
        priority: int = 5
    ) -> str:
        """
        Create a new Visage task in the universal tasks table
        
        Args:
            task_type: Visage task type (from VisageTaskTypes)
            input_data: Task input parameters (image data, thresholds, etc.)
            job_id: Optional job ID if part of batch operation
            priority: Task priority (0-9, higher is more priority)
            
        Returns:
            Generated task_id
        """
        try:
            task_id = str(uuid.uuid4())
            
            db = get_db_session()
            task = QueueTask(
                task_id=task_id,
                adapter_name=self.adapter_name,
                task_type=task_type,
                status=TaskStatus.PENDING.value,
                priority=priority,
                input_data=input_data,
                job_id=job_id
            )
            
            db.add(task)
            db.commit()
            db.refresh(task)
            db.close()
            
            logger.info(f"Created Visage task {task_id} of type {task_type}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to create Visage task: {str(e)}")
            raise
    
    def update_task_status(
        self, 
        task_id: str, 
        status: str,
        output_json: Optional[Dict[str, Any]] = None,
        error_message: Optional[str] = None,
        processing_time_ms: Optional[float] = None
    ) -> bool:
        """
        Update task status and results
        
        Args:
            task_id: Task ID to update
            status: New status (from TaskStatus enum)
            output_json: Task results/output data
            error_message: Error message if task failed
            processing_time_ms: Task execution time
            
        Returns:
            True if updated successfully
        """
        try:
            db = get_db_session()
            task = db.query(QueueTask).filter(
                QueueTask.task_id == task_id,
                QueueTask.adapter_name == self.adapter_name
            ).first()
            
            if not task:
                logger.error(f"Visage task {task_id} not found")
                return False
            
            # Update task fields
            task.status = status
            task.updated_at = datetime.now(timezone.utc)
            
            if output_json is not None:
                task.output_json = output_json
            
            if error_message is not None:
                task.error_message = error_message
            
            if processing_time_ms is not None:
                task.processing_time_ms = processing_time_ms
            
            # Set timestamps based on status
            if status == TaskStatus.RUNNING.value and not task.started_at:
                task.started_at = datetime.now(timezone.utc)
            elif status in [TaskStatus.FINISHED.value, TaskStatus.FAILED.value]:
                task.finished_at = datetime.now(timezone.utc)
            
            # Capture task properties before committing/closing session
            task_type = task.task_type
            job_id = task.job_id
            input_data = task.input_data
            
            db.commit()
            db.close()
            
            logger.info(f"Updated Visage task {task_id} to status {status}")
            
            # Simple debugging log to check if this is being called for completion
            if status in [TaskStatus.FINISHED.value, TaskStatus.FAILED.value]:
                logger.info(f"Task {task_id} completed with status {status} - attempting WebSocket broadcast")
            
            # Broadcast task status update via WebSocket
            # NOTE: Since Huey workers run in separate processes, direct WebSocket broadcasting
            # won't work. Instead, we'll use a simple HTTP callback to notify the main process.
            try:
                import httpx
                # Send a simple HTTP request to the main server to trigger WebSocket broadcast
                # Try multiple possible URLs (Docker container, localhost, etc.)
                possible_urls = [
                    "http://stash-ai-server:9998/internal/broadcast_task_status",  # Docker service name
                    "http://127.0.0.1:9998/internal/broadcast_task_status",       # Local loopback
                    "http://localhost:9998/internal/broadcast_task_status"        # Localhost fallback
                ]
                broadcast_data = {
                    "task_id": task_id,
                    "status": status,
                    "adapter_name": self.adapter_name,
                    "task_type": task_type,
                    "output_json": output_json,
                    "error_message": error_message,
                    "processing_time_ms": processing_time_ms
                }
                
                # Try multiple URLs until one works
                success = False
                with httpx.Client(timeout=2.0) as client:
                    for callback_url in possible_urls:
                        try:
                            response = client.post(callback_url, json=broadcast_data)
                            if response.status_code == 200:
                                logger.info(f"WebSocket broadcast callback sent successfully for task {task_id} via {callback_url}")
                                success = True
                                break
                            else:
                                logger.debug(f"WebSocket broadcast callback failed with status {response.status_code} for {callback_url}")
                        except httpx.RequestError as e:
                            logger.debug(f"WebSocket broadcast callback request failed for {callback_url}: {e}")
                    
                    if not success:
                        logger.warning(f"All WebSocket broadcast callback attempts failed for task {task_id}")
            except Exception as e:
                logger.warning(f"Failed to send WebSocket broadcast callback: {e}")
                
            # Keep the original broadcaster code as fallback (though it won't work in worker processes)
            if queue_broadcaster:
                queue_broadcaster.broadcast_task_status_sync(
                    task_id=task_id,
                    status=status,
                    adapter_name=self.adapter_name,
                    task_type=task_type,
                    output_json=output_json,
                    error_message=error_message,
                    processing_time_ms=processing_time_ms
                )
            
            # Store results in Visage-specific table if task completed successfully
            if status == TaskStatus.FINISHED.value and output_json is not None:
                self._store_visage_result(
                    task_id=task_id,
                    job_id=job_id,
                    raw_output=output_json,
                    processing_time_ms=processing_time_ms,
                    input_data=input_data
                )
            
            # Update associated job progress if this task belongs to a job
            if job_id:
                self._update_job_progress(job_id)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to update Visage task {task_id}: {str(e)}")
            return False
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task details by task ID"""
        try:
            db = get_db_session()
            task = db.query(QueueTask).filter(
                QueueTask.task_id == task_id,
                QueueTask.adapter_name == self.adapter_name
            ).first()
            db.close()
            
            return task.to_dict() if task else None
            
        except Exception as e:
            logger.error(f"Failed to get Visage task {task_id}: {str(e)}")
            return None
    
    # =========================================================================
    # Job Management Methods
    # =========================================================================
    
    def create_job(
        self,
        job_type: str,
        job_name: Optional[str] = None,
        job_config: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None
    ) -> str:
        """
        Create a new Visage batch job
        
        Args:
            job_type: Job type (from VisageJobTypes)
            job_name: Human-readable job name
            job_config: Job-specific configuration
            user_id: Optional user ID
            session_id: Optional session ID
            
        Returns:
            Generated job_id
        """
        try:
            job_id = str(uuid.uuid4())
            
            db = get_db_session()
            job = QueueJob(
                job_id=job_id,
                adapter_name=self.adapter_name,
                job_type=job_type,
                job_name=job_name or f"Visage {job_type}",
                status=JobStatus.PENDING.value,
                job_config=job_config or {},
                user_id=user_id,
                session_id=session_id
            )
            
            db.add(job)
            db.commit()
            db.refresh(job)
            db.close()
            
            logger.info(f"Created Visage job {job_id} of type {job_type}")
            return job_id
            
        except Exception as e:
            logger.error(f"Failed to create Visage job: {str(e)}")
            raise
    
    def add_tasks_to_job(self, job_id: str, task_ids: List[str]) -> bool:
        """
        Associate tasks with a job and update job metadata
        
        Args:
            job_id: Job ID
            task_ids: List of task IDs to associate with job
            
        Returns:
            True if updated successfully
        """
        try:
            db = get_db_session()
            job = db.query(QueueJob).filter(
                QueueJob.job_id == job_id,
                QueueJob.adapter_name == self.adapter_name
            ).first()
            
            if not job:
                logger.error(f"Visage job {job_id} not found")
                return False
            
            # Update job task tracking
            current_task_ids = job.task_ids or []
            updated_task_ids = list(set(current_task_ids + task_ids))
            
            job.task_ids = updated_task_ids
            job.total_tasks = len(updated_task_ids)
            job.updated_at = datetime.now(timezone.utc)
            
            # Update associated tasks with job_id
            db.query(QueueTask).filter(
                QueueTask.task_id.in_(task_ids),
                QueueTask.adapter_name == self.adapter_name
            ).update({"job_id": job_id}, synchronize_session=False)
            
            db.commit()
            db.close()
            
            logger.info(f"Added {len(task_ids)} tasks to Visage job {job_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add tasks to Visage job {job_id}: {str(e)}")
            return False
    
    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details by job ID"""
        try:
            db = get_db_session()
            job = db.query(QueueJob).filter(
                QueueJob.job_id == job_id,
                QueueJob.adapter_name == self.adapter_name
            ).first()
            db.close()
            
            return job.to_dict() if job else None
            
        except Exception as e:
            logger.error(f"Failed to get Visage job {job_id}: {str(e)}")
            return None
    
    def get_job_tasks(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all tasks associated with a job"""
        try:
            db = get_db_session()
            tasks = db.query(QueueTask).filter(
                QueueTask.job_id == job_id,
                QueueTask.adapter_name == self.adapter_name
            ).all()
            db.close()
            
            return [task.to_dict() for task in tasks]
            
        except Exception as e:
            logger.error(f"Failed to get tasks for Visage job {job_id}: {str(e)}")
            return []
    
    # =========================================================================
    # Visage Results Storage Methods
    # =========================================================================
    
    def _store_visage_result(
        self,
        task_id: str,
        job_id: Optional[str],
        raw_output: Dict[str, Any],
        processing_time_ms: Optional[float] = None,
        input_data: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        Store Visage-specific results in the visage_results table
        
        Args:
            task_id: Task ID from queue_tasks
            job_id: Job ID from queue_jobs (if part of batch)
            raw_output: Raw JSON response from Visage API
            processing_time_ms: Task execution time
            input_data: Original task input data
            
        Returns:
            result_id if successful, None if failed
        """
        try:
            result_id = str(uuid.uuid4())
            
            db = get_db_session()
            
            # Create Visage result record
            visage_result = VisageResult(
                result_id=result_id,
                task_id=task_id,
                job_id=job_id,
                raw_visage_output=raw_output,
                processing_time_ms=processing_time_ms
            )
            
            # Extract metadata from input data if available
            if input_data:
                visage_result.visage_api_url = input_data.get("visage_api_url")
                visage_result.threshold_used = input_data.get("threshold")
                
                # Store image metadata (not the actual image data for space efficiency)
                image_info = {}
                if "image" in input_data:
                    # Just store metadata about the image, not the full base64
                    image_data = input_data["image"]
                    if isinstance(image_data, str):
                        image_info["image_type"] = "base64_string"
                        image_info["image_size_chars"] = len(image_data)
                    else:
                        image_info["image_type"] = "other"
                
                if input_data.get("additional_params"):
                    image_info.update(input_data["additional_params"])
                
                visage_result.input_image_info = image_info
            
            # Extract metrics from raw output for easier querying
            visage_result.extract_metrics_from_raw_output()
            visage_result.processing_successful = "true"
            
            db.add(visage_result)
            db.commit()
            db.refresh(visage_result)
            db.close()
            
            logger.info(f"Stored Visage result {result_id} for task {task_id}")
            return result_id
            
        except Exception as e:
            logger.error(f"Failed to store Visage result for task {task_id}: {str(e)}")
            return None
    
    def get_job_results(self, job_id: str) -> List[Dict[str, Any]]:
        """Get all Visage results for a specific job"""
        try:
            from Database.data.visage_results_models import get_visage_results_by_job
            
            db = get_db_session()
            results = get_visage_results_by_job(db, job_id)
            db.close()
            
            return [result.to_dict() for result in results]
            
        except Exception as e:
            logger.error(f"Failed to get Visage results for job {job_id}: {str(e)}")
            return []
    
    def get_task_result(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get Visage result for a specific task"""
        try:
            from Database.data.visage_results_models import get_visage_results_by_task
            
            db = get_db_session()
            result = get_visage_results_by_task(db, task_id)
            db.close()
            
            return result.to_dict() if result else None
            
        except Exception as e:
            logger.error(f"Failed to get Visage result for task {task_id}: {str(e)}")
            return None

    # =========================================================================
    # Private Helper Methods
    # =========================================================================
    
    def _update_job_progress(self, job_id: str) -> None:
        """Update job progress based on associated task statuses"""
        try:
            db = get_db_session()
            
            # Get job
            job = db.query(QueueJob).filter(
                QueueJob.job_id == job_id,
                QueueJob.adapter_name == self.adapter_name
            ).first()
            
            if not job:
                return
            
            # Count task statuses
            tasks = db.query(QueueTask).filter(
                QueueTask.job_id == job_id,
                QueueTask.adapter_name == self.adapter_name
            ).all()
            
            total_tasks = len(tasks)
            completed_tasks = len([t for t in tasks if t.status == TaskStatus.FINISHED.value])
            failed_tasks = len([t for t in tasks if t.status == TaskStatus.FAILED.value])
            
            # Update job status and progress
            job.total_tasks = total_tasks
            job.completed_tasks = completed_tasks
            job.failed_tasks = failed_tasks
            job.update_progress()
            job.updated_at = datetime.now(timezone.utc)
            
            # Update job status based on task completion
            if completed_tasks == total_tasks and total_tasks > 0:
                job.status = JobStatus.COMPLETED.value
                if not job.completed_at:
                    job.completed_at = datetime.now(timezone.utc)
            elif failed_tasks > 0 and (completed_tasks + failed_tasks) == total_tasks:
                job.status = JobStatus.PARTIAL.value if completed_tasks > 0 else JobStatus.FAILED.value
                if not job.completed_at:
                    job.completed_at = datetime.now(timezone.utc)
            elif completed_tasks > 0 or failed_tasks > 0:
                job.status = JobStatus.RUNNING.value
                if not job.started_at:
                    job.started_at = datetime.now(timezone.utc)
            
            # Capture job properties before committing/closing session
            job_status = job.status
            job_type = job.job_type
            progress_percentage = job.progress_percentage
            
            db.commit()
            db.close()
            
            # Broadcast job progress update via WebSocket
            if queue_broadcaster:
                queue_broadcaster.broadcast_job_progress_sync(
                    job_id=job_id,
                    status=job_status,
                    adapter_name=self.adapter_name,
                    job_type=job_type,
                    total_tasks=total_tasks,
                    completed_tasks=completed_tasks,
                    failed_tasks=failed_tasks,
                    progress_percentage=progress_percentage
                )
            
        except Exception as e:
            logger.error(f"Failed to update job progress for {job_id}: {str(e)}")

# =============================================================================
# Global Visage Adapter Instance
# =============================================================================

# Create global instance for use throughout the application
visage_adapter = VisageDatabaseAdapter()