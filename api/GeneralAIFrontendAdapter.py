# =============================================================================
# General AI Frontend Adapter - Huey Task Processor
# =============================================================================

import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from huey_config import huey
from Database.data.general_ai_adapter import GeneralAIDatabaseAdapter
from api.GeneralAIAdapter import call_general_ai_api
from websocket_broadcaster import WebSocketBroadcaster

logger = logging.getLogger(__name__)

@huey.task()
def general_ai_task(task_data: Dict[str, Any]):
    """
    Process general AI task using Huey queue system
    
    This task processor can handle any AI service by using a plugin-style approach.
    It dynamically processes tasks based on the service_type parameter.
    
    Args:
        task_data: Dictionary containing task information
            - task_id: Unique task identifier
            - service_type: Type of AI service (e.g., "custom_nlp", "image_enhance")
            - input_data: Task input data including content and configuration
    """
    task_id = task_data.get("task_id")
    service_type = task_data.get("service_type", "unknown")
    input_data = task_data.get("input_data", {})
    
    logger.info(f"Starting general AI task for {service_type}: {task_id}")
    
    # Initialize database adapter
    adapter = GeneralAIDatabaseAdapter()
    broadcaster = WebSocketBroadcaster()
    
    try:
        # Update task status to running
        adapter.update_task_status(task_id, "running")
        
        # Broadcast task started
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="general_ai",
            task_type=f"general_ai_{service_type}",
            status="running",
            message=f"{service_type} processing started"
        )
        
        # Extract task parameters
        content_data = input_data.get("content")
        api_endpoint = input_data.get("api_endpoint")
        config = input_data.get("config", {})
        stash_content_id = input_data.get("stash_content_id")
        stash_content_title = input_data.get("stash_content_title")
        stash_metadata = input_data.get("stash_metadata", {})
        
        if not content_data:
            raise ValueError("No content data provided")
        
        if not api_endpoint:
            raise ValueError("No API endpoint provided")
        
        # Record start time
        start_time = time.time()
        
        # Call general AI API
        logger.info(f"Calling {service_type} API: {api_endpoint}")
        api_result = asyncio.run(call_general_ai_api(api_endpoint, content_data, service_type, config))
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Prepare result data
        result_data = {
            **api_result,
            "processing_time_ms": processing_time_ms,
            "api_endpoint": api_endpoint,
            "service_type": service_type,
            "config": config
        }
        
        # Store results in general_ai_results table
        adapter.store_result(
            task_id=task_id,
            service_type=service_type,
            result_data=result_data,
            job_id=input_data.get("job_id"),
            stash_content_id=stash_content_id,
            stash_content_title=stash_content_title,
            api_endpoint=api_endpoint
        )
        
        # Update task status to completed
        adapter.update_task_status(task_id, "completed", {
            "success": True,
            "service_type": service_type,
            "processing_time_ms": processing_time_ms,
            "api_endpoint": api_endpoint,
            "has_results": bool(result_data.get("results"))
        })
        
        # Broadcast task completed
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="general_ai",
            task_type=f"general_ai_{service_type}",
            status="completed",
            output_json=result_data,
            processing_time_ms=processing_time_ms,
            message=f"{service_type} processing completed successfully"
        )
        
        logger.info(f"General AI task completed successfully for {service_type}: {task_id}")
        
    except Exception as e:
        logger.error(f"General AI task failed for {service_type}: {task_id} - {str(e)}")
        
        # Update task status to failed
        adapter.update_task_status(task_id, "failed", {
            "success": False,
            "service_type": service_type,
            "error": str(e),
            "error_type": type(e).__name__
        })
        
        # Broadcast task failed
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="general_ai", 
            task_type=f"general_ai_{service_type}",
            status="failed",
            error=str(e),
            message=f"{service_type} processing failed: {str(e)}"
        )
        
        raise