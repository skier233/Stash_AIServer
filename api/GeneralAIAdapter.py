# =============================================================================
# General AI Adapter - Plugin-style AI Service Integration
# =============================================================================

import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional
from Database.data.general_ai_adapter import GeneralAIDatabaseAdapter, GeneralAITaskTypes

logger = logging.getLogger(__name__)

async def call_general_ai_api(api_endpoint: str, content_data: str, service_type: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Call external AI API with content data using a generic approach
    
    Args:
        api_endpoint: URL of the AI API
        content_data: Base64 encoded content data
        service_type: Type of AI service being called
        config: Configuration parameters
        
    Returns:
        Dict containing API response data
    """
    try:
        # Create a generic payload that most AI APIs can understand
        payload = {
            "data": content_data,
            "content": content_data,  # Alternative field name
            "image": content_data,    # For image-based APIs
            "service_type": service_type,
            "config": config,
            **config  # Include all config parameters at root level
        }
        
        # Determine timeout based on service type
        timeout_seconds = 120
        if service_type in ["video_analysis", "scene_analysis"]:
            timeout_seconds = 300
        elif service_type in ["large_model", "llm"]:
            timeout_seconds = 180
            
        timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        
        async with aiohttp.ClientSession(timeout=timeout) as session:
            logger.info(f"Calling {service_type} API: {api_endpoint}")
            
            async with session.post(api_endpoint, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    logger.info(f"{service_type} API call successful")
                    return result
                else:
                    error_text = await response.text()
                    logger.error(f"{service_type} API error {response.status}: {error_text}")
                    raise Exception(f"API call failed with status {response.status}: {error_text}")
                    
    except asyncio.TimeoutError:
        logger.error(f"{service_type} API call timed out")
        raise Exception(f"{service_type} API call timed out after {timeout_seconds} seconds")
    except Exception as e:
        logger.error(f"Error calling {service_type} API: {e}")
        raise

def create_general_ai_task_with_config(
    service_type: str,
    content_data: str,
    api_endpoint: str,
    stash_content_id: Optional[str] = None,
    stash_content_title: Optional[str] = None,
    stash_metadata: Optional[Dict[str, Any]] = None,
    config: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Create a general AI task with the given configuration
    
    This adapter supports any AI service by using a plugin-style architecture.
    New AI services can be integrated without modifying this code.
    
    Args:
        service_type: Type of AI service (e.g., "custom_nlp", "image_enhance")
        content_data: Base64 encoded content data
        api_endpoint: URL of the AI API
        stash_content_id: Stash content ID for reference
        stash_content_title: Content title from Stash
        stash_metadata: Additional metadata from Stash
        config: Task configuration parameters
        
    Returns:
        Dict containing task creation result
    """
    try:
        from api.GeneralAIFrontendAdapter import general_ai_task
        
        config = config or {}
        stash_metadata = stash_metadata or {}
        
        # Create database adapter
        adapter = GeneralAIDatabaseAdapter()
        
        # Create task in database
        task_id = adapter.create_task(
            task_type=GeneralAITaskTypes.GENERAL_PROCESSING,
            service_type=service_type,
            input_data={
                "content": content_data,
                "api_endpoint": api_endpoint,
                "service_type": service_type,
                "stash_content_id": stash_content_id,
                "stash_content_title": stash_content_title,
                "stash_metadata": stash_metadata,
                "config": config
            },
            priority=config.get("priority", 5)
        )
        
        # Queue the task for processing
        general_ai_task.schedule(args=({
            "task_id": task_id,
            "service_type": service_type,
            "input_data": {
                "content": content_data,
                "api_endpoint": api_endpoint,
                "service_type": service_type,
                "stash_content_id": stash_content_id,
                "stash_content_title": stash_content_title,
                "stash_metadata": stash_metadata,
                "config": config
            }
        },), delay=0)
        
        logger.info(f"General AI task created for {service_type}: {task_id}")
        
        return {
            "success": True,
            "task_id": task_id,
            "service_type": service_type,
            "status": "queued",
            "message": f"{service_type} task created and queued for processing",
            "api_endpoint": api_endpoint,
            "config": config
        }
        
    except Exception as e:
        logger.error(f"Error creating general AI task for {service_type}: {e}")
        return {
            "success": False,
            "error": str(e),
            "service_type": service_type,
            "message": f"Failed to create {service_type} task"
        }