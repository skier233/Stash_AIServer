# =============================================================================
# WebSocket Queue Event Broadcaster
# =============================================================================

import logging
import asyncio
import httpx
from typing import Dict, Any, Optional
from datetime import datetime, timezone
from core.config import config

logger = logging.getLogger(__name__)

class QueueEventBroadcaster:
    """
    Handles broadcasting of queue events to WebSocket clients
    Acts as a bridge between the queue system and WebSocket manager
    """
    
    def __init__(self):
        self.websocket_manager = None
        self._loop = None
    
    def set_websocket_manager(self, manager):
        """Set the WebSocket manager instance"""
        self.websocket_manager = manager
        logger.info("WebSocket manager attached to queue broadcaster")
    
    def _try_get_websocket_manager(self):
        """Try to lazily get WebSocket manager from global state"""
        try:
            # Try to import and get the manager from main app state
            logger.info("Attempting to lazily load WebSocket manager...")
            
            # First try the main module approach
            try:
                from main import get_websocket_manager
                self.websocket_manager = get_websocket_manager()
                if self.websocket_manager:
                    logger.info(f"WebSocket manager lazily loaded from main: {self.websocket_manager}")
                    logger.info(f"Active connections: {len(self.websocket_manager.active_connections)}")
                    return
            except (ImportError, AttributeError) as e:
                logger.debug(f"Could not load from main: {e}")
            
            # Try to get it from a global registry if main approach fails
            try:
                import builtins
                if hasattr(builtins, '_websocket_manager_registry'):
                    self.websocket_manager = builtins._websocket_manager_registry
                    if self.websocket_manager:
                        logger.info(f"WebSocket manager loaded from global registry: {self.websocket_manager}")
                        logger.info(f"Active connections: {len(self.websocket_manager.active_connections)}")
                        return
            except Exception as e:
                logger.debug(f"Could not load from global registry: {e}")
            
            if not self.websocket_manager:
                logger.warning("WebSocket manager not found through any method")
                
        except Exception as e:
            logger.error(f"Unexpected error trying to load WebSocket manager: {e}")
    
    def _broadcast_via_http_callback(self, endpoint: str, payload: Dict[str, Any]):
        """
        Broadcast updates via HTTP POST to FastAPI internal endpoints
        This solves the cross-process issue between Huey workers and FastAPI
        """
        try:
            # Try Docker service name first (for containerized environments)
            # Then fallback to localhost for development
            possible_bases = [
                config.STASH_INTERNAL_BASE_URL,
                config.STASH_LOCAL_BASE_URL,
                config.STASH_LOOPBACK_BASE_URL,
            ]
            
            # Try each base URL until one works
            last_error = None
            for base_url in possible_bases:
                try:
                    full_url = f"{base_url}{endpoint}"
                    logger.debug(f"Attempting HTTP callback to {full_url}")
                    
                    # Make synchronous HTTP POST request using httpx
                    with httpx.Client(timeout=5.0) as client:
                        response = client.post(
                            full_url,
                            json=payload,
                            headers={"Content-Type": "application/json"}
                        )
                    
                    if response.status_code == 200:
                        logger.info(f"HTTP callback successful to {full_url}: {response.json()}")
                        return  # Success, exit early
                    else:
                        logger.warning(f"HTTP callback failed with status {response.status_code} to {full_url}: {response.text}")
                        last_error = f"HTTP {response.status_code}: {response.text}"
                        continue  # Try next URL
                        
                except httpx.RequestError as e:
                    logger.debug(f"Connection failed to {full_url}: {e}")
                    last_error = str(e)
                    continue  # Try next URL
            
            # If we get here, all URLs failed
            logger.error(f"Failed to send HTTP callback to {endpoint} - tried all addresses. Last error: {last_error}")
                
        except Exception as e:
            logger.error(f"Unexpected error in HTTP callback: {e}")
    
    def _ensure_event_loop(self):
        """Ensure we have an event loop for async operations"""
        try:
            self._loop = asyncio.get_event_loop()
        except RuntimeError:
            # If no loop exists, create a new one (for background tasks)
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
    
    def broadcast_task_status_sync(self, task_id: str, status: str, 
                                 adapter_name: str, task_type: str,
                                 output_json: Optional[Dict] = None,
                                 error_message: Optional[str] = None,
                                 processing_time_ms: Optional[float] = None):
        """
        Broadcast task status update via HTTP callback to FastAPI
        Called from task execution context (Huey workers)
        """
        logger.info(f"Broadcasting task status for {task_id}: {status}")
        
        # Use HTTP callback approach instead of direct WebSocket access
        self._broadcast_via_http_callback(
            endpoint="/internal/broadcast_task_status",
            payload={
                "task_id": task_id,
                "status": status,
                "adapter_name": adapter_name,
                "task_type": task_type,
                "output_json": output_json,
                "error_message": error_message,
                "processing_time_ms": processing_time_ms
            }
        )
    
    def broadcast_job_progress_sync(self, job_id: str, status: str, 
                                  adapter_name: str, job_type: str,
                                  total_tasks: int, completed_tasks: int, 
                                  failed_tasks: int, progress_percentage: float):
        """
        Broadcast job progress update via HTTP callback to FastAPI
        Called from job management context (Huey workers)
        """
        logger.info(f"Broadcasting job progress for {job_id}: {status} ({completed_tasks}/{total_tasks})")
        
        # Use HTTP callback approach instead of direct WebSocket access
        self._broadcast_via_http_callback(
            endpoint="/internal/broadcast_job_progress",
            payload={
                "job_id": job_id,
                "status": status,
                "adapter_name": adapter_name,
                "job_type": job_type,
                "total_tasks": total_tasks,
                "completed_tasks": completed_tasks,
                "failed_tasks": failed_tasks,
                "progress_percentage": progress_percentage
            }
        )
    
    def broadcast_queue_stats_sync(self, stats: Dict[str, Any]):
        """
        Broadcast queue statistics (synchronous wrapper)
        """
        if not self.websocket_manager:
            return
        
        try:
            self._ensure_event_loop()
            if self._loop.is_running():
                # If loop is running, schedule the coroutine
                asyncio.create_task(
                    self.websocket_manager.broadcast_queue_stats(stats)
                )
            else:
                # If loop is not running, run it
                self._loop.run_until_complete(
                    self.websocket_manager.broadcast_queue_stats(stats)
                )
        except Exception as e:
            logger.error(f"Failed to broadcast queue stats: {e}")

# =============================================================================
# Global Broadcaster Instance
# =============================================================================

# Create global instance for use throughout the application
queue_broadcaster = QueueEventBroadcaster()