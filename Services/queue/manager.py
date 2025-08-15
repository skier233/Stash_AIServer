# =============================================================================
# Queue Manager for StashAI Server
# =============================================================================

import os
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone

from Services.queue.huey_app import huey
from Services.queue.processors import queue_processor

logger = logging.getLogger(__name__)

# =============================================================================
# Queue Manager Class
# =============================================================================

class QueueManager:
    """
    Main queue manager that integrates with the FastAPI application
    Provides both sync and async interfaces for queue operations
    """
    
    def __init__(self):
        self.processor = queue_processor
        self.app = huey
        self.is_enabled = os.getenv("QUEUE_ENABLED", "true").lower() == "true"
        self.direct_mode = os.getenv("DIRECT_MODE", "false").lower() == "true"
        self._healthy = False
        
        logger.info(f"Huey Queue Manager initialized - Enabled: {self.is_enabled}, Direct Mode: {self.direct_mode}")
    
    async def startup(self):
        """Initialize queue manager on application startup"""
        try:
            if not self.is_enabled:
                logger.info("Queue is disabled - running in direct mode")
                return
            
            logger.info("Starting Queue Manager...")
            
            # Test queue connectivity
            health_result = await self.async_health_check()
            if health_result.get("queue_healthy", False):
                self._healthy = True
                logger.info("✅ Queue Manager started successfully")
            else:
                logger.warning("⚠️ Queue Manager started but health check failed")
                if not self.direct_mode:
                    # Fall back to direct mode if queue is unhealthy
                    logger.info("Falling back to direct mode due to queue health issues")
                    self.direct_mode = True
                
        except Exception as e:
            logger.error(f"❌ Failed to start Queue Manager: {str(e)}")
            if not self.direct_mode:
                logger.info("Falling back to direct mode due to startup failure")
                self.direct_mode = True
    
    async def shutdown(self):
        """Cleanup queue manager on application shutdown"""
        logger.info("Shutting down Queue Manager...")
        try:
            if self.is_enabled and self._healthy:
                # Gracefully close any pending tasks
                await self.async_cancel_all_tasks()
            logger.info("✅ Queue Manager shutdown completed")
        except Exception as e:
            logger.error(f"Error during Queue Manager shutdown: {str(e)}")
    
    # =============================================================================
    # Async Interface (for FastAPI integration)
    # =============================================================================
    
    async def async_submit_interaction(self, interaction_data: Dict[str, Any], priority: int = 5) -> Dict[str, Any]:
        """Submit interaction processing task (async)"""
        if self.direct_mode or not self.is_enabled:
            return await self._direct_process_interaction(interaction_data)
        
        try:
            loop = asyncio.get_event_loop()
            task_id = await loop.run_in_executor(
                None, 
                self.processor.submit_interaction, 
                interaction_data, 
                priority
            )
            
            return {
                "task_id": task_id,
                "status": "queued",
                "mode": "queue",
                "submitted_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to submit interaction to queue: {str(e)}")
            # Fall back to direct processing
            logger.info("Falling back to direct processing")
            return await self._direct_process_interaction(interaction_data)
    
    async def async_submit_session_update(self, session_data: Dict[str, Any], priority: int = 5) -> Dict[str, Any]:
        """Submit session update task (async)"""
        if self.direct_mode or not self.is_enabled:
            return await self._direct_process_session(session_data)
        
        try:
            loop = asyncio.get_event_loop()
            task_id = await loop.run_in_executor(
                None, 
                self.processor.submit_session_update, 
                session_data, 
                priority
            )
            
            return {
                "task_id": task_id,
                "status": "queued",
                "mode": "queue",
                "submitted_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to submit session update to queue: {str(e)}")
            # Fall back to direct processing
            logger.info("Falling back to direct processing")
            return await self._direct_process_session(session_data)
    
    async def async_submit_batch(self, batch_data: Dict[str, Any], priority: int = 3) -> Dict[str, Any]:
        """Submit batch processing task (async)"""
        if self.direct_mode or not self.is_enabled:
            return await self._direct_process_batch(batch_data)
        
        try:
            loop = asyncio.get_event_loop()
            task_id = await loop.run_in_executor(
                None, 
                self.processor.submit_batch_processing, 
                batch_data, 
                priority
            )
            
            return {
                "task_id": task_id,
                "status": "queued",
                "mode": "queue",
                "submitted_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to submit batch to queue: {str(e)}")
            return {"error": str(e), "mode": "direct_fallback_failed"}
    
    async def async_get_task_status(self, task_id: str) -> Dict[str, Any]:
        """Get task status (async)"""
        if self.direct_mode or not self.is_enabled:
            return {"error": "Task status not available in direct mode", "mode": "direct"}
        
        try:
            loop = asyncio.get_event_loop()
            status = await loop.run_in_executor(
                None, 
                self.processor.get_task_status, 
                task_id
            )
            return status
            
        except Exception as e:
            logger.error(f"Failed to get task status: {str(e)}")
            return {"error": str(e), "task_id": task_id}
    
    async def async_health_check(self) -> Dict[str, Any]:
        """Perform health check (async)"""
        if not self.is_enabled:
            return {
                "queue_enabled": False,
                "mode": "direct",
                "healthy": True,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        
        try:
            loop = asyncio.get_event_loop()
            health = await loop.run_in_executor(None, self.processor.health_check)
            
            health.update({
                "queue_enabled": self.is_enabled,
                "direct_mode": self.direct_mode,
                "manager_healthy": self._healthy
            })
            
            return health
            
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            return {
                "queue_enabled": self.is_enabled,
                "queue_healthy": False,
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def async_get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics (async)"""
        if self.direct_mode or not self.is_enabled:
            return {"error": "Queue stats not available in direct mode", "mode": "direct"}
        
        try:
            loop = asyncio.get_event_loop()
            stats = await loop.run_in_executor(None, self.processor.get_queue_stats)
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get queue stats: {str(e)}")
            return {"error": str(e)}
    
    async def async_cancel_task(self, task_id: str) -> Dict[str, Any]:
        """Cancel a task (async)"""
        if self.direct_mode or not self.is_enabled:
            return {"error": "Task cancellation not available in direct mode", "mode": "direct"}
        
        try:
            loop = asyncio.get_event_loop()
            cancelled = await loop.run_in_executor(None, self.processor.cancel_task, task_id)
            
            return {
                "task_id": task_id,
                "cancelled": cancelled,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Failed to cancel task {task_id}: {str(e)}")
            return {"error": str(e), "task_id": task_id}
    
    async def async_cancel_all_tasks(self):
        """Cancel all pending tasks"""
        if self.direct_mode or not self.is_enabled:
            return
        
        try:
            # This is a cleanup operation during shutdown
            # Implementation depends on specific requirements
            logger.info("Cancelling all pending tasks...")
        except Exception as e:
            logger.error(f"Failed to cancel all tasks: {str(e)}")
    
    # =============================================================================
    # Direct Processing Fallback Methods
    # =============================================================================
    
    async def _direct_process_interaction(self, interaction_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process interaction directly without queue"""
        try:
            from Database.database import get_db_session
            from Database.models import UserInteraction, UserSession
            
            db = get_db_session()
            
            interaction = UserInteraction(
                session_id=interaction_data.get("session_id"),
                user_id=interaction_data.get("user_id"),
                action_type=interaction_data.get("action_type"),
                page_path=interaction_data.get("page_path"),
                element_type=interaction_data.get("element_type"),
                element_id=interaction_data.get("element_id"),
                metadata=interaction_data.get("metadata", {})
            )
            
            db.add(interaction)
            db.commit()
            db.refresh(interaction)
            db.close()
            
            return {
                "interaction_id": interaction.id,
                "status": "completed",
                "mode": "direct",
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Direct interaction processing failed: {str(e)}")
            return {"error": str(e), "mode": "direct"}
    
    async def _direct_process_session(self, session_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process session update directly without queue"""
        try:
            from Database.database import get_db_session
            from Database.models import UserSession
            
            db = get_db_session()
            
            session = db.query(UserSession).filter(
                UserSession.session_id == session_data.get("session_id")
            ).first()
            
            if session:
                session.page_views = session_data.get("page_views", session.page_views)
                session.total_interactions = session_data.get("total_interactions", session.total_interactions)
                session.metadata = session_data.get("metadata", session.metadata)
                session.updated_at = datetime.now(timezone.utc)
                status = "updated"
            else:
                session = UserSession(
                    session_id=session_data.get("session_id"),
                    user_id=session_data.get("user_id"),
                    page_views=session_data.get("page_views", 0),
                    total_interactions=session_data.get("total_interactions", 0),
                    metadata=session_data.get("metadata", {})
                )
                db.add(session)
                status = "created"
            
            db.commit()
            db.refresh(session)
            db.close()
            
            return {
                "session_id": session.session_id,
                "status": status,
                "mode": "direct",
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Direct session processing failed: {str(e)}")
            return {"error": str(e), "mode": "direct"}
    
    async def _direct_process_batch(self, batch_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process batch directly without queue"""
        # For now, return an error since batch processing should use the queue
        return {
            "error": "Batch processing not supported in direct mode",
            "mode": "direct",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# =============================================================================
# Global Queue Manager Instance
# =============================================================================

# Create global instance
queue_manager = QueueManager()