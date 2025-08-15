# =============================================================================
# Content Analysis Adapter - AI Service Integration
# =============================================================================

import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from Database.data.content_analysis_adapter import ContentAnalysisDatabaseAdapter, ContentAnalysisTaskTypes

logger = logging.getLogger(__name__)

async def call_content_analysis_api(api_endpoint: str, image_data: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call external content analysis API with image data
    
    Args:
        api_endpoint: URL of the content analysis API
        image_data: Base64 encoded image data
        config: Configuration parameters
        
    Returns:
        Dict containing API response data
    """
    try:
        payload = {
            "image": image_data,
            "include_tags": config.get("include_tags", True),
            "include_description": config.get("include_description", True),
            "confidence_threshold": config.get("confidence_threshold", 0.5),
            "max_tags": config.get("max_tags", 20),
            "language": config.get("language", "en")
        }
        
        timeout = aiohttp.ClientTimeout(total=120)  # 2 minute timeout
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"Calling content analysis API: {api_endpoint}")
            
            async with session.post(api_endpoint, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info("Content analysis API call successful")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"Content analysis API error {response.status}: {error_text}")
                    raise Exception(f"API call failed with status {response.status}: {error_text}")
                    
    except asyncio.TimeoutError:
        logger.error("Content analysis API call timed out")
        raise Exception("Content analysis API call timed out after 120 seconds")
    except Exception as e:
        logger.error(f"Error calling content analysis API: {e}")
        raise

def create_content_analysis_task_with_config(
    image_data: str,
    api_endpoint: str,
    stash_image_id: Optional[str] = None,
    stash_image_title: Optional[str] = None,
    stash_metadata: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a content analysis task with the given configuration
    
    Args:
        image_data: Base64 encoded image data
        api_endpoint: URL of the content analysis API
        stash_image_id: Stash image ID for reference
        stash_image_title: Image title from Stash
        stash_metadata: Additional metadata from Stash
        config: Task configuration parameters
        
    Returns:
        Dict containing task creation result
    """
    try:
        from api.ContentAnalysisFrontendAdapter import content_analysis_task
        
        config = config or {}
        stash_metadata = stash_metadata or {}
        
        # Create database adapter
        adapter = ContentAnalysisDatabaseAdapter()
        
        # Create task in database
        task_id = adapter.create_task(
            task_type=ContentAnalysisTaskTypes.ANALYZE_CONTENT,
            input_data={
                "image": image_data,
                "api_endpoint": api_endpoint,
                "stash_image_id": stash_image_id,
                "stash_image_title": stash_image_title,
                "stash_metadata": stash_metadata,
                "config": config
            },
            priority=config.get("priority", 5)
        )
        
        # Queue the task for processing
        content_analysis_task.schedule(args=({
            "task_id": task_id,
            "input_data": {
                "image": image_data,
                "api_endpoint": api_endpoint,
                "stash_image_id": stash_image_id,
                "stash_image_title": stash_image_title,
                "stash_metadata": stash_metadata,
                "config": config
            }
        },), delay=0)
        
        logger.info(f"Content analysis task created: {task_id}")
        
        return {
            "success": True,
            "task_id": task_id,
            "status": "queued",
            "message": "Content analysis task created and queued for processing",
            "api_endpoint": api_endpoint,
            "config": config
        }
        
    except Exception as e:
        logger.error(f"Error creating content analysis task: {e}")
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to create content analysis task"
        }