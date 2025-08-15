# =============================================================================
# Huey Tasks for StashAI Server
# =============================================================================

import logging
import sqlite3
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from Services.queue.huey_app import huey, DEFAULT_RETRY_CONFIG
from Database.database import get_db_session
from Database.models import UserInteraction, UserSession

# Import WebSocket broadcaster for real-time updates
try:
    from Services.websocket.broadcaster import queue_broadcaster
except ImportError:
    # Handle case where websocket module is not available  
    queue_broadcaster = None

logger = logging.getLogger(__name__)

# =============================================================================
# SQLite Retry Decorator for Database Lock Issues
# =============================================================================

def sqlite_retry(max_attempts=5):
    """Decorator to retry SQLite operations that fail due to database locks"""
    return retry(
        retry=retry_if_exception_type((sqlite3.OperationalError, sqlite3.DatabaseError)),
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=0.5, max=10),
        reraise=True,
        before_sleep=lambda retry_state: logger.warning(
            f"SQLite operation failed (attempt {retry_state.attempt_number}/{max_attempts}): {retry_state.outcome.exception()}"
        )
    )

# =============================================================================
# User Interaction Tasks
# =============================================================================

@huey.task(retries=DEFAULT_RETRY_CONFIG["retries"], retry_delay=DEFAULT_RETRY_CONFIG["retry_delay"])
@sqlite_retry(max_attempts=3)
def process_interaction_task(interaction_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process user interaction data asynchronously
    
    Args:
        interaction_data: Dictionary containing interaction information
        
    Returns:
        Dictionary with processing results
    """
    try:
        task_id = process_interaction_task.id if hasattr(process_interaction_task, 'id') else "unknown"
        logger.info(f"Processing interaction task {task_id}: {interaction_data.get('action_type', 'unknown')}")
        
        db = get_db_session()
        
        # Create interaction record
        interaction = UserInteraction(
            session_id=interaction_data.get("session_id"),
            user_id=interaction_data.get("user_id"),
            action_type=interaction_data.get("action_type"),
            page_path=interaction_data.get("page_path"),
            element_type=interaction_data.get("element_type"),
            element_id=interaction_data.get("element_id"),
            interaction_metadata=interaction_data.get("metadata", {})
        )
        
        db.add(interaction)
        db.commit()
        db.refresh(interaction)
        
        # Get values before closing session
        interaction_id = interaction.id
        session_id = interaction.session_id
        
        # Update session statistics
        session = db.query(UserSession).filter(
            UserSession.session_id == session_id
        ).first()
        
        if session:
            session.total_interactions += 1
            session.updated_at = datetime.now(timezone.utc)
            db.commit()
        
        db.close()
        
        result = {
            "task_id": task_id,
            "interaction_id": interaction_id,
            "session_id": session_id,
            "status": "completed",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Interaction task {task_id} completed successfully")
        
        # Broadcast task completion via WebSocket
        if queue_broadcaster:
            queue_broadcaster.broadcast_task_status_sync(
                task_id=task_id,
                status="completed",
                adapter_name="user_interactions",
                task_type="process_interaction",
                output_json=result
            )
        
        return result
        
    except Exception as e:
        logger.error(f"Error processing interaction task {task_id}: {str(e)}")
        # Huey will automatically retry based on task configuration
        raise e

# =============================================================================
# Session Management Tasks
# =============================================================================

@huey.task(retries=DEFAULT_RETRY_CONFIG["retries"], retry_delay=DEFAULT_RETRY_CONFIG["retry_delay"])
@sqlite_retry(max_attempts=3)
def process_session_update_task(session_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process session update asynchronously
    
    Args:
        session_data: Dictionary containing session information
        
    Returns:
        Dictionary with processing results
    """
    try:
        task_id = process_session_update_task.id if hasattr(process_session_update_task, 'id') else "unknown"
        logger.info(f"Processing session update task {task_id}")
        
        db = get_db_session()
        
        session = db.query(UserSession).filter(
            UserSession.session_id == session_data.get("session_id")
        ).first()
        
        if session:
            # Update existing session
            session.page_views = session_data.get("page_views", session.page_views)
            session.total_interactions = session_data.get("total_interactions", session.total_interactions)
            session.session_metadata = session_data.get("metadata", session.session_metadata)
            session.updated_at = datetime.now(timezone.utc)
            
            if session_data.get("end_time"):
                session.end_time = datetime.fromisoformat(session_data["end_time"])
            
            db.commit()
            db.refresh(session)
            status = "updated"
        else:
            # Create new session
            session = UserSession(
                session_id=session_data.get("session_id"),
                user_id=session_data.get("user_id"),
                page_views=session_data.get("page_views", 0),
                total_interactions=session_data.get("total_interactions", 0),
                session_metadata=session_data.get("metadata", {})
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            status = "created"
        
        db.close()
        
        result = {
            "task_id": task_id,
            "session_id": session.session_id,
            "status": status,
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Session update task {task_id} completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Error processing session update task {task_id}: {str(e)}")
        # Huey will automatically retry based on task configuration
        raise e

# =============================================================================
# Batch Processing Tasks
# =============================================================================

@huey.task(retries=DEFAULT_RETRY_CONFIG["retries"], retry_delay=DEFAULT_RETRY_CONFIG["retry_delay"])
@sqlite_retry(max_attempts=3)
def process_batch_task(batch_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process batch operations asynchronously
    
    Args:
        batch_data: Dictionary containing batch operation information
        
    Returns:
        Dictionary with processing results
    """
    try:
        task_id = process_batch_task.id if hasattr(process_batch_task, 'id') else "unknown"
        batch_type = batch_data.get("type", "unknown")
        items = batch_data.get("items", [])
        
        logger.info(f"Processing batch task {task_id}: {batch_type} with {len(items)} items")
        
        results = []
        processed_count = 0
        failed_count = 0
        
        for item in items:
            try:
                if batch_type == "interactions":
                    result = process_interaction_task(item)  # Huey tasks are called directly
                    results.append({"item_id": item.get("id"), "status": "completed", "result": result})
                elif batch_type == "sessions":
                    result = process_session_update_task(item)  # Huey tasks are called directly
                    results.append({"item_id": item.get("id"), "status": "completed", "result": result})
                else:
                    results.append({"item_id": item.get("id"), "status": "unsupported_type"})
                    failed_count += 1
                    continue
                
                processed_count += 1
                
            except Exception as e:
                logger.error(f"Error queuing batch item: {str(e)}")
                results.append({"item_id": item.get("id"), "status": "failed", "error": str(e)})
                failed_count += 1
        
        final_result = {
            "task_id": task_id,
            "batch_type": batch_type,
            "total_items": len(items),
            "processed": processed_count,
            "failed": failed_count,
            "results": results,
            "status": "completed",
            "processed_at": datetime.now(timezone.utc).isoformat()
        }
        
        logger.info(f"Batch task {task_id} completed: {processed_count}/{len(items)} items processed")
        return final_result
        
    except Exception as e:
        logger.error(f"Error processing batch task {task_id}: {str(e)}")
        # Huey will automatically retry based on task configuration
        raise e

# =============================================================================
# Monitoring and Health Tasks
# =============================================================================

@huey.task()
def queue_health_check_task() -> Dict[str, Any]:
    """
    Health check task for queue monitoring
    
    Returns:
        Dictionary with health status
    """
    try:
        task_id = queue_health_check_task.id if hasattr(queue_health_check_task, 'id') else "unknown"
        
        # Check database connectivity
        db = get_db_session()
        try:
            db.execute("SELECT 1")
            db_status = "healthy"
        except Exception as e:
            db_status = f"error: {str(e)}"
        finally:
            db.close()
        
        result = {
            "task_id": task_id,
            "queue_status": "healthy",
            "database_status": db_status,
            "worker_id": "huey_worker",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Health check task failed: {str(e)}")
        return {
            "task_id": queue_health_check_task.id if hasattr(queue_health_check_task, 'id') else "unknown",
            "queue_status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

# =============================================================================
# Import Service-specific tasks for registration
# =============================================================================

# Import all API tasks to ensure they are registered with Huey
try:
    from api.VisageFrontendAdapter import visage_face_identify_task, visage_batch_coordinator_task
    print("✅ Visage tasks imported successfully")
except ImportError as e:
    print(f"⚠️ Failed to import Visage tasks: {e}")

try:
    from api.ContentAnalysisFrontendAdapter import content_analysis_task
    print("✅ Content Analysis tasks imported successfully")
except ImportError as e:
    print(f"⚠️ Failed to import Content Analysis tasks: {e}")

try:
    from api.SceneAnalysisFrontendAdapter import scene_analysis_task
    print("✅ Scene Analysis tasks imported successfully")
except ImportError as e:
    print(f"⚠️ Failed to import Scene Analysis tasks: {e}")

try:
    from api.GeneralAIFrontendAdapter import general_ai_task
    print("✅ General AI tasks imported successfully")
except ImportError as e:
    print(f"⚠️ Failed to import General AI tasks: {e}")

# Service-specific tasks are now imported for registration
# This file contains both general-purpose and service-specific tasks

# =============================================================================
# External API Tasks (with retry logic)
# =============================================================================

@huey.task(retries=DEFAULT_RETRY_CONFIG["retries"], retry_delay=DEFAULT_RETRY_CONFIG["retry_delay"])
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=4, max=10))
def external_api_call_task(api_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Make external API calls with retry logic
    
    Args:
        api_data: Dictionary containing API call information
        
    Returns:
        Dictionary with API response
    """
    try:
        import httpx
        
        task_id = external_api_call_task.id if hasattr(external_api_call_task, 'id') else "unknown"
        url = api_data.get("url")
        method = api_data.get("method", "GET")
        headers = api_data.get("headers", {})
        payload = api_data.get("payload", {})
        
        logger.info(f"Making external API call {task_id}: {method} {url}")
        
        with httpx.Client(timeout=30.0) as client:
            if method.upper() == "GET":
                response = client.get(url, headers=headers, params=payload)
            elif method.upper() == "POST":
                response = client.post(url, headers=headers, json=payload)
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")
            
            response.raise_for_status()
            
            result = {
                "task_id": task_id,
                "status_code": response.status_code,
                "response": response.json() if response.headers.get("content-type", "").startswith("application/json") else response.text,
                "processed_at": datetime.now(timezone.utc).isoformat()
            }
            
            logger.info(f"External API call {task_id} completed successfully")
            return result
            
    except Exception as e:
        logger.error(f"External API call task {task_id} failed: {str(e)}")
        # Huey will automatically retry based on task configuration
        raise e