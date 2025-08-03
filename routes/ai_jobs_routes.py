from datetime import datetime
import logging
from typing import Optional

from fastapi import APIRouter, HTTPException

from database.interactions_service import interactions_service
from database.models import AIActionType, AIJobCreate, AIJobHistoryQuery, AIJobResponse, AITestCreate, AITestResponse, EntityType, ProcessingStatus


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/ai-jobs", tags=["ai-jobs"])


@router.get("/history")
async def get_ai_job_history(
    entity_type: Optional[str] = None,
    entity_id: Optional[str] = None,
    action_type: Optional[str] = None,
    status: Optional[str] = None,
    job_name: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    """Get AI job history with optional filters"""
    try:
        # Build query object
        query = AIJobHistoryQuery(
            entity_type=EntityType(entity_type) if entity_type else None,
            entity_id=entity_id,
            action_type=AIActionType(action_type) if action_type else None,
            status=ProcessingStatus(status) if status else None,
            job_name=job_name,
            limit=min(limit, 100),  # Cap at 100
            offset=offset
        )
        
        history = interactions_service.query_ai_job_history(query)
        return history.dict()
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {e}")
    except Exception as e:
        logger.error(f"Failed to get AI job history: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve AI job history")
    
@router.get("/{job_id}/tests")
async def get_job_tests(job_id: str):
    """Get all tests for a specific job"""
    try:
        # First verify job exists
        job_info = interactions_service.get_ai_job(job_id)
        if not job_info:
            raise HTTPException(status_code=404, detail=f"AI job {job_id} not found")
        
        tests = interactions_service.get_tests_for_job(job_id)
        return {"job_id": job_id, "tests": [test.dict() for test in tests]}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get tests for job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve job tests")



def unregister_batch_job(job_id: str):
    """Unregister a batch job when completed"""
    global _active_batch_jobs
    _active_batch_jobs.discard(job_id)
    
    # Disable batch processing mode if no active batch jobs

    # TODO
    # if service_registry and not _active_batch_jobs:
    #     service_registry._batch_processing_active = False
    #     logger.info(f"Batch processing deactivated after job {job_id} completion (0 active batch jobs)")

@router.post("/{job_id}/cancel")
async def cancel_ai_job(job_id: str):
    """Cancel an AI job and all its pending/processing tests"""
    try:
        result = interactions_service.cancel_ai_job(job_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"AI job {job_id} not found or cannot be cancelled")
        
        # Unregister batch job when cancelled
        unregister_batch_job(job_id)
        
        return {
            "success": True,
            "message": f"Successfully cancelled AI job {job_id}",
            "job": result.dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel AI job {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel AI job")
    
@router.get("/{job_id}")
async def get_ai_job_details(job_id: str, include_results: bool = False, include_tests: bool = False):
    """Get detailed information about a specific AI job"""
    try:
        job_info = interactions_service.get_ai_job(job_id)
        if not job_info:
            raise HTTPException(status_code=404, detail=f"AI job {job_id} not found")
        
        result = job_info.dict()
        
        if include_tests:
            tests = interactions_service.get_tests_for_job(job_id)
            result["tests"] = [test.dict() for test in tests]
        
        if include_results:
            results = interactions_service.get_job_results(job_id)
            if results:
                result["detailed_results"] = results
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI job details for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve AI job details")
    
@router.post("", response_model=AIJobResponse)
async def create_ai_job(job_data: AIJobCreate):
    """Create a new AI job"""
    try:
        job_response = interactions_service.create_ai_job(job_data)
        return job_response
    except Exception as e:
        logger.error(f"Failed to create AI job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create AI job")

@router.post("/{job_id}/tests", response_model=AITestResponse)
async def create_ai_test(job_id: str, test_data: AITestCreate):
    """Create a new AI test within a job"""
    try:
        test_response = interactions_service.create_ai_test(job_id, test_data)
        return test_response
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create AI test: {e}")
        raise HTTPException(status_code=500, detail="Failed to create AI test")