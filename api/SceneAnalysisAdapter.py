# =============================================================================
# Scene Analysis Adapter - AI Service Integration
# =============================================================================

import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from Database.data.scene_analysis_adapter import SceneAnalysisDatabaseAdapter, SceneAnalysisTaskTypes

logger = logging.getLogger(__name__)

async def call_scene_analysis_api(api_endpoint: str, content_data: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call external scene analysis API with content data
    
    Args:
        api_endpoint: URL of the scene analysis API
        content_data: Base64 encoded content data (could be image or video)
        config: Configuration parameters
        
    Returns:
        Dict containing API response data
    """
    try:
        payload = {
            "content": content_data,
            "extract_keyframes": config.get("extract_keyframes", False),
            "analyze_audio": config.get("analyze_audio", False),
            "scene_detection": config.get("scene_detection", True),
            "object_detection": config.get("object_detection", True),
            "max_scenes": config.get("max_scenes", 10),
            "confidence_threshold": config.get("confidence_threshold", 0.5)
        }
        
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout for scene analysis
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"Calling scene analysis API: {api_endpoint}")
            
            async with session.post(api_endpoint, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info("Scene analysis API call successful")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Scene analysis API error {response.status}: {error_text}")
                    raise Exception(f"API call failed with status {response.status}: {error_text}")
                    
    except asyncio.TimeoutError:
        logger.error("Scene analysis API call timed out")
        raise Exception("Scene analysis API call timed out after 300 seconds")
    except Exception as e:
        logger.error(f"Error calling scene analysis API: {e}")
        raise

def create_scene_analysis_task_with_config(
    content_data: str,
    api_endpoint: str,
    stash_content_id: Optional[str] = None,
    stash_content_title: Optional[str] = None,
    stash_metadata: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a scene analysis task with the given configuration
    
    Args:
        content_data: Base64 encoded content data
        api_endpoint: URL of the scene analysis API
        stash_content_id: Stash content ID for reference
        stash_content_title: Content title from Stash
        stash_metadata: Additional metadata from Stash
        config: Task configuration parameters
        
    Returns:
        Dict containing task creation result
    """
    try:
        from api.SceneAnalysisFrontendAdapter import scene_analysis_task
        
        config = config or {}
        stash_metadata = stash_metadata or {}
        
        # Create database adapter
        adapter = SceneAnalysisDatabaseAdapter()
        
        # Create task in database
        task_id = adapter.create_task(
            task_type=SceneAnalysisTaskTypes.ANALYZE_SCENE,
            input_data={
                "content": content_data,
                "api_endpoint": api_endpoint,
                "stash_content_id": stash_content_id,
                "stash_content_title": stash_content_title,
                "stash_metadata": stash_metadata,
                "config": config
            },
            priority=config.get("priority", 5)
        )
        
        # Queue the task for processing
        scene_analysis_task.schedule(args=({
            "task_id": task_id,
            "input_data": {
                "content": content_data,
                "api_endpoint": api_endpoint,
                "stash_content_id": stash_content_id,
                "stash_content_title": stash_content_title,
                "stash_metadata": stash_metadata,
                "config": config
            }
        },), delay=0)
        
        logger.info(f"Scene analysis task created: {task_id}")
        
        return {
            "success": True,
            "task_id": task_id,
            "status": "queued",
            "message": "Scene analysis task created and queued for processing",
            "api_endpoint": api_endpoint,
            "config": config
        }
        
    except Exception as e:
        logger.error(f"Error creating scene analysis task: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to create scene analysis task"
        }