# =============================================================================
# Visage Frontend Adapter - API Integration Tasks
# =============================================================================
#
# This module provides frontend-facing endpoints and queue tasks for Visage
# face recognition service integration. It handles API calls to external
# Visage services and manages task lifecycle through the normalized queue schema.
#
# =============================================================================

import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import httpx

from Services.queue.huey_app import huey, DEFAULT_RETRY_CONFIG
from Database.data.visage_adapter import VisageDatabaseAdapter, VisageTaskTypes
from Database.data.queue_models import TaskStatus

logger = logging.getLogger(__name__)

# =============================================================================
# Visage Queue Tasks
# =============================================================================

@huey.task(retries=DEFAULT_RETRY_CONFIG["retries"], retry_delay=DEFAULT_RETRY_CONFIG["retry_delay"])
def visage_face_identify_task(task_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Process individual face identification task using external Visage API
    
    Args:
        task_data: Dictionary containing task information and input data
            - task_id: Unique task identifier
            - input_data: Dictionary containing:
                - image: Base64 encoded image data or image URL
                - threshold: Recognition threshold (0.0-1.0, default: 0.5)
                - visage_api_url: Visage API endpoint URL (default: http://localhost:5000/api/identify)
                - additional_params: Extra parameters for Visage API
        
    Returns:
        Dictionary with processing results
    """
    adapter = VisageDatabaseAdapter()
    task_id = task_data.get("task_id")
    
    try:
        logger.info(f"Starting Visage face identification task {task_id}")
        
        # Check if task has been cancelled before processing
        from Services.queue.processors import queue_processor
        if queue_processor.is_task_cancelled(task_id):
            logger.info(f"Task {task_id} was cancelled before processing, skipping")
            return {"status": "cancelled", "task_id": task_id}
        
        # Update task status to running
        adapter.update_task_status(task_id, TaskStatus.RUNNING.value)
        
        # Extract input data
        input_data = task_data.get("input_data", {})
        image_data = input_data.get("image")  # This should contain the base64 image data
        threshold = input_data.get("threshold", 0.5)
        visage_api_url = input_data.get("visage_api_url", "http://localhost:9997/api/predict_1")
        
        # Convert external URLs to internal Docker network URLs for container communication
        # DISABLED: This conversion was causing API failures when not running in Docker
        # if "10.0.0.154:9997" in visage_api_url or "localhost:9997" in visage_api_url:
        #     # Replace the host:port but preserve the endpoint path
        #     original_url = visage_api_url
        #     visage_api_url = visage_api_url.replace("10.0.0.154:9997", "visage:8000").replace("localhost:9997", "visage:8000")
        #     logger.info(f"Converted external URL to internal Docker network URL: {original_url} -> {visage_api_url}")
        additional_params = input_data.get("additional_params", {})
        
        logger.info(f"Task input data for {task_id}: image_data_length={len(image_data) if image_data else 0}, threshold={threshold}, visage_api_url={visage_api_url}")
        
        if not image_data:
            raise ValueError("No image data provided")
        
        if not visage_api_url:
            raise ValueError("No Visage API URL provided")
        
        # Check again for cancellation before making the API call
        if queue_processor.is_task_cancelled(task_id):
            logger.info(f"Task {task_id} was cancelled before API call, stopping")
            return {"status": "cancelled", "task_id": task_id}
        
        # Call actual Visage API
        processing_start_time = datetime.now()
        
        try:
            # Make API call to external Visage service
            with httpx.Client(timeout=30.0) as client:
                # Format payload for Visage API (expects image_data, not image)
                payload = {
                    "image_data": image_data,
                    "threshold": threshold,
                    "results": additional_params.get("max_faces", 3)
                }
                
                logger.info(f"Calling Visage API at {visage_api_url} for task {task_id}")
                logger.info(f"Payload: image_data length = {len(image_data) if image_data else 0}, threshold = {threshold}")
                logger.info(f"Full payload keys: {list(payload.keys())}")
                
                response = client.post(visage_api_url, json=payload)
                response.raise_for_status()
                
                api_result = response.json()
                processing_time_ms = (datetime.now() - processing_start_time).total_seconds() * 1000
                
                logger.info(f"Visage API call successful for task {task_id}")
                logger.debug(f"Visage API response: {api_result}")
                
        except httpx.RequestError as e:
            logger.error(f"Visage API request failed for task {task_id}: {str(e)}")
            logger.error(f"Request details - URL: {visage_api_url}, Error type: {type(e).__name__}")
            logger.error(f"Full error details: {repr(e)}")
            
            # Let's test the connection manually
            logger.error(f"Attempting to test basic connectivity to Visage service...")
            try:
                with httpx.Client(timeout=5.0) as test_client:
                    health_url = visage_api_url.replace('/api/predict_1', '/health')
                    health_response = test_client.get(health_url)
                    logger.error(f"Health check response: {health_response.status_code} - {health_response.text}")
            except Exception as health_e:
                logger.error(f"Health check also failed: {str(health_e)}")
            
            # NEVER return mock data - fail the task instead
            raise ValueError(f"Visage API is unavailable: {str(e)}, url: {visage_api_url}")

        except httpx.HTTPStatusError as e:
            logger.error(f"Visage API HTTP error for task {task_id}: {e.response.status_code}")
            raise ValueError(f"Visage API returned error: {e.response.status_code}")
        
        # Update task with results
        adapter.update_task_status(
            task_id, 
            TaskStatus.FINISHED.value,
            output_json=api_result,
            processing_time_ms=processing_time_ms
        )
        
        # Job status updates will be handled at the API level for universal queue management
        
        logger.info(f"Visage face identification task {task_id} completed successfully")
        return {"task_id": task_id, "status": "completed", "result": api_result}
        
    except Exception as e:
        logger.error(f"Visage face identification task {task_id} failed: {str(e)}")
        
        # Update task with error
        adapter.update_task_status(
            task_id, 
            TaskStatus.FAILED.value,
            error_message=str(e)
        )
        
        # Job status updates will be handled at the API level for universal queue management
        
        # Re-raise for Huey retry logic
        raise e

@huey.task(retries=DEFAULT_RETRY_CONFIG["retries"], retry_delay=DEFAULT_RETRY_CONFIG["retry_delay"])
def visage_batch_coordinator_task(job_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Coordinate batch face identification job using normalized schema
    
    Args:
        job_data: Dictionary containing job information
            - job_id: Unique job identifier
            - images: List of image data objects
            - task_config: Configuration for individual tasks including:
                - threshold: Recognition threshold
                - visage_api_url: Visage API endpoint URL
                - priority: Task priority level
                - additional_params: Extra parameters for Visage API
        
    Returns:
        Dictionary with coordination results
    """
    adapter = VisageDatabaseAdapter()
    job_id = job_data.get("job_id")
    
    try:
        logger.info(f"Starting Visage batch coordination for job {job_id}")
        
        # Get job details
        job = adapter.get_job(job_id)
        if not job:
            raise ValueError(f"Job {job_id} not found")
        
        # Create individual tasks for each image
        images = job_data.get("images", [])
        task_config = job_data.get("task_config", {})
        
        created_task_ids = []
        
        for i, image_data in enumerate(images):
            # Prepare input data with entity tracking if available in task_config
            task_input_data = {
                "image": image_data,
                "threshold": task_config.get("threshold", 0.5),
                "visage_api_url": task_config.get("visage_api_url", "http://localhost:5000/api/identify"),
                "additional_params": task_config.get("additional_params", {}),
                "batch_index": i
            }
            
            # Add entity tracking for batch items if specified in additional_params
            additional_params = task_config.get("additional_params", {})
            if additional_params.get("entity_type"):
                task_input_data["entity_type"] = additional_params["entity_type"]
                # For batch processing, entity_id might be an array or derived pattern
                if additional_params.get("entity_ids") and i < len(additional_params["entity_ids"]):
                    task_input_data["entity_id"] = additional_params["entity_ids"][i]
                elif additional_params.get("entity_id_base"):
                    # Generate entity ID based on batch index
                    task_input_data["entity_id"] = f"{additional_params['entity_id_base']}_{i}"
            
            # Create individual task
            task_id = adapter.create_task(
                task_type=VisageTaskTypes.FACE_IDENTIFY,
                input_data=task_input_data,
                job_id=job_id,
                priority=task_config.get("priority", 5)
            )
            created_task_ids.append(task_id)
            
            # Queue the individual task
            visage_face_identify_task.schedule(args=({
                "task_id": task_id,
                "input_data": task_input_data  # Use the same input_data with entity tracking
            },), delay=0)
        
        # Update job with task IDs
        adapter.add_tasks_to_job(job_id, created_task_ids)
        
        result = {
            "job_id": job_id,
            "tasks_created": len(created_task_ids),
            "task_ids": created_task_ids,
            "status": "coordinated",
            "visage_api_url": task_config.get("visage_api_url", "http://localhost:5000/api/identify")
        }
        
        logger.info(f"Visage batch coordination completed for job {job_id}: {len(created_task_ids)} tasks created")
        return result
        
    except Exception as e:
        logger.error(f"Visage batch coordination failed for job {job_id}: {str(e)}")
        raise e

# =============================================================================
# Helper Functions
# =============================================================================

# MOCK FUNCTION REMOVED - NO MOCK DATA ALLOWED

# =============================================================================
# Frontend API Helper Functions
# =============================================================================

def create_visage_job_with_api_url(
    images: list,
    visage_api_url: str,
    threshold: float = 0.5,
    job_name: Optional[str] = None,
    user_id: Optional[str] = None,
    session_id: Optional[str] = None,
    additional_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a Visage batch job with specified API URL for frontend use
    
    Args:
        images: List of image data (base64 or URLs)
        visage_api_url: External Visage API endpoint URL
        threshold: Recognition threshold (0.0-1.0)
        job_name: Human-readable job name
        user_id: Optional user ID
        session_id: Optional session ID
        additional_params: Extra parameters for Visage API
        
    Returns:
        Dictionary containing job_id and status information
    """
    from Database.data.visage_adapter import VisageJobTypes
    
    adapter = VisageDatabaseAdapter()
    
    # Create job
    job_id = adapter.create_job(
        job_type=VisageJobTypes.BULK_FACE_IDENTIFICATION,
        job_name=job_name or f"Face Identification Batch ({len(images)} images)",
        job_config={
            "threshold": threshold,
            "visage_api_url": visage_api_url,
            "additional_params": additional_params or {},
            "image_count": len(images)
        },
        user_id=user_id,
        session_id=session_id
    )
    
    # Queue the coordinator task
    coordinator_task = visage_batch_coordinator_task.schedule(args=({
        "job_id": job_id,
        "images": images,
        "task_config": {
            "threshold": threshold,
            "visage_api_url": visage_api_url,
            "additional_params": additional_params or {},
            "priority": 5
        }
    },), delay=0)
    
    return {
        "job_id": job_id,
        "status": "queued",
        "coordinator_task_id": coordinator_task.id if hasattr(coordinator_task, 'id') else None,
        "expected_tasks": len(images),
        "visage_api_url": visage_api_url,
        "message": "Visage batch job created with custom API endpoint"
    }

def create_single_visage_task_with_api_url(
    image_data: str,
    visage_api_url: str,
    threshold: float = 0.5,
    additional_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a single Visage face identification task with specified API URL
    
    Now creates a job for every task to maintain proper Jobs → Tasks hierarchy.
    
    Args:
        image_data: Base64 encoded image data or image URL
        visage_api_url: External Visage API endpoint URL
        threshold: Recognition threshold (0.0-1.0)
        additional_params: Extra parameters for Visage API (can include entity tracking)
        
    Returns:
        Dictionary containing task_id, job_id and status information
    """
    from Database.data.visage_adapter import VisageJobTypes
    
    adapter = VisageDatabaseAdapter()
    
    # Prepare input data with entity tracking if provided
    input_data = {
        "image": image_data,
        "threshold": threshold,
        "visage_api_url": visage_api_url,
        "additional_params": additional_params or {}
    }
    
    # Extract entity tracking information from additional_params
    entity_type = None
    entity_id = None
    
    if additional_params:
        # Store entity information directly in input_data for easy access
        if additional_params.get("entity_type"):
            input_data["entity_type"] = additional_params["entity_type"]
            entity_type = additional_params["entity_type"]
        if additional_params.get("entity_id"):
            input_data["entity_id"] = additional_params["entity_id"]
            entity_id = additional_params["entity_id"]
        
        # Also support legacy field patterns for backward compatibility
        if additional_params.get("stash_image_id"):
            input_data["entity_type"] = "image"
            input_data["entity_id"] = additional_params["stash_image_id"]
            input_data["image_id"] = additional_params["stash_image_id"]  # Keep for backward compat
            entity_type = "image"
            entity_id = additional_params["stash_image_id"]
        elif additional_params.get("stash_scene_id"):
            input_data["entity_type"] = "scene"
            input_data["entity_id"] = additional_params["stash_scene_id"]
            input_data["scene_id"] = additional_params["stash_scene_id"]  # Keep for backward compat
            entity_type = "scene"
            entity_id = additional_params["stash_scene_id"]
    
    # Create a job for this single task (ensures proper hierarchy)
    entity_display = f"{entity_type.title()} | {entity_id}" if entity_type and entity_id else "Single Analysis"
    job_name = f"Face Analysis: {entity_display}"
    
    job_id = adapter.create_job(
        job_type=VisageJobTypes.SINGLE_FACE_IDENTIFICATION,
        job_name=job_name,
        job_config={
            "threshold": threshold,
            "visage_api_url": visage_api_url,
            "additional_params": additional_params or {},
            "entity_type": entity_type,
            "entity_id": entity_id,
            "task_count": 1
        },
        user_id=additional_params.get("user_id") if additional_params else None,
        session_id=additional_params.get("session_id") if additional_params else None
    )
    
    # Create individual task linked to the job
    task_id = adapter.create_task(
        task_type=VisageTaskTypes.FACE_IDENTIFY,
        input_data=input_data,
        job_id=job_id,  # Link task to job
        priority=7
    )
    
    # Update job with task ID
    adapter.add_tasks_to_job(job_id, [task_id])
    
    # Queue the task
    queued_task = visage_face_identify_task.schedule(args=({
        "task_id": task_id,
        "input_data": input_data  # Use the same input_data with entity tracking
    },), delay=0)
    
    return {
        "task_id": task_id,
        "job_id": job_id,
        "status": "queued", 
        "huey_task_id": queued_task.id if hasattr(queued_task, 'id') else None,
        "visage_api_url": visage_api_url,
        "message": f"Visage task created within job {job_id}"
    }