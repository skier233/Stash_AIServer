# =============================================================================
# API Endpoints for StashAI Server
# =============================================================================

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, HTTPException, Request
from core.config import config as app_config
from Database.database import get_db_session
from Database.models import UserInteraction, UserSession

logger = logging.getLogger(__name__)

# Create API router
router = APIRouter()

# Import websocket manager and queue manager (will be injected from main.py)
websocket_manager = None
queue_manager = None

def set_websocket_manager(manager):
    """Set the websocket manager instance"""
    global websocket_manager
    websocket_manager = manager

def set_queue_manager(manager):
    """Set the queue manager instance"""
    global queue_manager
    queue_manager = manager

# =============================================================================
# Health and Root Endpoints
# =============================================================================

@router.get("/", tags=["Core"], summary="Service Status")
async def root():
    """Get basic service status"""
    return {"message": "StashAI Server is running", "status": "healthy"}

@router.get("/health", tags=["Core"], summary="Comprehensive Health Check")
async def health_check():
    # Include queue health in overall health check
    health_data = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "database": "connected",
        "version": "1.0.0"
    }
    
    # Add queue health if queue manager is available
    if queue_manager:
        try:
            queue_health = await queue_manager.async_health_check()
            health_data["queue"] = queue_health
        except Exception as e:
            health_data["queue"] = {"error": str(e), "status": "unhealthy"}
    
    return health_data

# =============================================================================
# Interaction Endpoints
# =============================================================================

@router.post("/api/interactions", tags=["Interactions"], summary="Create User Interaction")  
async def create_interaction(request: Request):
    """
    Create a new user interaction record using queue processing
    
    Processes user interactions through the queue system with intelligent fallback 
    to direct processing if queue is unavailable.
    
    Expected payload:
    {
        "session_id": "string",
        "user_id": "string", 
        "action_type": "string",
        "page_path": "string",
        "element_type": "string",
        "element_id": "string", 
        "metadata": {}
    }
    """
    try:
        data = await request.json()
        
        # Use queue manager for processing (with fallback to direct processing)
        if queue_manager:
            result = await queue_manager.async_submit_interaction(data)
            
            # If processed directly, also broadcast via WebSocket
            if result.get("mode") == "direct" and websocket_manager:
                await websocket_manager.broadcast({
                    "type": "new_interaction",
                    "data": {
                        "session_id": data.get("session_id"),
                        "action_type": data.get("action_type"),
                        "page_path": data.get("page_path"),
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                })
            
            return result
        else:
            # Fallback to direct processing if queue manager is not available
            db = get_db_session()
            
            interaction = UserInteraction(
                session_id=data.get("session_id"),
                user_id=data.get("user_id"),
                action_type=data.get("action_type"),
                page_path=data.get("page_path"),
                element_type=data.get("element_type"),
                element_id=data.get("element_id"),
                interaction_metadata=data.get("metadata", {})
            )
            
            db.add(interaction)
            db.commit()
            db.refresh(interaction)
            db.close()
            
            # Broadcast to connected WebSocket clients
            if websocket_manager:
                await websocket_manager.broadcast({
                    "type": "new_interaction",
                    "data": {
                        "id": interaction.id,
                        "session_id": interaction.session_id,
                        "action_type": interaction.action_type,
                        "page_path": interaction.page_path,
                        "timestamp": interaction.timestamp.isoformat()
                    }
                })
            
            return {"id": interaction.id, "status": "created", "mode": "fallback"}
        
    except Exception as e:
        logger.error(f"Error creating interaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/interactions", tags=["Interactions"], summary="Get User Interactions")
async def get_interactions(
    session_id: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get user interactions with optional filtering
    
    Query parameters:
    - session_id: Filter by specific session ID
    - limit: Maximum number of interactions to return (default: 100)
    - offset: Number of interactions to skip (default: 0)
    """
    try:
        db = get_db_session()
        query = db.query(UserInteraction)
        
        if session_id:
            query = query.filter(UserInteraction.session_id == session_id)
            
        interactions = query.order_by(UserInteraction.timestamp.desc()).offset(offset).limit(limit).all()
        db.close()
        
        return {
            "interactions": [
                {
                    "id": i.id,
                    "session_id": i.session_id,
                    "action_type": i.action_type,
                    "page_path": i.page_path,
                    "element_type": i.element_type,
                    "element_id": i.element_id,
                    "metadata": i.interaction_metadata,
                    "timestamp": i.timestamp.isoformat()
                }
                for i in interactions
            ],
            "total": len(interactions)
        }
        
    except Exception as e:
        logger.error(f"Error getting interactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Session Endpoints
# =============================================================================

@router.post("/api/sessions", tags=["Sessions"], summary="Create/Update User Session")
async def create_session(request: Request):
    """
    Create or update a user session using queue processing
    
    Processes session data through the queue system with intelligent fallback
    to direct processing if queue is unavailable.
    
    Expected payload:
    {
        "session_id": "string",
        "user_id": "string",
        "page_views": 0,
        "total_interactions": 0, 
        "metadata": {},
        "end_time": "2024-01-01T00:00:00Z" (optional)
    }
    """
    try:
        data = await request.json()
        
        # Use queue manager for processing (with fallback to direct processing)
        if queue_manager:
            result = await queue_manager.async_submit_session_update(data)
            return result
        else:
            # Fallback to direct processing if queue manager is not available
            db = get_db_session()
            
            existing_session = db.query(UserSession).filter(
                UserSession.session_id == data.get("session_id")
            ).first()
            
            if existing_session:
                # Update existing session
                existing_session.page_views = data.get("page_views", existing_session.page_views)
                existing_session.total_interactions = data.get("total_interactions", existing_session.total_interactions)
                existing_session.metadata = data.get("metadata", existing_session.metadata)
                existing_session.updated_at = datetime.now(timezone.utc)
                if data.get("end_time"):
                    existing_session.end_time = datetime.fromisoformat(data["end_time"])
                
                db.commit()
                db.refresh(existing_session)
                session = existing_session
                status = "updated"
            else:
                # Create new session
                session = UserSession(
                    session_id=data.get("session_id"),
                    user_id=data.get("user_id"),
                    page_views=data.get("page_views", 0),
                    total_interactions=data.get("total_interactions", 0),
                    session_metadata=data.get("metadata", {})
                )
                db.add(session)
                db.commit()
                db.refresh(session)
                status = "created"
            
            db.close()
            
            return {
                "id": session.id,
                "session_id": session.session_id,
                "status": status,
                "mode": "fallback"
            }
        
    except Exception as e:
        logger.error(f"Error creating/updating session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/sessions/{session_id}", tags=["Sessions"], summary="Get Session Details")
async def get_session(session_id: str):
    """
    Get session details by session ID
    
    Returns comprehensive session information including timestamps,
    interaction counts, and metadata.
    """
    try:
        db = get_db_session()
        session = db.query(UserSession).filter(UserSession.session_id == session_id).first()
        db.close()
        
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
            
        return {
            "id": session.id,
            "session_id": session.session_id,
            "user_id": session.user_id,
            "start_time": session.start_time.isoformat(),
            "end_time": session.end_time.isoformat() if session.end_time else None,
            "page_views": session.page_views,
            "total_interactions": session.total_interactions,
            "metadata": session.session_metadata
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Queue Management Endpoints
# =============================================================================

@router.get("/api/queue/status/{task_id}", tags=["Queue"], summary="Get Task Status")
async def get_task_status(task_id: str):
    """
    Get the status and result of a queued task
    
    Returns task execution status, progress, results, and error information
    if available. Useful for monitoring long-running batch operations.
    """
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not available")
    
    try:
        status = await queue_manager.async_get_task_status(task_id)
        return status
    except Exception as e:
        logger.error(f"Error getting task status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/queue/cancel/{task_id}", tags=["Queue"], summary="Cancel Task")
async def cancel_task(task_id: str):
    """Cancel a queued task by task ID"""
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not available")
    
    try:
        result = await queue_manager.async_cancel_task(task_id)
        return result
    except Exception as e:
        logger.error(f"Error cancelling task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/stats", tags=["Queue"], summary="Get Queue Statistics")
async def get_queue_stats():
    """Get comprehensive queue statistics including active, scheduled, and reserved tasks"""
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not available")
    
    try:
        stats = await queue_manager.async_get_queue_stats()
        return stats
    except Exception as e:
        logger.error(f"Error getting queue stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/health", tags=["Queue"], summary="Queue Health Check")
async def queue_health_check():
    """Dedicated queue health check endpoint for monitoring queue system status"""
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not available")
    
    try:
        health = await queue_manager.async_health_check()
        return health
    except Exception as e:
        logger.error(f"Error checking queue health: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/jobs", tags=["Queue"], summary="Get All Queue Jobs")
async def get_queue_jobs(limit: int = 50, offset: int = 0, status: str = None):
    """
    Get all queue jobs with pagination and optional status filtering
    
    Returns jobs from the queue_jobs table with their associated task counts
    """
    try:
        from Database.database import get_db_session
        from Database.data.queue_models import QueueJob, QueueTask
        from sqlalchemy import desc, func
        
        db = get_db_session()
        
        # Base query with task counts
        query = db.query(QueueJob).order_by(desc(QueueJob.created_at))
        
        # Filter by status if provided
        if status:
            query = query.filter(QueueJob.status == status)
        
        # Apply pagination
        jobs = query.offset(offset).limit(limit).all()
        
        # Convert to dict format
        job_list = []
        for job in jobs:
            job_dict = job.to_dict()
            
            # Get actual task count from database
            actual_task_count = db.query(QueueTask).filter(QueueTask.job_id == job.job_id).count()
            job_dict["actual_task_count"] = actual_task_count
            
            job_list.append(job_dict)
        
        # Get total count for pagination
        total_count = db.query(QueueJob).count()
        if status:
            total_count = db.query(QueueJob).filter(QueueJob.status == status).count()
        
        return {
            "jobs": job_list,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
        
    except Exception as e:
        logger.error(f"Error getting queue jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/job/{job_id}", tags=["Queue"], summary="Get Queue Job Details")
async def get_queue_job(job_id: str):
    """Get detailed information about a specific queue job"""
    try:
        from Database.database import get_db_session
        from Database.data.queue_models import QueueJob, QueueTask
        
        db = get_db_session()
        
        # Get the job
        job = db.query(QueueJob).filter(QueueJob.job_id == job_id).first()
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        job_dict = job.to_dict()
        
        # Get all tasks for this job
        tasks = db.query(QueueTask).filter(QueueTask.job_id == job_id).order_by(QueueTask.created_at).all()
        job_dict["tasks"] = [task.to_dict() for task in tasks]
        
        return job_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue job {job_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/tasks", tags=["Queue"], summary="Get All Queue Tasks")
async def get_queue_tasks(limit: int = 100, offset: int = 0, status: str = None, adapter_name: str = None):
    """
    Get all queue tasks with pagination and optional filtering
    
    Returns tasks from the queue_tasks table with optional filtering by status and adapter
    """
    try:
        from Database.database import get_db_session
        from Database.data.queue_models import QueueTask
        from sqlalchemy import desc
        
        db = get_db_session()
        
        # Base query
        query = db.query(QueueTask).order_by(desc(QueueTask.created_at))
        
        # Apply filters
        if status:
            query = query.filter(QueueTask.status == status)
        if adapter_name:
            query = query.filter(QueueTask.adapter_name == adapter_name)
        
        # Apply pagination
        tasks = query.offset(offset).limit(limit).all()
        
        # Convert to dict format
        task_list = [task.to_dict() for task in tasks]
        
        # Get total count for pagination
        total_query = db.query(QueueTask)
        if status:
            total_query = total_query.filter(QueueTask.status == status)
        if adapter_name:
            total_query = total_query.filter(QueueTask.adapter_name == adapter_name)
        total_count = total_query.count()
        
        return {
            "tasks": task_list,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
        
    except Exception as e:
        logger.error(f"Error getting queue tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/batch", tags=["Queue"], summary="Submit Batch Job")
async def submit_batch_processing(request: Request):
    """
    Submit a batch processing job
    
    Accepts batch operations for processing multiple items through the queue system.
    
    Expected payload:
    {
        "type": "interactions|sessions|custom",
        "items": [...],
        "config": {
            "batch_size": 4,
            "priority": 5
        }
    }
    """
    if not queue_manager:
        raise HTTPException(status_code=503, detail="Queue manager not available")
    
    try:
        data = await request.json()
        result = await queue_manager.async_submit_batch(data)
        return result
    except Exception as e:
        logger.error(f"Error submitting batch: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Visage Frontend Integration Endpoints
# =============================================================================

@router.post("/api/visage/job", tags=["Visage"], summary="Create Visage Batch Job")
async def create_visage_batch_job(request: Request):
    """
    Create a batch Visage face identification job with custom API endpoint
    
    This endpoint allows frontend applications to submit batch face identification
    jobs to external Visage API services. Jobs are processed asynchronously
    with real-time progress tracking via WebSocket.
    
    Expected payload:
    {
        "images": ["base64_image_1", "base64_image_2", ...],
        "visage_api_url": "http://your-visage-api.com/api/identify",
        "config": {
            "threshold": 0.7,
            "job_name": "Custom Job Name",
            "user_id": "user_123",
            "session_id": "session_456",
            "additional_params": {"max_faces": 10, "return_embeddings": true}
        }
    }
    """
    try:
        from api.VisageFrontendAdapter import create_visage_job_with_api_url

        data = await request.json()
        images = data.get("images", [])
        # Ignore any client-provided URL; always use backend-configured value
        visage_api_url = app_config.VISAGE_API_URL
        config = data.get("config", {})
        
        if not images:
            raise HTTPException(status_code=400, detail="No images provided")
        
        # If not provided, we fall back to centrally configured URL
        if not visage_api_url:
            raise HTTPException(status_code=500, detail="VISAGE_API_URL not configured on server")
        
        # Create the batch job
        result = create_visage_job_with_api_url(
            images=images,
            visage_api_url=visage_api_url,
            threshold=config.get("threshold", 0.5),
            job_name=config.get("job_name"),
            user_id=config.get("user_id"),
            session_id=config.get("session_id"),
            additional_params=config.get("additional_params")
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Visage batch job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/visage/task", tags=["Visage"], summary="Create Single Visage Task") 
async def create_visage_single_task(request: Request):
    """
    Create a single Visage face identification task with custom API endpoint
    
    Supports both legacy and new generalized payload formats for backward compatibility.
    
    Legacy payload format:
    {
        "image": "base64_encoded_image_data",
        "visage_api_url": "http://your-visage-api.com/api/identify",
        "config": {
            "threshold": 0.8,
            "additional_params": {"max_faces": 5, "return_embeddings": false}
        }
    }
    
    New generalized payload format:
    {
        "service_type": "visage",
        "image_data": {
            "stash_image_id": "123",
            "image_base64": "base64_data",
            "stash_image_title": "Image Title",
            "image_metadata": {...}
        },
        "config": {
            "threshold": 0.7,
            "service_config": {
                "api_endpoint": "http://localhost:5000/api/predict_1",
                "max_faces": 10,
                "detection_mode": "multi"
            }
        }
    }
    """
    try:
        from api.VisageFrontendAdapter import create_single_visage_task_with_api_url
        
        data = await request.json()
        
        # Detect payload format and normalize
        if "service_type" in data and data.get("service_type") == "visage":
            # New generalized format
            image_data_obj = data.get("image_data", {})
            config = data.get("config", {})
            service_config = config.get("service_config", {})
            
            image_data = image_data_obj.get("image_base64")
            # Ignore any client-provided URL; always use backend-configured value
            visage_api_url = app_config.VISAGE_API_URL
            threshold = config.get("threshold", 0.7)
            
            additional_params = {
                "max_faces": service_config.get("max_faces", 10),
                "return_embeddings": service_config.get("return_embeddings", False),
                "detection_mode": service_config.get("detection_mode", "multi"),
                "source": config.get("source", "generalized_api"),
                "stash_image_id": image_data_obj.get("stash_image_id"),
                "stash_image_title": image_data_obj.get("stash_image_title"),
                "stash_metadata": image_data_obj.get("image_metadata", {})
            }
            
        else:
            # Legacy format
            image_data = data.get("image")
            # Ignore any client-provided URL; always use backend-configured value
            visage_api_url = app_config.VISAGE_API_URL
            config = data.get("config", {})
            threshold = config.get("threshold", 0.5)
            additional_params = config.get("additional_params", {})
        
        if not image_data:
            raise HTTPException(status_code=400, detail="No image data provided")
        
        if not visage_api_url:
            raise HTTPException(status_code=500, detail="VISAGE_API_URL not configured on server")
        
        # Create the single task
        result = create_single_visage_task_with_api_url(
            image_data=image_data,
            visage_api_url=visage_api_url,
            threshold=threshold,
            additional_params=additional_params
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating Visage single task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/visage/job/{job_id}/results", tags=["Visage"], summary="Get Visage Job Results")
async def get_visage_job_results(job_id: str):
    """
    Get all Visage results for a completed job
    
    This endpoint allows you to:
    1. Look at previous jobs (job_id)
    2. Find the tasks that ran (from queue_tasks table)
    3. Get the service-specific outputs (from visage_results table)
    
    Returns all raw Visage API outputs for tasks within the specified job.
    """
    try:
        from Database.data.visage_adapter import VisageDatabaseAdapter
        
        adapter = VisageDatabaseAdapter()
        
        # Get job info
        job = adapter.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get all Visage-specific results for this job
        results = adapter.get_job_results(job_id)
        
        return {
            "job_id": job_id,
            "job_info": job,
            "total_results": len(results),
            "visage_results": results
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Visage job results: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/visage/task/{task_id}/result", tags=["Visage"], summary="Get Visage Task Result")
async def get_visage_task_result(task_id: str):
    """
    Get Visage result for a specific task
    
    This endpoint returns the raw Visage API output stored in the
    visage_results table for a specific task execution.
    """
    try:
        from Database.data.visage_adapter import VisageDatabaseAdapter
        
        adapter = VisageDatabaseAdapter()
        
        # Get task info
        task = adapter.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="Task not found")
        
        # Get Visage-specific result
        result = adapter.get_task_result(task_id)
        if not result:
            raise HTTPException(status_code=404, detail="Visage result not found for this task")
        
        return {
            "task_id": task_id,
            "task_info": task,
            "visage_result": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Visage task result: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Universal Queue Management Endpoints
# =============================================================================

@router.get("/api/queue/tasks", tags=["Queue"], summary="Get All Queue Tasks")
async def get_all_queue_tasks(
    adapter_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get tasks from all adapters with filtering support
    
    This is the universal tasks endpoint that supports all AI services.
    Allows filtering by adapter (service), status, and pagination.
    
    Query parameters:
    - adapter_name: Filter by service (visage, content_analysis, scene_analysis)
    - status: Filter by status (pending, running, finished, failed)  
    - limit: Maximum results to return
    - offset: Results to skip for pagination
    """
    try:
        from Database.data.queue_service import queue_service
        
        tasks = queue_service.get_all_tasks(
            adapter_name=adapter_name,
            status=status,
            limit=limit,
            offset=offset
        )
        
        # Count total for pagination
        total_count = len(queue_service.get_all_tasks(adapter_name=adapter_name, status=status, limit=1000))
        
        return {
            "tasks": tasks,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
        
    except Exception as e:
        logger.error(f"Error getting queue tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/task/{task_id}", tags=["Queue"], summary="Get Queue Task Details")
async def get_queue_task_details(task_id: str):
    """
    Get detailed information about a specific task
    
    This works across all adapters and provides complete task information
    including input data, output results, and execution metrics.
    """
    try:
        from Database.data.queue_models import QueueTask
        from Database.database import get_db_session
        
        db = get_db_session()
        
        # Get task info
        task = db.query(QueueTask).filter(QueueTask.task_id == task_id).first()
        if not task:
            db.close()
            raise HTTPException(status_code=404, detail="Task not found")
        
        db.close()
        return task.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue task details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/jobs", tags=["Queue"], summary="Get All Queue Jobs")  
async def get_all_queue_jobs(
    adapter_name: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """
    Get jobs from all adapters with filtering support
    
    Query parameters:
    - adapter_name: Filter by service (visage, content_analysis, scene_analysis)
    - status: Filter by status (pending, running, completed, failed, partial)
    - limit: Maximum results to return
    - offset: Results to skip for pagination
    """
    try:
        from Database.data.queue_service import queue_service
        
        jobs = queue_service.get_all_jobs(
            adapter_name=adapter_name,
            status=status,
            limit=limit,
            offset=offset
        )
        
        # Count total for pagination
        total_count = len(queue_service.get_all_jobs(adapter_name=adapter_name, status=status, limit=1000))
        
        return {
            "jobs": jobs,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < total_count
        }
        
    except Exception as e:
        logger.error(f"Error getting queue jobs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/job/{job_id}", tags=["Queue"], summary="Get Queue Job Details")
async def get_queue_job_details(job_id: str):
    """
    Get detailed information about a specific job including its tasks
    
    This works across all adapters and provides task-level details for any job.
    """
    try:
        from Database.data.queue_service import queue_service
        from Database.data.queue_models import QueueJob, QueueTask
        from Database.database import get_db_session
        
        db = get_db_session()
        
        # Get job info
        job = db.query(QueueJob).filter(QueueJob.job_id == job_id).first()
        if not job:
            db.close()
            raise HTTPException(status_code=404, detail="Job not found")
        
        # Get associated tasks
        tasks = db.query(QueueTask).filter(QueueTask.job_id == job_id).all()
        db.close()
        
        job_dict = job.to_dict()
        job_dict["tasks"] = [task.to_dict() for task in tasks]
        
        return job_dict
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue job details: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/queue/stats", tags=["Queue"], summary="Get Queue Statistics")
async def get_queue_statistics():
    """
    Get comprehensive queue statistics across all adapters
    
    Returns task and job counts, processing metrics, and adapter breakdown.
    """
    try:
        from Database.data.queue_service import queue_service
        
        stats = queue_service.get_queue_statistics()
        return stats
        
    except Exception as e:
        logger.error(f"Error getting queue statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# Generalized AI Service Endpoints
# =============================================================================

@router.post("/api/content/task", tags=["Content Analysis"], summary="Create Content Analysis Task")
async def create_content_analysis_task(request: Request):
    """
    Create a content analysis task using the generalized AI service format
    
    Expected payload:
    {
        "service_type": "content_analysis",
        "image_data": {
            "stash_image_id": "123",
            "image_base64": "base64_data",
            "stash_image_title": "Image Title",
            "image_metadata": {...}
        },
        "config": {
            "threshold": 0.5,
            "service_config": {
                "api_endpoint": "http://localhost:5001/api/analyze",
                "include_tags": true,
                "include_description": true,
                "confidence_threshold": 0.5
            }
        }
    }
    """
    try:
        from api.ContentAnalysisAdapter import create_content_analysis_task_with_config
        
        data = await request.json()
        
        # Extract generalized payload
        service_type = data.get("service_type", "content_analysis")
        image_data_obj = data.get("image_data", {})
        config = data.get("config", {})
        service_config = config.get("service_config", {})
        
        image_data = image_data_obj.get("image_base64")
        if not image_data:
            raise HTTPException(status_code=400, detail="No image data provided")

        # Ignore any client-provided endpoint; always use backend-configured value
        api_endpoint = app_config.CONTENT_ANALYSIS_API_URL
        
        # Create content analysis task
        result = create_content_analysis_task_with_config(
            image_data=image_data,
            api_endpoint=api_endpoint,
            stash_image_id=image_data_obj.get("stash_image_id"),
            stash_image_title=image_data_obj.get("stash_image_title"),
            stash_metadata=image_data_obj.get("image_metadata", {}),
            config={
                "include_tags": service_config.get("include_tags", True),
                "include_description": service_config.get("include_description", True),
                "confidence_threshold": service_config.get("confidence_threshold", 0.5),
                "threshold": config.get("threshold", 0.5),
                "priority": config.get("priority", 5),
                "source": config.get("source", "generalized_api")
            }
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating content analysis task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/scene/task", tags=["Scene Analysis"], summary="Create Scene Analysis Task")
async def create_scene_analysis_task(request: Request):
    """
    Create a scene analysis task using the generalized AI service format
    
    Expected payload:
    {
        "service_type": "scene_analysis",
        "image_data": {
            "stash_image_id": "123",
            "image_base64": "base64_data",
            "stash_image_title": "Scene Title",
            "image_metadata": {...}
        },
        "config": {
            "threshold": 0.5,
            "service_config": {
                "api_endpoint": "http://localhost:5002/api/analyze_scene",
                "extract_keyframes": false,
                "analyze_audio": false
            }
        }
    }
    """
    try:
        from api.SceneAnalysisAdapter import create_scene_analysis_task_with_config
        
        data = await request.json()
        
        # Extract generalized payload
        service_type = data.get("service_type", "scene_analysis")
        image_data_obj = data.get("image_data", {})
        config = data.get("config", {})
        service_config = config.get("service_config", {})
        
        content_data = image_data_obj.get("image_base64")  # Could be image or video data
        if not content_data:
            raise HTTPException(status_code=400, detail="No content data provided")

        # Ignore any client-provided endpoint; always use backend-configured value
        api_endpoint = app_config.SCENE_ANALYSIS_API_URL
        
        # Create scene analysis task
        result = create_scene_analysis_task_with_config(
            content_data=content_data,
            api_endpoint=api_endpoint,
            stash_content_id=image_data_obj.get("stash_image_id"),
            stash_content_title=image_data_obj.get("stash_image_title"),
            stash_metadata=image_data_obj.get("image_metadata", {}),
            config={
                "extract_keyframes": service_config.get("extract_keyframes", False),
                "analyze_audio": service_config.get("analyze_audio", False),
                "threshold": config.get("threshold", 0.5),
                "priority": config.get("priority", 5),
                "source": config.get("source", "generalized_api")
            }
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating scene analysis task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/general/task", tags=["General AI"], summary="Create General AI Task")
async def create_general_ai_task(request: Request):
    """
    Generic AI service endpoint for unknown or new service types
    
    This endpoint serves as a fallback for AI services that don't have 
    dedicated endpoints yet. It uses a plugin-style architecture to
    dynamically load service adapters.
    
    Expected payload:
    {
        "service_type": "custom_service_name",
        "image_data": {
            "stash_image_id": "123",
            "image_base64": "base64_data",
            "stash_image_title": "Content Title",
            "image_metadata": {...}
        },
        "config": {
            "threshold": 0.5,
            "service_config": {
                "api_endpoint": "http://localhost:5003/api/custom",
                "custom_param": "value"
            }
        }
    }
    """
    try:
        from api.GeneralAIAdapter import create_general_ai_task_with_config
        
        data = await request.json()
        
        # Extract generalized payload
        service_type = data.get("service_type", "unknown")
        image_data_obj = data.get("image_data", {})
        config = data.get("config", {})
        service_config = config.get("service_config", {})
        
        content_data = image_data_obj.get("image_base64")
        if not content_data:
            raise HTTPException(status_code=400, detail="No content data provided")
        
        api_endpoint = service_config.get("api_endpoint")
        if not api_endpoint:
            raise HTTPException(status_code=400, detail="No API endpoint specified for general AI service")
        
        # Create general AI task
        result = create_general_ai_task_with_config(
            service_type=service_type,
            content_data=content_data,
            api_endpoint=api_endpoint,
            stash_content_id=image_data_obj.get("stash_image_id"),
            stash_content_title=image_data_obj.get("stash_image_title"),
            stash_metadata=image_data_obj.get("image_metadata", {}),
            config={
                **service_config,  # Pass through all service-specific config
                "threshold": config.get("threshold", 0.5),
                "priority": config.get("priority", 5),
                "source": config.get("source", "generalized_api")
            }
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating general AI task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =============================================================================
# WebSocket Queue Demo Endpoints
# =============================================================================

@router.post("/api/demo/visage/job", tags=["Demo"], summary="Create Demo Visage Job")
async def create_demo_visage_job(request: Request):
    """
    Create a demo Visage face identification job for WebSocket testing
    
    This endpoint creates a batch job with multiple face identification tasks
    that can be monitored via WebSocket subscriptions.
    
    Returns job_id and task_ids that clients can subscribe to for real-time updates.
    """
    try:
        from Database.data.visage_adapter import VisageDatabaseAdapter, VisageJobTypes, VisageTaskTypes
        from api.VisageFrontendAdapter import visage_face_identify_task
        
        # Parse request parameters
        try:
            data = await request.json()
        except:
            data = {}
        
        batch_size = data.get("batch_size", 3)
        demo_task_count = data.get("demo_task_count", 5)
        visage_api_url = data.get("visage_api_url", "http://localhost:5000/api/identify")
        threshold = data.get("threshold", 0.7)
        
        # Create sample image data for demonstration
        sample_images = [
            f"demo_base64_encoded_image_data_{i}" for i in range(1, demo_task_count + 1)
        ]
        
        adapter = VisageDatabaseAdapter()
        
        # Create job directly
        job_id = adapter.create_job(
            job_type=VisageJobTypes.BULK_FACE_IDENTIFICATION,
            job_name="Demo Face Identification Batch",
            job_config={
                "threshold": threshold,
                "visage_api_url": visage_api_url,
                "additional_params": {},
                "image_count": len(sample_images)
            },
            user_id="demo_user",
            session_id="demo_session"
        )
        
        # Create individual tasks and link them to the job
        created_task_ids = []
        
        for i, image_data in enumerate(sample_images):
            # Create individual task
            task_id = adapter.create_task(
                task_type=VisageTaskTypes.FACE_IDENTIFY,
                input_data={
                    "image": image_data,
                    "threshold": threshold,
                    "visage_api_url": visage_api_url,
                    "additional_params": {"max_faces": 5, "source": "demo_batch_job"},
                    "batch_index": i
                },
                job_id=job_id,  # Link task to job immediately
                priority=5
            )
            created_task_ids.append(task_id)
            
            # Queue the individual task
            visage_face_identify_task.schedule(args=({
                "task_id": task_id,
                "input_data": {
                    "image": image_data,
                    "threshold": threshold,
                    "visage_api_url": visage_api_url,
                    "additional_params": {"max_faces": 5, "source": "demo_batch_job"},
                    "batch_index": i
                }
            },), delay=0)
        
        # Update job with task IDs
        adapter.add_tasks_to_job(job_id, created_task_ids)
        
        result = {
            "job_id": job_id,
            "status": "queued",
            "coordinator_task_id": None,  # Direct creation, no coordinator needed
            "expected_tasks": len(created_task_ids),
            "task_ids": created_task_ids,
            "visage_api_url": visage_api_url,
            "message": "Demo Visage job created. Subscribe to job_id via WebSocket to receive real-time updates.",
            "websocket_subscription": {
                "type": "subscribe_job",
                "job_id": job_id
            }
        }
        
        logger.info(f"Created demo Visage job {job_id} with {len(created_task_ids)} tasks")
        return result
        
    except Exception as e:
        logger.error(f"Error creating demo Visage job: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/api/demo/visage/task", tags=["Demo"], summary="Create Demo Visage Task")
async def create_demo_visage_task():
    """
    Create a single demo Visage face identification task for WebSocket testing
    
    Creates an individual task that can be monitored via WebSocket for
    real-time status updates, progress tracking, and result delivery.
    
    Returns task_id that clients can subscribe to for updates.
    """
    try:
        from api.VisageFrontendAdapter import create_single_visage_task_with_api_url
        
        # Create single task with demo API URL
        result = create_single_visage_task_with_api_url(
            image_data="demo_base64_encoded_image_data",
            visage_api_url="http://localhost:5000/api/identify",  # Default demo URL
            threshold=0.8,
            additional_params={"max_faces": 5, "source": "demo_single_task"}
        )
        
        result.update({
            "message": "Demo Visage task created. Subscribe to task_id via WebSocket to receive real-time updates.",
            "websocket_subscription": {
                "type": "subscribe_task", 
                "task_id": result["task_id"]
            }
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Error creating demo Visage task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/demo/websocket/instructions", tags=["Demo"], summary="WebSocket Usage Instructions")
async def websocket_demo_instructions():
    """
    Get comprehensive instructions for testing WebSocket queue functionality
    
    Provides examples of WebSocket message formats, subscription patterns,
    and demo workflows for testing real-time queue monitoring.
    """
    return {
        "websocket_endpoint": "/ws/{session_id}",
        "connection_example": "ws://localhost:9998/ws/demo_session",
        "supported_subscriptions": {
            "task_updates": {
                "description": "Subscribe to individual task status updates",
                "subscribe_message": {
                    "type": "subscribe_task",
                    "task_id": "task_uuid_here"
                },
                "update_format": {
                    "type": "task_status",
                    "task_id": "task_uuid",
                    "status": "pending|running|completed|failed",
                    "adapter_name": "visage",
                    "task_type": "visage_face_identify",
                    "output_json": {"result": "..."},
                    "processing_time_ms": 1500.0,
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            },
            "job_progress": {
                "description": "Subscribe to batch job progress updates",
                "subscribe_message": {
                    "type": "subscribe_job",
                    "job_id": "job_uuid_here"
                },
                "update_format": {
                    "type": "job_progress",
                    "job_id": "job_uuid",
                    "status": "pending|running|completed|partial|failed",
                    "adapter_name": "visage",
                    "job_type": "visage_bulk_face_identification",
                    "total_tasks": 5,
                    "completed_tasks": 3,
                    "failed_tasks": 0,
                    "progress_percentage": 60.0,
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            },
            "queue_statistics": {
                "description": "Subscribe to overall queue system statistics",
                "subscribe_message": {
                    "type": "subscribe_queue_stats"
                },
                "update_format": {
                    "type": "queue_stats",
                    "data": {
                        "total_tasks": 50,
                        "pending_tasks": 10,
                        "running_tasks": 5,
                        "completed_tasks": 35,
                        "failed_tasks": 0
                    },
                    "timestamp": "2024-01-01T00:00:00Z"
                }
            }
        },
        "demo_workflow": {
            "1": "Connect to WebSocket: ws://localhost:9998/ws/demo_session",
            "2": "Create demo job: POST /api/demo/visage/job",
            "3": "Subscribe to job updates: {\"type\": \"subscribe_job\", \"job_id\": \"job_uuid\"}",
            "4": "Monitor real-time progress as tasks are processed",
            "5": "Create individual task: POST /api/demo/visage/task", 
            "6": "Subscribe to task updates: {\"type\": \"subscribe_task\", \"task_id\": \"task_uuid\"}",
            "7": "Watch individual task lifecycle from pending to completion"
        },
        "unsubscribe_examples": {
            "task": {"type": "unsubscribe_task", "task_id": "task_uuid"},
            "job": {"type": "unsubscribe_job", "job_id": "job_uuid"},
            "queue_stats": {"type": "unsubscribe_queue_stats"}
        }
    }

# =============================================================================
# Internal Endpoints (for worker process callbacks)
# =============================================================================

@router.post("/internal/broadcast_task_status", tags=["Internal"], summary="Internal WebSocket Broadcast")
async def internal_broadcast_task_status(request: Request):
    """
    Internal endpoint for Huey worker processes to trigger WebSocket broadcasts
    This is needed because worker processes run in separate memory spaces
    """
    try:
        data = await request.json()
        task_id = data.get("task_id")
        
        if not task_id:
            raise HTTPException(status_code=400, detail="task_id is required")
        
        if not websocket_manager:
            logger.warning("WebSocket manager not available for internal broadcast")
            return {"status": "error", "message": "WebSocket manager not available"}
        
        # Extract broadcast data
        message = {
            "status": data.get("status"),
            "adapter_name": data.get("adapter_name"),
            "task_type": data.get("task_type"),
            "output_json": data.get("output_json"),
            "error_message": data.get("error_message"),
            "processing_time_ms": data.get("processing_time_ms")
        }
        
        logger.info(f"Internal broadcast request for task {task_id}: {data.get('status')}")
        
        # Broadcast to subscribed WebSocket clients
        await websocket_manager.broadcast_task_update(task_id, message)
        
        return {"status": "success", "message": f"WebSocket broadcast sent for task {task_id}"}
        
    except Exception as e:
        logger.error(f"Error in internal broadcast: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/internal/broadcast_job_progress", tags=["Internal"], summary="Internal Job Progress Broadcast")
async def internal_broadcast_job_progress(request: Request):
    """
    Internal endpoint for Huey worker processes to trigger job progress WebSocket broadcasts
    This is needed because worker processes run in separate memory spaces
    """
    try:
        data = await request.json()
        job_id = data.get("job_id")
        
        if not job_id:
            raise HTTPException(status_code=400, detail="job_id is required")
        
        if not websocket_manager:
            logger.warning("WebSocket manager not available for internal job broadcast")
            return {"status": "error", "message": "WebSocket manager not available"}
        
        # Extract broadcast data
        message = {
            "status": data.get("status"),
            "adapter_name": data.get("adapter_name"),
            "job_type": data.get("job_type"),
            "total_tasks": data.get("total_tasks"),
            "completed_tasks": data.get("completed_tasks"),
            "failed_tasks": data.get("failed_tasks"),
            "progress_percentage": data.get("progress_percentage")
        }
        
        logger.info(f"Internal broadcast request for job {job_id}: {data.get('status')} ({data.get('completed_tasks')}/{data.get('total_tasks')})")
        
        # Broadcast to subscribed WebSocket clients
        await websocket_manager.broadcast_job_update(job_id, message)
        
        return {"status": "success", "message": f"WebSocket broadcast sent for job {job_id}"}
        
    except Exception as e:
        logger.error(f"Error in internal job broadcast: {e}")
        raise HTTPException(status_code=500, detail=str(e))