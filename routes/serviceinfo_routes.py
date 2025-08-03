from datetime import datetime
import logging
from fastapi import APIRouter

from schemas.api_schema import HealthCheckResponse


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["serviceinfo"])

@router.get("/health", response_model=HealthCheckResponse)
async def health_check():
    """System health check endpoint"""
    start_time = datetime.utcnow()
    
    # Check service registry status

    # TODO: Deal with service health checks later
    healthy_services = [""]
    total_services = 1
    
    # Calculate uptime (placeholder - you'd track this in production)
    uptime = 3600.0  # 1 hour placeholder
    
    # Get active queue information from database
    #TODO
    # queue_info = get_active_queue_status()
    
    return HealthCheckResponse(
        success=True,
        message=f"StashAI Server is healthy. {len(healthy_services)}/{total_services} services available",
        service_name="stash-ai-server",
        status="healthy" if len(healthy_services) > 0 else "degraded",
        version="1.0.0",
        uptime=uptime,
        metrics={
            "total_services": total_services,
            "healthy_services": len(healthy_services),
            # "active_batch_jobs": queue_info.get("active_jobs_count", 0),
            # "queue_status": queue_info
        }
    )