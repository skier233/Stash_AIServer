# =============================================================================
# Scene Analysis Frontend Adapter - Huey Task Processor
# =============================================================================

import logging
import time
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
from huey_config import huey
from Database.data.scene_analysis_adapter import SceneAnalysisDatabaseAdapter
from api.SceneAnalysisAdapter import call_scene_analysis_api
from websocket_broadcaster import WebSocketBroadcaster

logger = logging.getLogger(__name__)

@huey.task()
def scene_analysis_task(task_data: Dict[str, Any]):
    """
    Process scene analysis task using Huey queue system
    
    Args:
        task_data: Dictionary containing task information
            - task_id: Unique task identifier
            - input_data: Task input data including content and configuration
    """
    task_id = task_data.get("task_id")
    input_data = task_data.get("input_data", {})
    
    logger.info(f"Starting scene analysis task: {task_id}")
    
    # Initialize database adapter
    adapter = SceneAnalysisDatabaseAdapter()
    broadcaster = WebSocketBroadcaster()
    
    try:
        # Update task status to running
        adapter.update_task_status(task_id, "running")
        
        # Broadcast task started
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="scene_analysis",
            task_type="scene_analyze_scene",
            status="running",
            message="Scene analysis started"
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
        
        # Call scene analysis API
        logger.info(f"Calling scene analysis API: {api_endpoint}")
        api_result = asyncio.run(call_scene_analysis_api(api_endpoint, content_data, config))
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Prepare result data
        result_data = {
            **api_result,
            "processing_time_ms": processing_time_ms,
            "api_endpoint": api_endpoint,
            "config": config
        }
        
        # Store results in scene_analysis_results table
        adapter.store_result(
            task_id=task_id,
            result_data=result_data,
            job_id=input_data.get("job_id"),
            stash_content_id=stash_content_id,
            stash_content_title=stash_content_title
        )
        
        # Update task status to completed
        adapter.update_task_status(task_id, "completed", {
            "success": True,
            "processing_time_ms": processing_time_ms,
            "scenes_count": len(result_data.get("scenes", [])),
            "keyframes_count": len(result_data.get("keyframes", [])),
            "has_audio": bool(result_data.get("audio")),
            "api_endpoint": api_endpoint
        })
        
        # Broadcast task completed
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="scene_analysis",
            task_type="scene_analyze_scene",
            status="completed",
            output_json=result_data,
            processing_time_ms=processing_time_ms,
            message=f"Scene analysis completed - {len(result_data.get('scenes', []))} scenes detected"
        )
        
        logger.info(f"Scene analysis task completed successfully: {task_id}")
        
    except Exception as e:
        logger.error(f"Scene analysis task failed: {task_id} - {str(e)}")
        
        # Update task status to failed
        adapter.update_task_status(task_id, "failed", {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__
        })
        
        # Broadcast task failed
        broadcaster.broadcast_task_update(
            task_id=task_id,
            adapter_name="scene_analysis", 
            task_type="scene_analyze_scene",
            status="failed",
            error=str(e),
            message=f"Scene analysis failed: {str(e)}"
        )
        
        raise