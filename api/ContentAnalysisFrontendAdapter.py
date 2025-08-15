# =============================================================================
# Content Analysis Frontend Adapter - Huey Task Processor
# =============================================================================

import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from huey_config import huey
from Database.data.content_analysis_adapter import ContentAnalysisDatabaseAdapter
from api.ContentAnalysisAdapter import call_content_analysis_api
from websocket_broadcaster import WebSocketBroadcaster

logger = logging.getLogger(__name__)

@huey.task()
def content_analysis_task(task_data: Dict[str, Any]):
    """
    Process content analysis task using Huey queue system
    
    Args:
        task_data: Dictionary containing task information
            - task_id: Unique task identifier
            - input_data: Task input data including image and configuration
    """
    task_id = task_data.get("task_id")
    input_data = task_data.get("input_data", {})
    
    logger.info(f"Starting content analysis task: {task_id}")
    
    # Initialize database adapter
    adapter = ContentAnalysisDatabaseAdapter()
    broadcaster = WebSocketBroadcaster()
    
    try:
        # Update task status to running
        adapter.update_task_status(task_id, "running")
        
        # Broadcast task started
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="content_analysis",
            task_type="content_analyze_content",
            status="running",
            message="Content analysis started"
        )
        
        # Extract task parameters
        image_data = input_data.get("image")
        api_endpoint = input_data.get("api_endpoint")
        config = input_data.get("config", {})
        stash_image_id = input_data.get("stash_image_id")
        stash_image_title = input_data.get("stash_image_title")
        stash_metadata = input_data.get("stash_metadata", {})
        
        if not image_data:
            raise ValueError("No image data provided")
        
        if not api_endpoint:
            raise ValueError("No API endpoint provided")
        
        # Record start time
        start_time = time.time()
        
        # Call content analysis API
        logger.info(f"Calling content analysis API: {api_endpoint}")
        api_result = asyncio.run(call_content_analysis_api(api_endpoint, image_data, config))
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Prepare result data
        result_data = {
            **api_result,
            "processing_time_ms": processing_time_ms,
            "api_endpoint": api_endpoint,
            "config": config
        }
        
        # Store results in content_analysis_results table
        adapter.store_result(
            task_id=task_id,
            result_data=result_data,
            job_id=input_data.get("job_id"),
            stash_image_id=stash_image_id,
            stash_image_title=stash_image_title
        )
        
        # Update task status to completed
        adapter.update_task_status(task_id, "completed", {
            "success": True,
            "processing_time_ms": processing_time_ms,
            "tags_count": len(result_data.get("tags", [])),
            "has_description": bool(result_data.get("descriptions")),
            "api_endpoint": api_endpoint
        })
        
        # Broadcast task completed
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="content_analysis",
            task_type="content_analyze_content",
            status="completed",
            output_json=result_data,
            processing_time_ms=processing_time_ms,
            message=f"Content analysis completed - {len(result_data.get('tags', []))} tags generated"
        )
        
        logger.info(f"Content analysis task completed successfully: {task_id}")
        
    except Exception as e:
        logger.error(f"Content analysis task failed: {task_id} - {str(e)}")
        
        # Update task status to failed
        adapter.update_task_status(task_id, "failed", {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })
        
        # Broadcast task failed
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="content_analysis", 
            task_type="content_analyze_content",
            status="failed",
            error=str(e),
            message=f"Content analysis failed: {str(e)}"
        )
        
        raise