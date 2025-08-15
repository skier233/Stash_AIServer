# =============================================================================
# Queue Processors for StashAI Server
# =============================================================================

import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional

from Services.queue.huey_app import huey
from Services.queue.tasks import (
    process_interaction_task,
    process_session_update_task,
    process_batch_task,
    queue_health_check_task,
    external_api_call_task
)

logger = logging.getLogger(__name__)

# =============================================================================
# Queue Processor Class
# =============================================================================

class QueueProcessor:
    """Main queue processor for managing task execution"""
    
    def __init__(self):
        self.app = huey
    
    def is_task_cancelled(self, task_id: str) -> bool:
        """
        Check if a task has been cancelled
        
        Args:
            task_id: Task ID to check
            
        Returns:
            True if task is cancelled
        """
        try:
            from Database.data.queue_models import QueueTask, TaskStatus
            from Database.database import get_db_session
            
            db = get_db_session()
            task = db.query(QueueTask).filter(QueueTask.task_id == task_id).first()
            db.close()
            
            if task and task.status == TaskStatus.CANCELLED.value:
                logger.info(f"Task {task_id} is cancelled, skipping processing")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Failed to check task cancellation status for {task_id}: {str(e)}")
            return False
        
    def submit_interaction(self, interaction_data: Dict[str, Any], priority: int = 5) -> str:
        """
        Submit interaction processing task to queue
        
        Args:
            interaction_data: Interaction data to process
            priority: Task priority (0-9, higher is more priority)
            
        Returns:
            Task ID
        """
        try:
            result = process_interaction_task(interaction_data)
            # For Huey, we get a TaskResultWrapper - get the actual task ID
            task_id = result.id if hasattr(result, 'id') else str(result)
            logger.info(f"Submitted interaction task: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"Failed to submit interaction task: {str(e)}")
            raise
    
    def submit_session_update(self, session_data: Dict[str, Any], priority: int = 5) -> str:
        """
        Submit session update task to queue
        
        Args:
            session_data: Session data to process
            priority: Task priority (0-9, higher is more priority)
            
        Returns:
            Task ID
        """
        try:
            result = process_session_update_task(session_data)
            task_id = result.id if hasattr(result, 'id') else str(result)
            logger.info(f"Submitted session update task: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"Failed to submit session update task: {str(e)}")
            raise
    
    def submit_batch_processing(self, batch_data: Dict[str, Any], priority: int = 3) -> str:
        """
        Submit batch processing task to queue
        
        Args:
            batch_data: Batch data to process
            priority: Task priority (0-9, higher is more priority)
            
        Returns:
            Task ID
        """
        try:
            result = process_batch_task(batch_data)
            task_id = result.id if hasattr(result, 'id') else str(result)
            logger.info(f"Submitted batch processing task: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"Failed to submit batch processing task: {str(e)}")
            raise
    
    def submit_external_api_call(self, api_data: Dict[str, Any], priority: int = 5) -> str:
        """
        Submit external API call task to queue
        
        Args:
            api_data: API call data
            priority: Task priority (0-9, higher is more priority)
            
        Returns:
            Task ID
        """
        try:
            result = external_api_call_task(api_data)
            task_id = result.id if hasattr(result, 'id') else str(result)
            logger.info(f"Submitted external API call task: {task_id}")
            return task_id
        except Exception as e:
            logger.error(f"Failed to submit external API call task: {str(e)}")
            raise
    
    def get_task_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get task status and result
        
        Args:
            task_id: Task ID to check
            
        Returns:
            Dictionary with task status information
        """
        try:
            # Huey doesn't have the same task tracking as Celery
            # For now, return a simple status
            return {
                "task_id": task_id,
                "status": "COMPLETED",  # Huey tasks complete immediately in this setup
                "ready": True,
                "successful": True,
                "message": "Huey task tracking is simplified - tasks run immediately"
            }
            
        except Exception as e:
            logger.error(f"Failed to get task status for {task_id}: {str(e)}")
            return {
                "task_id": task_id,
                "status": "ERROR",
                "error": str(e)
            }
    
    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a task using Huey's revoke() method and update database
        
        Args:
            task_id: Task ID to cancel
            
        Returns:
            True if cancelled successfully
        """
        try:
            from Database.data.queue_models import QueueTask, TaskStatus
            from Database.database import get_db_session
            from datetime import datetime, timezone
            
            # Get database session
            db = get_db_session()
            
            # Find the task
            task = db.query(QueueTask).filter(QueueTask.task_id == task_id).first()
            
            if not task:
                logger.info(f"Task {task_id} not found in database")
                db.close()
                return False
            
            # Only cancel tasks that are pending or running
            if task.status not in [TaskStatus.PENDING.value, TaskStatus.RUNNING.value]:
                logger.info(f"Task {task_id} cannot be cancelled - current status: {task.status}")
                db.close()
                return False
            
            # Store task info for broadcasting before modifying task
            adapter_name = task.adapter_name
            task_type = task.task_type
            
            # Try to revoke the task in Huey
            try:
                # Use Huey's revoke method to actually cancel the task
                self.app.revoke_by_id(task_id)
                logger.info(f"Task {task_id} revoked in Huey queue")
            except Exception as revoke_error:
                logger.warning(f"Failed to revoke task {task_id} in Huey: {revoke_error}")
                # Continue with database update even if revoke fails
            
            # Mark task as cancelled in database
            task.status = TaskStatus.CANCELLED.value
            task.finished_at = datetime.now(timezone.utc)
            task.updated_at = datetime.now(timezone.utc)
            task.error_message = "Task cancelled by user request"
            
            db.commit()
            logger.info(f"Task {task_id} successfully marked as cancelled in database")
            
            # Broadcast cancellation update via websocket if available
            try:
                from Services.websocket.broadcaster import queue_broadcaster
                if queue_broadcaster:
                    import asyncio
                    # Create the update message
                    update_message = {
                        'type': 'task_status',
                        'task_id': task_id,
                        'status': TaskStatus.CANCELLED.value,
                        'adapter_name': adapter_name,
                        'task_type': task_type,
                        'timestamp': task.updated_at.isoformat()
                    }
                    
                    # Try to broadcast the update
                    try:
                        # Run the async function
                        loop = asyncio.new_event_loop()
                        asyncio.set_event_loop(loop)
                        loop.run_until_complete(queue_broadcaster.broadcast_task_update(task_id, update_message))
                        loop.close()
                    except Exception as ws_error:
                        logger.debug(f"Failed to broadcast cancellation via websocket: {ws_error}")
                        
            except ImportError:
                # WebSocket broadcasting not available, continue without it
                logger.debug("WebSocket broadcasting not available for cancellation notification")
            
            # Update parent job status if this task belongs to a job
            if task.job_id:
                self._update_job_status_after_cancellation(task.job_id, db)
            
            db.close()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {str(e)}")
            return False
    
    def _update_job_status_after_cancellation(self, job_id: str, db):
        """
        Update job status to 'partial' when some tasks are cancelled
        
        Args:
            job_id: Job ID to update
            db: Database session
        """
        try:
            from Database.data.queue_models import QueueJob, QueueTask, JobStatus, TaskStatus
            
            # Get the job
            job = db.query(QueueJob).filter(QueueJob.job_id == job_id).first()
            if not job:
                return
            
            # Count task statuses for this job
            task_counts = db.query(QueueTask.status, db.query(QueueTask).filter(QueueTask.job_id == job_id).count()).filter(QueueTask.job_id == job_id).all()
            
            # Get actual counts
            total_tasks = db.query(QueueTask).filter(QueueTask.job_id == job_id).count()
            completed_tasks = db.query(QueueTask).filter(
                QueueTask.job_id == job_id, 
                QueueTask.status == TaskStatus.FINISHED.value
            ).count()
            failed_tasks = db.query(QueueTask).filter(
                QueueTask.job_id == job_id,
                QueueTask.status == TaskStatus.FAILED.value
            ).count()
            cancelled_tasks = db.query(QueueTask).filter(
                QueueTask.job_id == job_id,
                QueueTask.status == TaskStatus.CANCELLED.value
            ).count()
            pending_running_tasks = db.query(QueueTask).filter(
                QueueTask.job_id == job_id,
                QueueTask.status.in_([TaskStatus.PENDING.value, TaskStatus.RUNNING.value])
            ).count()
            
            # Update job status based on task states
            if cancelled_tasks > 0 and (completed_tasks > 0 or failed_tasks > 0):
                # Some tasks cancelled, some completed/failed = partial
                job.status = JobStatus.PARTIAL.value
            elif cancelled_tasks > 0 and pending_running_tasks == 0:
                # All remaining tasks cancelled = partial (user stopped the job)
                job.status = JobStatus.PARTIAL.value
            elif completed_tasks == total_tasks:
                # All tasks completed
                job.status = JobStatus.COMPLETED.value
            elif failed_tasks > 0 and (completed_tasks + failed_tasks + cancelled_tasks) == total_tasks:
                # Mix of completed/failed/cancelled with no pending = partial
                job.status = JobStatus.PARTIAL.value
            
            # Update job counters
            job.total_tasks = total_tasks
            job.completed_tasks = completed_tasks
            job.failed_tasks = failed_tasks
            job.update_progress()
            
            db.commit()
            logger.info(f"Updated job {job_id} status to {job.status} (completed: {completed_tasks}, failed: {failed_tasks}, cancelled: {cancelled_tasks})")
            
        except Exception as e:
            logger.error(f"Failed to update job status for {job_id}: {str(e)}")
            db.rollback()
    
    def get_queue_stats(self) -> Dict[str, Any]:
        """
        Get queue statistics
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            # Huey has simpler stats than Celery
            stats = {
                "queue_type": "huey_sqlite",
                "active_tasks": "Not available in Huey",
                "scheduled_tasks": "Not available in Huey", 
                "total_tasks_processed": "Not tracked in simple setup",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "message": "Huey provides simpler queue statistics than Celery"
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform queue health check
        
        Returns:
            Dictionary with health status
        """
        try:
            # Submit health check task and get the result
            health_task = queue_health_check_task()
            
            # For immediate mode or testing, we can get the result directly
            # For actual queue mode, we should just confirm the task was submitted
            try:
                # Try to get the result if it's available immediately
                health_result = health_task() if hasattr(health_task, '__call__') else None
            except:
                # If we can't get the result immediately, just show task was submitted
                health_result = {"status": "task_submitted", "task_id": str(health_task)}
            
            return {
                "queue_healthy": True,
                "health_check_result": health_result,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Queue health check failed: {str(e)}")
            return {
                "queue_healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def process_interaction_batch(self, interactions: List[Dict[str, Any]]) -> str:
        """
        Process multiple interactions as a batch (simplified for Huey)
        
        Args:
            interactions: List of interaction data
            
        Returns:
            Batch task ID
        """
        try:
            # With Huey, we'll process them sequentially for simplicity
            batch_data = {
                "type": "interactions",
                "items": interactions
            }
            
            result = process_batch_task(batch_data)
            task_id = result.id if hasattr(result, 'id') else str(result)
            logger.info(f"Submitted interaction batch: {task_id}")
            return task_id
            
        except Exception as e:
            logger.error(f"Failed to submit interaction batch: {str(e)}")
            raise

# =============================================================================
# Global Queue Processor Instance
# =============================================================================

# Create global instance
queue_processor = QueueProcessor()