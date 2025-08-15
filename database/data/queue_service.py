# =============================================================================
# Queue Database Service - Manages Universal Tasks and Jobs
# =============================================================================
# 
# This service provides high-level operations for the normalized queue schema:
# - Task lifecycle management (create, update, query)
# - Job orchestration and batch operations
# - Cross-adapter queries and statistics
# - Database maintenance and cleanup
# =============================================================================

import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy import func, and_
from sqlalchemy.orm import Session

from Database.data.queue_models import QueueTask, QueueJob, TaskStatus, JobStatus
from Database.database import get_db_session

logger = logging.getLogger(__name__)

# =============================================================================
# Queue Database Service Class
# =============================================================================

class QueueDatabaseService:
    """
    High-level service for managing the normalized queue database
    
    Provides operations that work across all adapters while maintaining
    the normalized schema benefits of task-level granularity and
    job-level orchestration.
    """
    
    def __init__(self):
        pass
    
    # =========================================================================
    # Cross-Adapter Query Methods
    # =========================================================================
    
    def get_all_tasks(
        self, 
        adapter_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get tasks across all adapters with filtering
        
        Args:
            adapter_name: Filter by specific adapter
            status: Filter by task status
            limit: Maximum results to return
            offset: Results to skip
            
        Returns:
            List of task dictionaries
        """
        try:
            db = get_db_session()
            query = db.query(QueueTask)
            
            if adapter_name:
                query = query.filter(QueueTask.adapter_name == adapter_name)
            
            if status:
                query = query.filter(QueueTask.status == status)
            
            tasks = query.order_by(QueueTask.created_at.desc()).offset(offset).limit(limit).all()
            db.close()
            
            return [task.to_dict() for task in tasks]
            
        except Exception as e:
            logger.error(f"Failed to get tasks: {str(e)}")
            return []
    
    def get_all_jobs(
        self,
        adapter_name: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get jobs across all adapters with filtering
        
        Args:
            adapter_name: Filter by specific adapter
            status: Filter by job status
            limit: Maximum results to return
            offset: Results to skip
            
        Returns:
            List of job dictionaries
        """
        try:
            db = get_db_session()
            query = db.query(QueueJob)
            
            if adapter_name:
                query = query.filter(QueueJob.adapter_name == adapter_name)
            
            if status:
                query = query.filter(QueueJob.status == status)
            
            jobs = query.order_by(QueueJob.created_at.desc()).offset(offset).limit(limit).all()
            db.close()
            
            return [job.to_dict() for job in jobs]
            
        except Exception as e:
            logger.error(f"Failed to get jobs: {str(e)}")
            return []
    
    # =========================================================================
    # Statistics and Monitoring Methods
    # =========================================================================
    
    def get_queue_statistics(self) -> Dict[str, Any]:
        """
        Get comprehensive queue statistics across all adapters
        
        Returns:
            Dictionary with queue statistics
        """
        try:
            db = get_db_session()
            
            # Task statistics
            total_tasks = db.query(func.count(QueueTask.id)).scalar()
            pending_tasks = db.query(func.count(QueueTask.id)).filter(
                QueueTask.status == TaskStatus.PENDING.value
            ).scalar()
            running_tasks = db.query(func.count(QueueTask.id)).filter(
                QueueTask.status == TaskStatus.RUNNING.value
            ).scalar()
            finished_tasks = db.query(func.count(QueueTask.id)).filter(
                QueueTask.status == TaskStatus.FINISHED.value
            ).scalar()
            failed_tasks = db.query(func.count(QueueTask.id)).filter(
                QueueTask.status == TaskStatus.FAILED.value
            ).scalar()
            
            # Job statistics
            total_jobs = db.query(func.count(QueueJob.id)).scalar()
            active_jobs = db.query(func.count(QueueJob.id)).filter(
                QueueJob.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value])
            ).scalar()
            completed_jobs = db.query(func.count(QueueJob.id)).filter(
                QueueJob.status == JobStatus.COMPLETED.value
            ).scalar()
            
            # Adapter breakdown
            adapter_stats = db.query(
                QueueTask.adapter_name,
                func.count(QueueTask.id).label('task_count')
            ).group_by(QueueTask.adapter_name).all()
            
            db.close()
            
            return {
                "tasks": {
                    "total": total_tasks,
                    "pending": pending_tasks,
                    "running": running_tasks,
                    "finished": finished_tasks,
                    "failed": failed_tasks
                },
                "jobs": {
                    "total": total_jobs,
                    "active": active_jobs,
                    "completed": completed_jobs
                },
                "adapters": {
                    adapter: count for adapter, count in adapter_stats
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get queue statistics: {str(e)}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    def get_adapter_statistics(self, adapter_name: str) -> Dict[str, Any]:
        """
        Get statistics for a specific adapter
        
        Args:
            adapter_name: Name of the adapter (e.g., "visage")
            
        Returns:
            Dictionary with adapter-specific statistics
        """
        try:
            db = get_db_session()
            
            # Task statistics for this adapter
            total_tasks = db.query(func.count(QueueTask.id)).filter(
                QueueTask.adapter_name == adapter_name
            ).scalar()
            
            # Status breakdown
            status_stats = db.query(
                QueueTask.status,
                func.count(QueueTask.id).label('count')
            ).filter(
                QueueTask.adapter_name == adapter_name
            ).group_by(QueueTask.status).all()
            
            # Task type breakdown
            task_type_stats = db.query(
                QueueTask.task_type,
                func.count(QueueTask.id).label('count')
            ).filter(
                QueueTask.adapter_name == adapter_name
            ).group_by(QueueTask.task_type).all()
            
            # Average processing time
            avg_processing_time = db.query(
                func.avg(QueueTask.processing_time_ms)
            ).filter(
                and_(
                    QueueTask.adapter_name == adapter_name,
                    QueueTask.processing_time_ms.isnot(None)
                )
            ).scalar()
            
            # Job statistics for this adapter
            total_jobs = db.query(func.count(QueueJob.id)).filter(
                QueueJob.adapter_name == adapter_name
            ).scalar()
            
            active_jobs = db.query(func.count(QueueJob.id)).filter(
                and_(
                    QueueJob.adapter_name == adapter_name,
                    QueueJob.status.in_([JobStatus.PENDING.value, JobStatus.RUNNING.value])
                )
            ).scalar()
            
            db.close()
            
            return {
                "adapter_name": adapter_name,
                "tasks": {
                    "total": total_tasks,
                    "by_status": {status: count for status, count in status_stats},
                    "by_type": {task_type: count for task_type, count in task_type_stats},
                    "avg_processing_time_ms": float(avg_processing_time) if avg_processing_time else None
                },
                "jobs": {
                    "total": total_jobs,
                    "active": active_jobs
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to get adapter statistics for {adapter_name}: {str(e)}")
            return {
                "adapter_name": adapter_name,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    # =========================================================================
    # Database Maintenance Methods
    # =========================================================================
    
    def cleanup_old_tasks(self, days_old: int = 30) -> int:
        """
        Clean up old completed tasks
        
        Args:
            days_old: Remove tasks older than this many days
            
        Returns:
            Number of tasks deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            db = get_db_session()
            deleted_count = db.query(QueueTask).filter(
                and_(
                    QueueTask.finished_at < cutoff_date,
                    QueueTask.status.in_([TaskStatus.FINISHED.value, TaskStatus.FAILED.value])
                )
            ).delete(synchronize_session=False)
            
            db.commit()
            db.close()
            
            logger.info(f"Cleaned up {deleted_count} old tasks older than {days_old} days")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {str(e)}")
            return 0
    
    def cleanup_old_jobs(self, days_old: int = 30) -> int:
        """
        Clean up old completed jobs (and their associated tasks)
        
        Args:
            days_old: Remove jobs older than this many days
            
        Returns:
            Number of jobs deleted
        """
        try:
            cutoff_date = datetime.now(timezone.utc) - timedelta(days=days_old)
            
            db = get_db_session()
            
            # Find old jobs to delete
            old_jobs = db.query(QueueJob).filter(
                and_(
                    QueueJob.completed_at < cutoff_date,
                    QueueJob.status.in_([
                        JobStatus.COMPLETED.value, 
                        JobStatus.FAILED.value, 
                        JobStatus.PARTIAL.value
                    ])
                )
            ).all()
            
            deleted_jobs = 0
            deleted_tasks = 0
            
            for job in old_jobs:
                # Delete associated tasks first
                if job.task_ids:
                    task_delete_count = db.query(QueueTask).filter(
                        QueueTask.task_id.in_(job.task_ids)
                    ).delete(synchronize_session=False)
                    deleted_tasks += task_delete_count
                
                # Delete the job
                db.delete(job)
                deleted_jobs += 1
            
            db.commit()
            db.close()
            
            logger.info(f"Cleaned up {deleted_jobs} old jobs and {deleted_tasks} associated tasks")
            return deleted_jobs
            
        except Exception as e:
            logger.error(f"Failed to cleanup old jobs: {str(e)}")
            return 0
    
    # =========================================================================
    # Health Check Methods
    # =========================================================================
    
    def health_check(self) -> Dict[str, Any]:
        """
        Perform health check on queue database
        
        Returns:
            Dictionary with health status
        """
        try:
            db = get_db_session()
            
            # Test basic database connectivity
            task_count = db.query(func.count(QueueTask.id)).scalar()
            job_count = db.query(func.count(QueueJob.id)).scalar()
            
            # Check for stuck tasks (running for too long)
            stuck_threshold = datetime.now(timezone.utc) - timedelta(hours=2)
            stuck_tasks = db.query(func.count(QueueTask.id)).filter(
                and_(
                    QueueTask.status == TaskStatus.RUNNING.value,
                    QueueTask.started_at < stuck_threshold
                )
            ).scalar()
            
            db.close()
            
            return {
                "database_healthy": True,
                "total_tasks": task_count,
                "total_jobs": job_count,
                "stuck_tasks": stuck_tasks,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Queue database health check failed: {str(e)}")
            return {
                "database_healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

# =============================================================================
# Global Queue Service Instance
# =============================================================================

# Create global instance for use throughout the application
queue_service = QueueDatabaseService()