# =============================================================================
# StashAI Server - Main FastAPI Gateway Service
# =============================================================================

import asyncio
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple

import uvicorn
from fastapi import FastAPI, HTTPException, Request, Depends, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from schemas.api_schema import (
    # Request/Response models
    SceneIdentificationRequest, GalleryIdentificationRequest, 
    FacialRecognitionRequest, FaceComparisonRequest,
    FacialRecognitionResponse, FaceComparisonResponse,
    ContentAnalysisRequest, ContentAnalysisResponse,
    BatchRequest, BatchResponse, BatchJobStatus,
    HealthCheckResponse, ServiceInfo, APIError,
    FaceInfo, StashEntity,
    
    # Enums
    ServiceType, ProcessingStatus
)
from services.service_registry import ServiceRegistry, ServiceDiscovery, BatchProcessingContext, create_default_registry
from services.visage_adapter import VisageAdapter, create_visage_adapter
from simple_queue import simple_queue, JobStatus

# Database imports
from database.database import initialize_database, get_db, db_manager
from database.interactions_service import interactions_service
from database.migrations import verify_database_version, run_startup_migration, CURRENT_SCHEMA_VERSION
from database.models import (
    AIJobCreate, AIJobUpdate, AIJobResponse, AIJobHistoryQuery, AIJobHistoryResponse,
    AITestCreate, AITestUpdate, AITestResponse,
    InteractionCreate, InteractionResponse, EntityType, AIActionType, ProcessingStatus, AIModel
)

# =============================================================================
# Logging Configuration
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# Database Migration Functions
# =============================================================================

async def verify_and_migrate_database():
    """Verify database version and run migrations on startup"""
    try:
        # Get database path from DATABASE_URL (for SQLite databases)
        from database.database import DATABASE_URL
        if DATABASE_URL.startswith("sqlite:///"):
            database_path = DATABASE_URL.replace("sqlite:///", "")
        else:
            # For non-SQLite databases, use a fallback or skip migration
            logger.info("Non-SQLite database detected - skipping file-based migration")
            return
            
        logger.info(f"Using database path: {database_path}")
        
        # Verify current database status
        db_status = verify_database_version(database_path)
        
        logger.info(f"Database version check:")
        logger.info(f"  Current version: {db_status['current_version']}")
        logger.info(f"  Target version: {db_status['target_version']}")
        logger.info(f"  Needs migration: {db_status['needs_migration']}")
        logger.info(f"  Schema tables exist: {db_status['schema_tables_exist']}")
        
        # Run migration if needed
        if db_status['needs_migration']:
            logger.info("Database migration required - starting migration process")
            
            migration_success = run_startup_migration(database_path)
            
            if migration_success:
                logger.info(f"✅ Database successfully migrated to version {CURRENT_SCHEMA_VERSION}")
                
                # Verify migration completed successfully
                updated_status = verify_database_version(database_path)
                if updated_status['current_version'] == CURRENT_SCHEMA_VERSION:
                    logger.info("✅ Migration verification passed")
                else:
                    logger.warning(f"⚠️ Migration verification failed - expected {CURRENT_SCHEMA_VERSION}, got {updated_status['current_version']}")
            else:
                logger.error("❌ Database migration failed - server may have compatibility issues")
                logger.error("Please check migration logs and database backups")
                # Don't raise exception - allow server to start with legacy support
        else:
            logger.info(f"✅ Database is up to date (version {db_status['current_version']})")
        
        # Log table status for debugging
        if not db_status['schema_tables_exist']:
            logger.info("Schema tables not fully available - running in legacy compatibility mode")
            missing_tables = [table for table, exists in db_status['table_status'].items() if not exists]
            if missing_tables:
                logger.info(f"Missing schema tables: {missing_tables}")
        else:
            logger.info("✅ All schema tables are available")
            
    except Exception as e:
        logger.error(f"Database verification/migration failed: {e}")
        import traceback
        logger.error(f"Migration error traceback: {traceback.format_exc()}")
        # Don't raise - allow server to continue with legacy support

# =============================================================================
# Global State
# =============================================================================

service_registry: Optional[ServiceRegistry] = None
service_discovery: Optional[ServiceDiscovery] = None
batch_jobs: Dict[str, Dict[str, Any]] = {}

# Queue activity tracking for adaptive health checks
_last_queue_activity = datetime.utcnow()
_active_jobs_cache = []

# Job-based batch processing state tracking
_active_batch_jobs = set()  # Track active batch job IDs

# =============================================================================
# Application Lifecycle Management
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown"""
    global service_registry, service_discovery
    
    logger.info("Starting StashAI Server...")
    
    # Initialize database first
    try:
        initialize_database()
        logger.info("Database initialized successfully")
        
        # Verify database version and run migrations if needed
        await verify_and_migrate_database()
        
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise
    
    # Initialize service registry
    service_registry = create_default_registry()
    service_discovery = ServiceDiscovery(service_registry)
    
    # Start service registry (health monitoring)
    await service_registry.start()
    
    # Start simple queue
    simple_queue.start()
    logger.info("Simple queue started")
    
    # Restore batch processing state from database
    restore_batch_processing_state()
    
    logger.info("StashAI Server started successfully")
    logger.info(f"Registered services: {list(service_registry.services.keys())}")
    
    yield
    
    # Cleanup
    logger.info("Shutting down StashAI Server...")
    
    # Stop simple queue
    simple_queue.stop()
    logger.info("Simple queue stopped")
    
    if service_registry:
        await service_registry.stop()
    logger.info("StashAI Server shutdown complete")

# =============================================================================
# FastAPI Application Setup
# =============================================================================

app = FastAPI(
    title="StashAI Server",
    description="Unified API gateway for AI services in Stash",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your needs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["*"]  # Configure based on your needs
)

# =============================================================================
# WebSocket Connection Manager
# =============================================================================

class ConnectionManager:
    """Manages WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Failed to send personal message: {e}")
            self.disconnect(websocket)
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        if not self.active_connections:
            return
            
        disconnected = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"Failed to broadcast to connection: {e}")
                disconnected.append(connection)
        
        # Clean up disconnected connections
        for conn in disconnected:
            self.disconnect(conn)

# Global connection manager
websocket_manager = ConnectionManager()

# Connect websocket manager to simple queue for real-time updates
simple_queue.set_websocket_manager(websocket_manager)

# =============================================================================
# Request Processing Helpers
# =============================================================================

def generate_request_id() -> str:
    """Generate a unique request ID"""
    return str(uuid.uuid4())

async def get_service_for_request(service_type: ServiceType, capability: Optional[str] = None, allow_busy: bool = True):
    """Get an available service for a request with enhanced resilience"""
    if not service_discovery:
        raise HTTPException(status_code=503, detail="Service discovery not available")
    
    service = service_discovery.find_best_service(service_type, capability, allow_busy=allow_busy)
    if not service:
        available_services = service_registry.get_services_by_type(service_type) if service_registry else []
        service_names = [(s.name, s.status.value) for s in available_services]
        
        # Provide more informative error message
        if available_services:
            service_status_msg = ", ".join([f"{name}({status})" for name, status in service_names])
            detail = f"No available {service_type} services. Status: {service_status_msg}"
        else:
            detail = f"No {service_type} services registered"
            
        raise HTTPException(status_code=503, detail=detail)
    
    return service

async def create_visage_client() -> VisageAdapter:
    """Create a Visage adapter client"""
    visage_service = await get_service_for_request(ServiceType.FACIAL_RECOGNITION, "facial_recognition")
    return create_visage_adapter(base_url=visage_service.endpoint)

def create_ai_job_and_test(entity_type: EntityType, entity_id: str, action_type: AIActionType, 
                          entity_name: str = None, entity_filepath: str = None, request_data: Dict[str, Any] = None, 
                          job_id: str = None, test_id: str = None) -> Tuple[str, str]:
    """Create AI job and test for tracking processing"""
    if test_id is None:
        test_id = generate_request_id()
    
    # Only create a new job if job_id is not provided (not a batch operation)
    if job_id is None:
        job_id = generate_request_id()
        
        # Create AI job record
        job_data = AIJobCreate(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            action_type=action_type,
            job_config=request_data
        )
        
        job_response = interactions_service.create_ai_job(job_data, job_id)
        logger.info(f"Created AI job {job_id} for {entity_type}:{entity_id}")
    else:
        logger.info(f"Using existing batch job {job_id} for {entity_type}:{entity_id}")
        # Register this as a batch job for batch processing mode
        register_batch_job(job_id)
    
    # Create AI test record
    test_data = AITestCreate(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_filepath=entity_filepath,
        entity_name=entity_name,
        action_type=action_type,
        ai_model=AIModel.VISAGE,
        test_config=request_data
    )
    
    test_response = interactions_service.create_ai_test(job_id, test_data, test_id)
    logger.info(f"Created AI test {test_id} in job {job_id}")
    
    return job_id, test_id

def track_queue_activity(active_jobs_count: int):
    """Track queue activity for adaptive health check intervals"""
    global _last_queue_activity, _active_jobs_cache
    
    if active_jobs_count > 0:
        _last_queue_activity = datetime.utcnow()
    
    _active_jobs_cache = [active_jobs_count]

def get_suggested_polling_interval() -> int:
    """Get suggested polling interval based on queue activity"""
    global _last_queue_activity, _active_jobs_cache
    
    now = datetime.utcnow()
    time_since_activity = (now - _last_queue_activity).total_seconds()
    
    # If there are active jobs, poll aggressively
    if _active_jobs_cache and _active_jobs_cache[0] > 0:
        return 2  # 2 seconds during active processing
    
    # If recent activity (within 2 minutes), poll moderately
    if time_since_activity < 120:
        return 10  # 10 seconds for recent activity
    
    # If no recent activity, poll slowly
    return 30  # 30 seconds when idle

def register_batch_job(job_id: str):
    """Register a batch job as active"""
    global _active_batch_jobs
    _active_batch_jobs.add(job_id)
    
    # Enable batch processing mode if we have active batch jobs
    if service_registry and _active_batch_jobs:
        service_registry._batch_processing_active = True
        logger.info(f"Batch processing activated for job {job_id} ({len(_active_batch_jobs)} active batch jobs)")

def unregister_batch_job(job_id: str):
    """Unregister a batch job when completed"""
    global _active_batch_jobs
    _active_batch_jobs.discard(job_id)
    
    # Disable batch processing mode if no active batch jobs
    if service_registry and not _active_batch_jobs:
        service_registry._batch_processing_active = False
        logger.info(f"Batch processing deactivated after job {job_id} completion (0 active batch jobs)")

def is_batch_processing_active() -> bool:
    """Check if any batch jobs are currently active"""
    global _active_batch_jobs
    return bool(_active_batch_jobs)

def restore_batch_processing_state():
    """Restore batch processing state from database on startup"""
    try:
        # Get all active jobs from database
        active_jobs = interactions_service.get_active_jobs()
        
        # Check which are batch jobs (have more than 1 test)
        for job in active_jobs:
            tests = interactions_service.get_tests_for_job(job.job_id)
            if len(tests) > 1:  # This is a batch job
                register_batch_job(job.job_id)
                logger.info(f"Restored batch job state for {job.job_id} ({len(tests)} tests)")
                
    except Exception as e:
        logger.error(f"Failed to restore batch processing state: {e}")

def get_active_queue_status() -> Dict[str, Any]:
    """Get current queue status from simple_queue (real-time) and database (for tests)"""
    try:
        # Get active jobs from simple_queue (source of truth for currently running jobs)
        simple_queue_active_jobs = []
        for job_id, job in simple_queue.jobs.items():
            if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
                simple_queue_active_jobs.append({
                    'job_id': job.job_id,
                    'job_type': job.job_type,
                    'status': job.status.value,
                    'created_at': job.created_at.isoformat(),
                    'started_at': job.started_at.isoformat() if job.started_at else None,
                    'entity_name': f"{job.job_type.title()} Job {job.job_id[:8]}..."
                })
        
        if not simple_queue_active_jobs:
            # Track no activity
            track_queue_activity(0)
            return {
                "active_jobs": [],  # Empty array for client
                "active_jobs_count": 0,
                "total_tests": 0,
                "completed_tests": 0,
                "failed_tests": 0,
                "suggested_polling_interval": get_suggested_polling_interval()
            }
        
        queue_jobs = []
        total_tests = 0
        completed_tests = 0
        failed_tests = 0
        
        for job_data in simple_queue_active_jobs:
            # Get database job info for additional details
            db_job = None
            tests = []
            try:
                if interactions_service:
                    # Try to get database info for this job
                    db_jobs = interactions_service.get_active_jobs()
                    db_job = next((j for j in db_jobs if j.job_id == job_data['job_id']), None)
                    if db_job:
                        tests = interactions_service.get_tests_for_job(job_data['job_id'])
            except Exception as e:
                logger.warning(f"Failed to get database info for job {job_data['job_id']}: {e}")
            
            job_completed = len([t for t in tests if t.status == 'completed'])
            job_failed = len([t for t in tests if t.status == 'failed'])
            job_total = len(tests)
            
            total_tests += job_total
            completed_tests += job_completed
            failed_tests += job_failed
            
            # Create job info combining simple_queue data with database data
            job_info = {
                "job_id": job_data['job_id'],
                "job_name": db_job.job_name if db_job else f"{job_data['job_type'].title()} Processing",
                "entity_type": db_job.entity_type if db_job else job_data['job_type'],
                "entity_id": db_job.entity_id if db_job else "unknown",
                "entity_name": db_job.entity_name if db_job else job_data['entity_name'],
                "status": job_data['status'],  # Use simple_queue status (real-time)
                "total_items": db_job.total_tests_planned if db_job else 1,
                "successful_items": db_job.tests_passed if db_job else 0,
                "failed_items": db_job.tests_failed if db_job else 0,
                "progress_percentage": db_job.progress_percentage if db_job else 0,
                "progress": {
                    "current": job_completed + job_failed,  # Total processed
                    "total": job_total
                },
                "jobProgress": {  # For compatibility with existing client code
                    "completed": job_completed,
                    "failed": job_failed,
                    "total": job_total
                },
                "created_at": job_data['created_at'],
                "started_at": job_data['started_at'],
                "tests": tests[:5] if tests else []  # Limit to first 5 tests  
            }
            queue_jobs.append(job_info)
        
        # Track activity for adaptive polling
        track_queue_activity(len(simple_queue_active_jobs))
        
        # Debug logging for troubleshooting
        logger.debug(f"get_active_queue_status returning {len(simple_queue_active_jobs)} active jobs from simple_queue")
        
        # Get recent completed jobs for result viewing
        recent_completed = interactions_service.get_recent_completed_jobs(limit=10)
        recent_completed_jobs = []
        for job in recent_completed:
            recent_completed_jobs.append({
                "job_id": job.job_id,
                "job_name": job.job_name,
                "entity_type": job.entity_type,
                "entity_id": job.entity_id,
                "entity_name": job.entity_name,
                "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                "total_items": job.total_tests_planned,
                "successful_items": job.tests_passed,
                "has_results": True  # We'll assume completed jobs have results
            })
        
        result = {
            "active_jobs": queue_jobs,  # Array of job objects for client
            "active_jobs_count": len(simple_queue_active_jobs),  # Count for metrics
            "recent_completed_jobs": recent_completed_jobs,  # Recent completed jobs for viewing
            "total_tests": total_tests,
            "completed_tests": completed_tests,
            "failed_tests": failed_tests,
            "suggested_polling_interval": get_suggested_polling_interval()
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get queue status: {e}")
        # Track no activity in error case
        track_queue_activity(0)
        
        return {
            "active_jobs": [],  # Empty array for client
            "active_jobs_count": 0,
            "total_tests": 0,
            "completed_tests": 0,
            "failed_tests": 0,
            "suggested_polling_interval": get_suggested_polling_interval(),
            "error": str(e)
        }

def check_and_complete_job(job_id: str):
    """Check if all tests in a job are complete and mark job as completed if so"""
    try:
        job = interactions_service.get_ai_job(job_id)
        if not job or job.status not in ['pending', 'in_progress']:
            return
        
        tests = interactions_service.get_tests_for_job(job_id)
        if not tests:
            return
        
        completed_tests = len([t for t in tests if t.status == 'completed'])
        failed_tests = len([t for t in tests if t.status == 'failed'])
        total_tests = len(tests)
        
        # Mark job as completed if all tests are done
        if completed_tests + failed_tests >= total_tests:
            job_update = AIJobUpdate(
                status='completed' if completed_tests > 0 else 'failed',
                successful_items=completed_tests,
                failed_items=failed_tests,
                progress_percentage=100.0
            )
            interactions_service.update_ai_job(job_id, job_update)
            logger.info(f"Job {job_id} marked as completed: {completed_tests} successful, {failed_tests} failed")
            
            # Unregister batch job when completed
            unregister_batch_job(job_id)
            
    except Exception as e:
        logger.error(f"Failed to check job completion for {job_id}: {e}")

def complete_ai_test(test_id: str, success: bool, response_data: Dict[str, Any] = None,
                    error_message: str = None, service_name: str = "stash-ai-server",
                    processing_time: float = None):
    """Complete an AI test tracking"""
    
    # Update the test record in database
    if success and response_data:
        interactions_service.complete_ai_test(
            test_id, response_data, service_name, processing_time
        )
    else:
        interactions_service.fail_ai_test(test_id, error_message or "Unknown error")
    
    # Track interaction for both successful AND failed tests (if we have entity data)
    if response_data and "entity" in response_data:
        entity_info = response_data["entity"]
        performers_found = len(response_data.get("performers", []))
        confidence_scores = []
        
        # Handle both PerformerInfo objects and dict responses
        for p in response_data.get("performers", []):
            if hasattr(p, 'confidence'):
                confidence_scores.append(p.confidence)
            elif isinstance(p, dict) and 'confidence' in p:
                confidence_scores.append(p['confidence'])
        
        # Get the database IDs for the job and test using UUIDs
        job_uuid = response_data.get("job_id", "unknown")
        test_uuid = test_id
        
        # Get the database records to extract integer IDs
        job_record = interactions_service.get_ai_job(job_uuid)
        test_record = interactions_service.get_ai_test(test_uuid)
        
        db_job_id = job_record.id if job_record else None
        db_test_id = test_record.id if test_record else None
        
        interaction_data = InteractionCreate(
            entity_type=EntityType(entity_info.get("type", "image")),
            entity_id=entity_info.get("id", "unknown"),
            session_id=f"job_{job_uuid}",
            service="stash_ai_server",
            action_type="facial_recognition",
            metadata={
                "job_uuid": job_uuid,
                "test_uuid": test_uuid,
                "success": success,
                "performers_found": performers_found,
                "confidence_scores": confidence_scores,
                "db_job_id": db_job_id,
                "db_test_id": db_test_id
            }
        )
        
        interactions_service.track_interaction(interaction_data)

# =============================================================================
# Health and System Endpoints
# =============================================================================

@app.get("/api/v1/health", response_model=HealthCheckResponse)
async def health_check():
    """System health check endpoint"""
    start_time = datetime.utcnow()
    
    # Check service registry status
    healthy_services = service_registry.get_healthy_services() if service_registry else []
    total_services = len(service_registry.services) if service_registry else 0
    
    # Calculate uptime (placeholder - you'd track this in production)
    uptime = 3600.0  # 1 hour placeholder
    
    # Service dependency status
    dependencies = {}
    if service_registry:
        for service in service_registry.services.values():
            dependencies[service.name] = service.status.value
    
    processing_time = (datetime.utcnow() - start_time).total_seconds()
    
    # Get active queue information from database
    queue_info = get_active_queue_status()
    
    return HealthCheckResponse(
        success=True,
        message=f"StashAI Server is healthy. {len(healthy_services)}/{total_services} services available",
        service_name="stash-ai-server",
        status="healthy" if len(healthy_services) > 0 else "degraded",
        version="1.0.0",
        uptime=uptime,
        processing_time=processing_time,
        dependencies=dependencies,
        metrics={
            "total_services": total_services,
            "healthy_services": len(healthy_services),
            "active_batch_jobs": queue_info.get("active_jobs_count", 0),
            "queue_status": queue_info
        }
    )

@app.get("/api/v1/database/status")
async def get_database_status():
    """Get database version and migration status"""
    try:
        database_path = db_manager.database_path
        db_status = verify_database_version(database_path)
        
        return {
            "success": True,
            "database_path": database_path,
            "current_version": db_status['current_version'],
            "target_version": db_status['target_version'],
            "schema_up_to_date": not db_status['needs_migration'],
            "schema_available": db_status['schema_tables_exist'],
            "table_status": db_status['table_status'],
            "migration_required": db_status['needs_migration'],
            "schema_compatibility": {
                "legacy_v1_support": True,
                "features_available": db_status['schema_tables_exist'],
                "model_evaluators_available": db_status['table_status'].get('model_evaluators', False)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get database status: {e}")
        return {
            "success": False,
            "error": str(e),
            "database_path": getattr(db_manager, 'database_path', 'unknown'),
            "current_version": "unknown",
            "target_version": CURRENT_SCHEMA_VERSION,
            "schema_up_to_date": False,
            "schema_available": False
        }

@app.get("/api/v1/services", response_model=List[ServiceInfo])
async def list_services():
    """List all registered services"""
    if not service_registry:
        raise HTTPException(status_code=503, detail="Service registry not available")
    
    return service_registry.list_all_services()

@app.get("/api/v1/ai-jobs/evaluation-results")
async def get_jobs_with_evaluation_results(limit: int = 50):
    """Get jobs with detailed evaluation results"""
    try:
        jobs = interactions_service.get_jobs_with_evaluation_results(limit)
        return {"success": True, "jobs": jobs}
    except Exception as e:
        logger.error(f"Failed to get jobs with evaluation results: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve evaluation results")

@app.get("/api/v1/ai-jobs/evaluator-stats")
async def get_model_evaluator_stats():
    """Get model evaluator performance statistics"""
    try:
        stats = interactions_service.get_model_evaluator_stats()
        return {"success": True, "stats": stats}
    except Exception as e:
        logger.error(f"Failed to get evaluator stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve evaluator statistics")

@app.get("/api/v1/ai-jobs/evaluation-trends")
async def get_evaluation_trends(days: int = 30):
    """Get evaluation trends over time"""
    try:
        trends = interactions_service.get_evaluation_trends(days)
        return {"success": True, "trends": trends}
    except Exception as e:
        logger.error(f"Failed to get evaluation trends: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve evaluation trends")

# =============================================================================
# AI Job and Test Management Endpoints
# =============================================================================

@app.get("/api/v1/ai-jobs/history")
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

@app.get("/api/v1/ai-jobs/{job_id}")
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

@app.get("/api/v1/ai-tests/{test_id}")
async def get_ai_test_details(test_id: str):
    """Get detailed information about a specific AI test"""
    try:
        test_info = interactions_service.get_ai_test(test_id)
        if not test_info:
            raise HTTPException(status_code=404, detail=f"AI test {test_id} not found")
        
        return test_info.dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI test details for {test_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve AI test details")

@app.get("/api/v1/ai-tests/{test_id}/results")
async def get_ai_test_results(test_id: str):
    """Get detailed results for a specific AI test including response data"""
    try:
        test_info = interactions_service.get_ai_test(test_id)
        if not test_info:
            raise HTTPException(status_code=404, detail=f"AI test {test_id} not found")
        
        # Return test info with full response data for overlay display
        test_data = test_info.dict()
        logger.info(f"Retrieved test {test_id}: response_data={bool(test_data.get('response_data'))} - Keys: {list(test_data.get('response_data', {}).keys()) if test_data.get('response_data') else 'None'}")
        
        # Transform response data to match overlay format expectations
        if test_data.get('response_data'):
            response = test_data['response_data']
            
            # For single image results (image processing)
            if test_data.get('entity_type') == 'image' and 'performers' in response:
                # Format as single image result
                result = {
                    'success': test_data.get('status') == 'completed',
                    'performers': response.get('performers', []),
                    'entity_id': test_data.get('entity_id'),
                    'entity_type': test_data.get('entity_type'),
                    'test_id': test_id,
                    'processing_time': test_data.get('processing_time'),
                    'confidence_scores': test_data.get('confidence_scores', []),
                    'max_confidence': test_data.get('max_confidence')
                }
                return result
            
            # For gallery results (batch processing)
            elif test_data.get('entity_type') == 'gallery' and 'performers' in response:
                # Format as gallery batch result
                result = {
                    'success': test_data.get('status') == 'completed',
                    'galleryId': test_data.get('entity_id'),
                    'entity_type': test_data.get('entity_type'),
                    'test_id': test_id,
                    'performers': response.get('performers', []),
                    'processingResults': response.get('processingResults', []),
                    'totalImages': len(response.get('processingResults', [])),
                    'processedImages': len([r for r in response.get('processingResults', []) if r.get('success')]),
                    'skippedImages': len([r for r in response.get('processingResults', []) if not r.get('success')]),
                    'totalProcessingTime': test_data.get('processing_time'),
                    'error': test_data.get('error_message') if test_data.get('status') == 'failed' else None
                }
                return result
            
            # For scene results
            elif test_data.get('entity_type') == 'scene' and 'performers' in response:
                # Format as scene batch result
                result = {
                    'success': test_data.get('status') == 'completed',
                    'sceneId': test_data.get('entity_id'),
                    'entity_type': test_data.get('entity_type'),
                    'test_id': test_id,
                    'performers': response.get('performers', []),
                    'processingResults': response.get('processingResults', []),
                    'totalFrames': len(response.get('processingResults', [])),
                    'processedFrames': len([r for r in response.get('processingResults', []) if r.get('success')]),
                    'skippedFrames': len([r for r in response.get('processingResults', []) if not r.get('success')]),
                    'totalProcessingTime': test_data.get('processing_time'),
                    'error': test_data.get('error_message') if test_data.get('status') == 'failed' else None
                }
                return result
        
        # Fallback - return raw test data
        return {
            'success': test_data.get('status') == 'completed',
            'test_id': test_id,
            'entity_id': test_data.get('entity_id'),
            'entity_type': test_data.get('entity_type'),
            'rawResponse': test_data.get('response_data'),
            'error': test_data.get('error_message') if test_data.get('status') == 'failed' else None
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get AI test results for {test_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve AI test results")

@app.get("/api/v1/ai-jobs/{job_id}/tests")
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

@app.post("/api/v1/ai-jobs/{job_id}/cancel")
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

@app.post("/api/v1/ai-tests/{test_id}/cancel")
async def cancel_ai_test(test_id: str):
    """Cancel a specific AI test"""
    try:
        result = interactions_service.cancel_ai_test(test_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"AI test {test_id} not found or cannot be cancelled")
        
        return {
            "success": True,
            "message": f"Successfully cancelled AI test {test_id}",
            "test": result.dict(),
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel AI test {test_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to cancel AI test")

@app.post("/api/v1/ai-jobs", response_model=AIJobResponse)
async def create_ai_job(job_data: AIJobCreate):
    """Create a new AI job"""
    try:
        job_response = interactions_service.create_ai_job(job_data)
        return job_response
    except Exception as e:
        logger.error(f"Failed to create AI job: {e}")
        raise HTTPException(status_code=500, detail="Failed to create AI job")

@app.post("/api/v1/ai-jobs/{job_id}/tests", response_model=AITestResponse)
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

@app.get("/api/v1/entities/{entity_type}/{entity_id}/registry")
async def get_entity_registry(entity_type: str, entity_id: str):
    """Get entity registry entry with latest processing info"""
    try:
        entity_type_enum = EntityType(entity_type)
        registry_entry = interactions_service.get_entity_registry_entry(entity_type_enum, entity_id)
        
        if registry_entry:
            return registry_entry
        else:
            return {"message": "No registry entry found for this entity"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")
    except Exception as e:
        logger.error(f"Failed to get entity registry for {entity_type}:{entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve entity registry")

@app.get("/api/v1/ai-runs/statistics")
async def get_ai_statistics():
    """Get AI processing statistics"""
    try:
        stats = interactions_service.get_statistics()
        
        # Add database health info
        db_info = db_manager.get_database_info()
        stats["database_info"] = db_info
        
        return stats
        
    except Exception as e:
        logger.error(f"Failed to get AI statistics: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve statistics")

@app.get("/api/v1/entities/{entity_type}/{entity_id}/interactions")
async def get_entity_interactions(entity_type: str, entity_id: str, limit: int = 10):
    """Get interaction history for a specific entity"""
    try:
        entity_type_enum = EntityType(entity_type)
        interactions = interactions_service.get_entity_interaction_history(
            entity_type_enum, entity_id, limit
        )
        
        return {"interactions": [i.dict() for i in interactions]}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid entity type: {entity_type}")
    except Exception as e:
        logger.error(f"Failed to get entity interactions for {entity_type}:{entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve entity interactions")

@app.get("/api/v1/entities/{entity_type}/{entity_id}/last-run")
async def get_entity_last_run(entity_type: str, entity_id: str, action_type: Optional[str] = None):
    """Check when an entity was last processed by AI"""
    try:
        entity_type_enum = EntityType(entity_type)
        action_type_enum = AIActionType(action_type) if action_type else None
        
        last_interaction = interactions_service.get_entity_last_interaction(
            entity_type_enum, entity_id, action_type_enum
        )
        
        if last_interaction:
            return {"last_interaction": last_interaction.dict()}
        else:
            return {"last_interaction": None, "message": "No previous interactions found"}
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid parameter: {e}")
    except Exception as e:
        logger.error(f"Failed to get last run for {entity_type}:{entity_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve last run information")

@app.post("/api/v1/ai-runs/cleanup")
async def cleanup_old_data(days_old: int = 90):
    """Clean up old AI run data and files"""
    try:
        if days_old < 7:
            raise HTTPException(status_code=400, detail="Cannot cleanup data newer than 7 days")
        
        interactions_service.cleanup_old_data(days_old)
        return {"message": f"Successfully cleaned up data older than {days_old} days"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup old data: {e}")
        raise HTTPException(status_code=500, detail="Failed to cleanup old data")

# =============================================================================
# Plugin Interaction Sync Endpoints
# =============================================================================

@app.post("/api/v1/interactions/sync")
async def sync_plugin_interactions(interactions: List[Dict[str, Any]]):
    """Sync plugin interactions to the server database"""
    try:
        synced_count = 0
        failed_count = 0
        
        for interaction_data in interactions:
            try:
                # Parse and validate interaction data
                interaction_type = interaction_data.get("type", "unknown")
                timestamp = interaction_data.get("timestamp", datetime.utcnow().isoformat())
                page = interaction_data.get("page", "unknown")
                session_id = interaction_data.get("sessionId", "unknown")
                
                # Create entity interaction record
                if interaction_type in ["ai_processing", "facial_recognition", "gallery_batch", "scene_batch"]:
                    # Extract entity information from interaction data
                    entity_data = interaction_data.get("data", {})
                    entity_type = EntityType.GALLERY if "gallery" in interaction_type else EntityType.SCENE if "scene" in interaction_type else EntityType.IMAGE
                    entity_id = entity_data.get("entityId", "unknown")
                    
                    # Map interaction type to AI action type
                    action_type_map = {
                        "facial_recognition": AIActionType.IMAGE_IDENTIFICATION,
                        "gallery_batch": AIActionType.GALLERY_IDENTIFICATION,
                        "scene_batch": AIActionType.SCENE_IDENTIFICATION,
                        "ai_processing": AIActionType.FACIAL_RECOGNITION
                    }
                    action_type = action_type_map.get(interaction_type, AIActionType.FACIAL_RECOGNITION)
                    
                    # Create interaction record
                    interaction_create = InteractionCreate(
                        entity_type=entity_type,
                        entity_id=entity_id,
                        session_id=session_id,
                        service="plugin_sync",
                        action_type=interaction_type,
                        user_id=entity_data.get("userId"),
                        metadata={
                            "success": entity_data.get("success", False),
                            "performers_found": entity_data.get("performersFound", 0),
                            "confidence_scores": entity_data.get("confidenceScores", []),
                            "request_id": entity_data.get("requestId"),
                            "original_action_type": action_type.value if hasattr(action_type, 'value') else str(action_type)
                        }
                    )
                    
                    interactions_service.track_interaction(interaction_create)
                    synced_count += 1
                    
                else:
                    # For non-AI interactions, we could still log them for analytics
                    logger.debug(f"Skipping non-AI interaction: {interaction_type}")
                    
            except Exception as e:
                logger.error(f"Failed to sync interaction: {e}")
                failed_count += 1
        
        return {
            "success": True,
            "message": f"Synced {synced_count} interactions, {failed_count} failed",
            "synced_count": synced_count,
            "failed_count": failed_count
        }
        
    except Exception as e:
        logger.error(f"Failed to sync plugin interactions: {e}")
        raise HTTPException(status_code=500, detail="Failed to sync interactions")

@app.post("/api/v1/interactions/track")
async def track_single_interaction(interaction: Dict[str, Any]):
    """Track a single plugin interaction in real-time using unified interactions table"""
    logger.info(f"📝 Received interaction tracking request: {interaction}")
    try:
        # Extract unified interaction data
        entity_type = EntityType(interaction.get("entity_type", "image"))
        entity_id = interaction.get("entity_id", "unknown")
        session_id = interaction.get("user_id", interaction.get("session_id", "anonymous"))
        service = interaction.get("service_name", "plugin")
        action_type = interaction.get("action_type", "unknown")
        user_id = interaction.get("user_id")
        
        # Build metadata from all additional fields
        metadata = interaction.get("metadata", {})
        
        # Include any additional data in metadata for compatibility
        if "interaction_type" in interaction:
            metadata["interaction_type"] = interaction["interaction_type"]
        if "response_time" in interaction:
            metadata["response_time"] = interaction["response_time"]
        if "status" in interaction:
            metadata["status"] = interaction["status"]
        if "confidence_scores" in interaction:
            metadata["confidence_scores"] = interaction["confidence_scores"]
        if "performers_found" in interaction:
            metadata["performers_found"] = interaction["performers_found"]
        
        interaction_create = InteractionCreate(
            entity_type=entity_type,
            entity_id=entity_id,
            session_id=session_id,
            service=service,
            action_type=action_type,
            user_id=user_id,
            metadata=metadata if metadata else None
        )
        
        result = interactions_service.track_interaction(interaction_create)
        logger.info(f"✅ Successfully tracked interaction in database: {result.id}")
        
        return {
            "success": True,
            "message": "Interaction tracked successfully",
            "interaction_id": result.id
        }
            
    except ValueError as e:
        logger.error(f"❌ Invalid interaction data: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid interaction data: {e}")
    except Exception as e:
        logger.error(f"❌ Failed to track interaction: {e}")
        import traceback
        logger.error(f"Interaction tracking traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail="Failed to track interaction")

@app.get("/api/v1/interactions/{interaction_id}")
async def get_interaction_details(interaction_id: str):
    """Get details of a specific interaction for verification"""
    try:
        # First try to parse as integer (legacy database ID)
        try:
            db_interaction_id = int(interaction_id)
            interaction = interactions_service.get_interaction_by_id(db_interaction_id)
        except ValueError:
            # If not an integer, search by metadata (for UUID lookup)  
            interactions = interactions_service.get_recent_interactions(limit=1000)
            interaction = None
            for i in interactions:
                # Check if this interaction matches the requested ID in metadata
                if (i.metadata and 
                    (i.metadata.get('local_id') == interaction_id or 
                     i.metadata.get('interaction_id') == interaction_id)):
                    interaction = i
                    break
        
        if not interaction:
            raise HTTPException(status_code=404, detail=f"Interaction {interaction_id} not found")
        
        return {
            "success": True,
            "interaction": {
                "id": interaction.id,
                "entity_type": interaction.entity_type,
                "entity_id": interaction.entity_id,
                "session_id": interaction.session_id,
                "service": interaction.service,
                "action_type": interaction.action_type,
                "timestamp": interaction.timestamp.isoformat() if interaction.timestamp else None,
                "user_id": interaction.user_id,
                "metadata": interaction.metadata
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get interaction {interaction_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to retrieve interaction")

@app.get("/api/v1/interactions/status")
async def get_interaction_sync_status():
    """Get status of interaction syncing and database health"""
    try:
        # Get database health
        db_healthy = db_manager.health_check()
        
        # Get recent interaction stats
        stats = interactions_service.get_statistics()
        
        # Get database info
        db_info = db_manager.get_database_info()
        
        return {
            "database_healthy": db_healthy,
            "database_info": db_info,
            "recent_interactions": stats.get("recent_runs_24h", 0),
            "total_interactions": stats.get("total_runs", 0),
            "success_rate": stats.get("success_rate", 0),
            "last_sync": datetime.utcnow().isoformat(),
            "sync_enabled": True
        }
        
    except Exception as e:
        logger.error(f"Failed to get interaction sync status: {e}")
        raise HTTPException(status_code=500, detail="Failed to get sync status")

# =============================================================================
# Facial Recognition Endpoints
# =============================================================================

@app.post("/api/v1/facial-recognition/identify-scene", response_model=FacialRecognitionResponse)
async def identify_scene_performers(request: SceneIdentificationRequest, progress_callback=None, cancellation_check=None):
    """Identify performers in a scene"""
    # Ensure request has an ID
    if not request.request_id:
        request.request_id = generate_request_id()
    
    logger.info(f"Processing scene identification request {request.request_id}")
    
    try:
        # Check for cancellation before processing
        if cancellation_check and await cancellation_check():
            logger.info(f"Scene processing cancelled for request {request.request_id}")
            raise asyncio.CancelledError("Scene processing was cancelled")
        
        async with await create_visage_client() as visage:
            response = await visage.process_scene_identification(request)
            
        logger.info(f"Scene identification completed for request {request.request_id}")
        return response
        
    except asyncio.CancelledError:
        logger.info(f"Scene identification cancelled for request {request.request_id}")
        return FacialRecognitionResponse(
            success=False,
            error="Scene identification was cancelled",
            request_id=request.request_id,
            service_name="stash-ai-server"
        )
    except Exception as e:
        logger.error(f"Scene identification failed for request {request.request_id}: {e}")
        return FacialRecognitionResponse(
            success=False,
            error=f"Scene identification failed: {str(e)}",
            request_id=request.request_id,
            service_name="stash-ai-server"
        )

@app.post("/api/v1/facial-recognition/identify-gallery", response_model=FacialRecognitionResponse)
async def identify_gallery_performers(request: GalleryIdentificationRequest, progress_callback=None, cancellation_check=None, batch_job_id=None):
    """Identify performers in gallery images"""
    if not request.request_id:
        request.request_id = generate_request_id()
    
    logger.info(f"Processing gallery identification request {request.request_id}")
    
    try:
        # Check if images are provided in the request
        if not request.images or len(request.images) == 0:
            return FacialRecognitionResponse(
                success=False,
                error="No images provided for gallery identification",
                request_id=request.request_id,
                service_name="stash-ai-server"
            )
        
        logger.info(f"Processing {len(request.images)} images in gallery")
        
        # Track performer frequencies across all images for aggregated results
        performers_map = {}  # performer_id -> performer data with aggregation
        all_processing_results = []
        processed_count = 0
        skipped_count = 0
        
        for i, image_info in enumerate(request.images):
            try:
                # Check for cancellation before processing each image
                if cancellation_check and await cancellation_check():
                    logger.info(f"Gallery processing cancelled at image {i+1}/{len(request.images)}")
                    raise asyncio.CancelledError("Processing was cancelled")
                
                # Create individual image request for each gallery image
                from schemas.api_schema import ImageData
                
                image_data = None
                if 'base64' in image_info and image_info['base64']:
                    logger.info(f"Creating ImageData for gallery image {i}: base64 length = {len(image_info['base64'])}")
                    try:
                        image_data = ImageData(
                            data=image_info['base64'],
                            format="jpeg"
                        )
                        logger.info(f"Successfully created ImageData for gallery image {i}")
                    except Exception as e:
                        logger.error(f"Failed to create ImageData for gallery image {i}: {e}")
                        continue
                else:
                    logger.warning(f"No base64 data found for gallery image {i}: keys = {list(image_info.keys())}")
                
                image_request = FacialRecognitionRequest(
                    entity=StashEntity(
                        id=image_info.get('id', f"gallery_image_{i}"),
                        type="image",
                        title=image_info.get('title', f'Gallery Image {i + 1}'),
                        path=image_info.get('url', '')
                    ),
                    image_data=image_data,
                    request_id=f"{request.request_id}_img_{i}",
                    threshold=request.threshold,
                    max_results=request.max_results
                )
                
                # Create AI_test record for this individual image
                test_id = f"{request.request_id}_img_{i}"
                image_entity_id = image_info.get('id', f"gallery_image_{i}")
                image_entity_name = image_info.get('title', f'Gallery Image {i + 1}')
                
                created_test_id = test_id
                if batch_job_id:
                    try:
                        # Create test record for this image
                        job_id, created_test_id = create_ai_job_and_test(
                            entity_type=EntityType.IMAGE,
                            entity_id=image_entity_id,
                            entity_name=image_entity_name,
                            entity_filepath=image_info.get('url', ''),
                            action_type=AIActionType.IMAGE_IDENTIFICATION,
                            request_data={"threshold": request.threshold, "max_results": request.max_results, "image_index": i},
                            job_id=batch_job_id,  # Use existing batch job
                            test_id=test_id
                        )
                        logger.info(f"📝 Created AI_test record {created_test_id} for gallery image {i}")
                    except Exception as e:
                        logger.error(f"Failed to create AI_test record for gallery image {i}: {e}")
                
                # Process this image with Visage adapter and update test record
                from services.visage_adapter import create_visage_adapter
                async with create_visage_adapter() as visage:
                    # Get performers for this image without creating separate jobs
                    try:
                        performers = await asyncio.wait_for(
                            visage.identify_single_performer(
                                image_data=image_data.data,
                                threshold=request.threshold,
                                max_results=request.max_results
                            ),
                            timeout=30.0  # 30 second timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning(f"Visage service timeout for gallery image {i+1}")
                        performers = []  # Empty result on timeout
                    except Exception as e:
                        logger.error(f"Visage service error for gallery image {i+1}: {e}")
                        performers = []  # Empty result on error
                    
                    # Create a response-like object
                    class ImageResult:
                        def __init__(self, success=True, performers=None, error=None, processing_time=0):
                            self.success = success
                            self.performers = performers or []
                            self.error = error
                            self.processing_time = processing_time
                    
                    image_response = ImageResult(
                        success=True, 
                        performers=performers,
                        processing_time=0.5
                    )
                
                # Record processing result for this image
                processing_result = {
                    "imageId": image_info.get('id', f"gallery_image_{i}"),
                    "imageUrl": image_info.get('url', ''),
                    "success": image_response.success,
                    "performers": [],
                    "error": image_response.error if not image_response.success else None,
                    "processingTime": image_response.processing_time or 0
                }
                
                if image_response.success and image_response.performers:
                    # Convert performers to the expected format and aggregate
                    for performer in image_response.performers:
                        performer_dict = {
                            "id": performer.id,
                            "name": performer.name,
                            "confidence": performer.confidence,
                            "distance": getattr(performer.additional_info, 'distance', 0) if performer.additional_info else 0,
                            "image": performer.image_url or "",
                            "image_url": performer.image_url,
                            "performer_url": performer.stash_url or "",
                            "stash_url": performer.stash_url,
                            "additional_info": performer.additional_info
                        }
                        processing_result["performers"].append(performer_dict)
                        
                        # Aggregate performer frequency data
                        if performer.id not in performers_map:
                            performers_map[performer.id] = {
                                "performer": performer_dict,
                                "frequency": 0,
                                "appearances": [],
                                "totalConfidence": 0,
                                "bestConfidence": 0
                            }
                        
                        perf_data = performers_map[performer.id]
                        perf_data["frequency"] += 1
                        perf_data["totalConfidence"] += performer.confidence
                        perf_data["bestConfidence"] = max(perf_data["bestConfidence"], performer.confidence)
                        perf_data["appearances"].append({
                            "imageId": image_info.get('id', f"gallery_image_{i}"),
                            "imageUrl": image_info.get('url', ''),
                            "confidence": performer.confidence
                        })
                
                all_processing_results.append(processing_result)
                processed_count += 1
                
                # Update AI_test record with results
                if batch_job_id and created_test_id:
                    try:
                        success = image_response.success and len(image_response.performers) > 0
                        
                        # Prepare response data for test record
                        response_data = {
                            "success": image_response.success,
                            "performers": processing_result.get("performers", []),
                            "processing_time": image_response.processing_time,
                            "image_id": image_info.get('id', f"gallery_image_{i}"),
                            "confidence_scores": [p.get("confidence", 0) for p in processing_result.get("performers", [])],
                            "error": image_response.error if not image_response.success else None,
                            # Add entity information for interaction tracking
                            "entity": {
                                "id": image_entity_id,
                                "type": "image",
                                "title": image_entity_name,
                                "path": image_info.get('url', '')
                            },
                            "job_id": batch_job_id
                        }
                        
                        # Complete the test record
                        complete_ai_test(
                            test_id=created_test_id,
                            success=success,
                            response_data=response_data,
                            service_name="visage",
                            processing_time=image_response.processing_time or 0.5
                        )
                        logger.info(f"✅ Updated AI_test {created_test_id} - Success: {success}, Performers: {len(processing_result.get('performers', []))}")
                        
                    except Exception as e:
                        logger.error(f"Failed to update AI_test record {created_test_id}: {e}")
                
                # Call progress callback if provided
                if progress_callback:
                    await progress_callback(processed_count, len(request.images), f"Processed {processed_count}/{len(request.images)} images")
                
            except Exception as e:
                logger.error(f"Failed to process gallery image {image_info.get('id', 'unknown')}: {e}")
                
                # Update AI_test record to mark as failed
                if batch_job_id and 'created_test_id' in locals():
                    try:
                        complete_ai_test(
                            test_id=created_test_id,
                            success=False,
                            response_data={
                                "error": str(e), 
                                "processing_failed": True,
                                # Add entity information for interaction tracking
                                "entity": {
                                    "id": image_info.get('id', f"gallery_image_{i}"),
                                    "type": "image",
                                    "title": image_info.get('title', f'Gallery Image {i + 1}'),
                                    "path": image_info.get('url', '')
                                },
                                "job_id": batch_job_id
                            },
                            service_name="visage",
                            processing_time=0
                        )
                        logger.info(f"❌ Marked AI_test {created_test_id} as failed due to processing error")
                    except Exception as test_error:
                        logger.error(f"Failed to update AI_test record {created_test_id} with error: {test_error}")
                
                skipped_count += 1
                continue
        
        # Convert performers map to frequency array with calculated averages
        performer_frequencies = []
        for perf_data in performers_map.values():
            performer_frequencies.append({
                "performer": perf_data["performer"],
                "frequency": perf_data["frequency"],
                "appearances": perf_data["appearances"],
                "averageConfidence": perf_data["totalConfidence"] / perf_data["frequency"],
                "bestConfidence": perf_data["bestConfidence"]
            })
        
        # Sort by frequency (descending) then by best confidence
        performer_frequencies.sort(key=lambda x: (-x["frequency"], -x["bestConfidence"]))
        
        logger.info(f"Gallery processing completed: {processed_count} images processed, {len(performer_frequencies)} unique performers found")
        
        return FacialRecognitionResponse(
            success=True,
            message=f"Processed {processed_count} images from gallery, found {len(performer_frequencies)} unique performers",
            request_id=request.request_id,
            service_name="stash-ai-server",
            entity=request.entity,
            performers=[],  # Individual performers list (empty for gallery aggregation)
            faces=[],
            processing_time=sum(result.get("processingTime", 0) for result in all_processing_results),
            ai_model_info={
                "gallery_results": {
                    "success": True,
                    "galleryId": request.entity.id,
                    "totalImages": len(request.images),
                    "processedImages": processed_count,
                    "skippedImages": skipped_count,
                    "performers": performer_frequencies,
                    "processingResults": all_processing_results,
                    "totalProcessingTime": sum(result.get("processingTime", 0) for result in all_processing_results)
                }
            }
        )
        
    except asyncio.CancelledError:
        logger.info(f"Gallery identification cancelled for request {request.request_id}")
        return FacialRecognitionResponse(
            success=False,
            error="Gallery identification was cancelled",
            request_id=request.request_id,
            service_name="stash-ai-server"
        )
    except Exception as e:
        logger.error(f"Gallery identification failed for request {request.request_id}: {e}")
        return FacialRecognitionResponse(
            success=False,
            error=f"Gallery identification failed: {str(e)}",
            request_id=request.request_id,
            service_name="stash-ai-server"
        )

@app.post("/api/v1/facial-recognition/identify-image", response_model=FacialRecognitionResponse)
async def identify_image_performers(request: FacialRecognitionRequest, progress_callback=None, cancellation_check=None):
    """Identify performers in a single image using multi-face detection"""
    if not request.request_id:
        request.request_id = generate_request_id()
    
    # Create AI job and test for tracking
    entity_type = EntityType.IMAGE
    entity_id = request.entity.id if request.entity else "unknown"
    entity_name = request.entity.title if request.entity else None
    
    # Use batch job ID if provided, otherwise create new job
    job_id, test_id = create_ai_job_and_test(
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name=entity_name,
        entity_filepath=request.entity.path if request.entity else None,
        action_type=AIActionType.IMAGE_IDENTIFICATION,
        request_data={"threshold": request.threshold, "max_results": request.max_results},
        job_id=request.batch_job_id,  # Use existing batch job if provided
        test_id=request.request_id
    )
    
    # Use batch processing context if this is part of a batch job
    is_batch_operation = request.batch_job_id is not None
    
    logger.info(f"Processing image identification test {test_id} in job {job_id}")
    start_time = datetime.utcnow()
    
    try:
        # Check for cancellation before processing
        if cancellation_check and await cancellation_check():
            logger.info(f"Image processing cancelled for test {test_id}")
            raise asyncio.CancelledError("Image processing was cancelled")
        
        # Batch processing mode is now managed at the job level, not request level
        async with await create_visage_client() as visage:
            return await _process_image_identification(
                visage, request, test_id, job_id, start_time, cancellation_check
            )
    except asyncio.CancelledError:
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        logger.info(f"Image identification cancelled for test {test_id}")
        return FacialRecognitionResponse(
            success=False,
            error="Image identification was cancelled",
            request_id=request.request_id,
            service_name="stash-ai-server",
            processing_time=processing_time
        )
    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        logger.error(f"Image identification failed for test {test_id}: {e}")
        
        complete_ai_test(test_id, False, error_message=str(e))
        
        return FacialRecognitionResponse(
            success=False,
            error=f"Image identification failed: {str(e)}",
            request_id=test_id,
            processing_time=processing_time,
            service_name="stash-ai-server"
        )

async def _process_image_identification(visage, request, test_id, job_id, start_time, cancellation_check=None):
    """Helper function to process image identification"""
    try:
        # Check for cancellation before processing
        if cancellation_check and await cancellation_check():
            logger.info(f"Image identification processing cancelled for test {test_id}")
            raise asyncio.CancelledError("Image identification processing was cancelled")
        
        if not request.image_data:
            complete_ai_test(test_id, False, error_message="No image data provided")
            return FacialRecognitionResponse(
                success=False,
                error="No image data provided",
                request_id=test_id,
                service_name="stash-ai-server"
            )
        
        # Use multiple performer identification to detect all faces in image
        faces_with_performers = await visage.identify_multiple_performers(
            image_data=request.image_data.data,
            threshold=request.threshold,
            max_results=request.max_results
        )
        
        # Aggregate performers with confidence filtering
        all_performers = []
        all_faces = []
        
        for face_data in faces_with_performers:
            # Add face info
            face_info = FaceInfo(
                bbox=[0, 0, 0, 0],  # Would need actual coordinates from Visage
                confidence=face_data.get("face_confidence", 0.0)
            )
            all_faces.append(face_info)
            
            # Get performers for this face and filter to top match only
            face_performers = face_data.get("performers", [])
            if face_performers:
                # Sort by confidence (descending) and take the top match
                # Handle both PerformerInfo objects and dictionary responses
                def get_confidence(p):
                    if hasattr(p, 'confidence'):
                        return p.confidence
                    elif isinstance(p, dict):
                        return p.get('confidence', 0.0)
                    else:
                        return 0.0
                
                sorted_performers = sorted(face_performers, key=get_confidence, reverse=True)
                top_performer = sorted_performers[0]
                
                # Get confidence value safely
                top_confidence = get_confidence(top_performer)
                
                # Get performer ID safely
                if hasattr(top_performer, 'id'):
                    performer_id = top_performer.id
                elif isinstance(top_performer, dict):
                    performer_id = top_performer.get('id', '')
                else:
                    performer_id = ''
                
                # Only add if meets minimum threshold and not already added
                def get_performer_id(p):
                    if hasattr(p, 'id'):
                        return p.id
                    elif isinstance(p, dict):
                        return p.get('id', '')
                    else:
                        return ''
                
                if (top_confidence >= request.threshold and 
                    not any(get_performer_id(p) == performer_id for p in all_performers)):
                    all_performers.append(top_performer)
        
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        
        response_data = {
            "success": True,
            "message": f"Identified {len(all_performers)} performers in image",
            "request_id": test_id,
            "job_id": job_id,
            "processing_time": processing_time,
            "service_name": "visage",
            "entity": request.entity.dict() if request.entity else None,
            "performers": [p.dict() if hasattr(p, 'dict') else p for p in all_performers],
            "faces": [f.dict() for f in all_faces],
            "ai_model_info": {
                "models_used": ["arcface", "facenet"],
                "ensemble_method": "weighted_voting",
                "threshold": request.threshold,
                "faces_detected": len(faces_with_performers)
            }
        }
        
        # Complete AI test tracking
        logger.info(f"Completing AI test {test_id} with response_data keys: {list(response_data.keys()) if response_data else 'None'}")
        complete_ai_test(
            test_id=test_id,
            success=True,
            response_data=response_data,
            service_name="visage",
            processing_time=processing_time
        )
        
        # Check if job should be marked as completed
        check_and_complete_job(job_id)
        
        return FacialRecognitionResponse(
            success=True,
            message=f"Identified {len(all_performers)} performers in image",
            request_id=test_id,
            processing_time=processing_time,
            service_name="visage",
            entity=request.entity,
            performers=all_performers,
            faces=all_faces,
            ai_model_info={
                "models_used": ["arcface", "facenet"],
                "ensemble_method": "weighted_voting",
                "threshold": request.threshold,
                "faces_detected": len(faces_with_performers)
            }
        )
                
    except Exception as e:
        processing_time = (datetime.utcnow() - start_time).total_seconds()
        error_msg = f"Image identification failed: {str(e)}"
        
        # Complete AI test tracking with failure
        complete_ai_test(test_id, False, error_message=error_msg, processing_time=processing_time)
        
        logger.error(f"Image identification failed for test {test_id}: {e}")
        return FacialRecognitionResponse(
            success=False,
            error=error_msg,
            request_id=test_id,
            processing_time=processing_time,
            service_name="stash-ai-server"
        )

@app.post("/api/v1/facial-recognition/compare-faces", response_model=FaceComparisonResponse)
async def compare_performer_faces(request: FaceComparisonRequest):
    """Compare faces between two performers"""
    if not request.request_id:
        request.request_id = generate_request_id()
    
    logger.info(f"Processing face comparison request {request.request_id}")
    
    try:
        async with await create_visage_client() as visage:
            response = await visage.process_face_comparison(request)
            
        logger.info(f"Face comparison completed for request {request.request_id}")
        return response
        
    except Exception as e:
        logger.error(f"Face comparison failed for request {request.request_id}: {e}")
        return FaceComparisonResponse(
            success=False,
            error=f"Face comparison failed: {str(e)}",
            request_id=request.request_id,
            service_name="stash-ai-server"
        )

# =============================================================================
# Content Analysis Endpoints (Placeholder)
# =============================================================================

@app.post("/api/v1/content-analysis/analyze-scene", response_model=ContentAnalysisResponse)
async def analyze_scene_content(request: ContentAnalysisRequest):
    """Analyze scene content for tags and metadata"""
    if not request.request_id:
        request.request_id = generate_request_id()
    
    logger.info(f"Processing content analysis request {request.request_id}")
    
    # Placeholder implementation - would route to appropriate service
    return ContentAnalysisResponse(
        success=False,
        error="Content analysis service not yet implemented",
        request_id=request.request_id,
        service_name="stash-ai-server"
    )

@app.post("/api/v1/content-analysis/extract-metadata", response_model=ContentAnalysisResponse)
async def extract_content_metadata(request: ContentAnalysisRequest):
    """Extract technical metadata from content"""
    if not request.request_id:
        request.request_id = generate_request_id()
    
    logger.info(f"Processing metadata extraction request {request.request_id}")
    
    # Placeholder implementation
    return ContentAnalysisResponse(
        success=False,
        error="Metadata extraction service not yet implemented",
        request_id=request.request_id,
        service_name="stash-ai-server"
    )

# =============================================================================
# Batch Processing Endpoints (Placeholder)
# =============================================================================

@app.post("/api/v1/batch/submit", response_model=BatchResponse)
async def submit_batch_job(request: BatchRequest, background_tasks: BackgroundTasks):
    """Submit a batch processing job"""
    if not request.request_id:
        request.request_id = generate_request_id()
    
    job_id = generate_request_id()
    
    # Create batch job status
    job_status = BatchJobStatus(
        job_id=job_id,
        status=ProcessingStatus.PENDING,
        total_items=len(request.entities),
        processed_items=0,
        failed_items=0,
        progress_percentage=0.0,
        started_at=datetime.utcnow()
    )
    
    # Store job status
    batch_jobs[job_id] = {
        "status": job_status,
        "request": request
    }
    
    logger.info(f"Submitted batch job {job_id} with {len(request.entities)} items")
    
    # TODO: Add background task processing
    # background_tasks.add_task(process_batch_job, job_id, request)
    
    return BatchResponse(
        success=True,
        message=f"Batch job {job_id} submitted successfully",
        request_id=request.request_id,
        service_name="stash-ai-server",
        job_status=job_status
    )

@app.get("/api/v1/batch/{job_id}/status", response_model=BatchJobStatus)
async def get_batch_job_status(job_id: str):
    """Get batch job status"""
    if job_id not in batch_jobs:
        raise HTTPException(status_code=404, detail=f"Batch job {job_id} not found")
    
    return batch_jobs[job_id]["status"]

# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail,
            "code": str(exc.status_code),
            "timestamp": datetime.utcnow().isoformat()
        }
    )

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "code": "500",
            "timestamp": datetime.utcnow().isoformat()
        }
    )

# =============================================================================
# Simple Queue Endpoints
# =============================================================================

@app.post("/api/v1/queue/submit/image")
async def submit_image_to_queue(request: FacialRecognitionRequest):
    """Submit an image identification job to the queue"""
    try:
        # Convert request to dict for storage
        request_data = request.dict()
        
        # Submit to queue and get job_id (queue handles database record creation)
        job_id = await simple_queue.submit_job("image", request_data)
        
        return {
            "success": True,
            "job_id": job_id,
            "message": f"Image job {job_id} submitted to queue"
        }
        
    except Exception as e:
        logger.error(f"Failed to submit image job to queue: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/v1/queue/submit/gallery")
async def submit_gallery_to_queue(request: GalleryIdentificationRequest):
    """Submit a gallery identification job to the queue"""
    try:
        # Convert request to dict for storage
        request_data = request.dict()
        
        # Submit to queue and get job_id (queue handles database record creation)
        job_id = await simple_queue.submit_job("gallery", request_data)
        
        return {
            "success": True,
            "job_id": job_id,
            "message": f"Gallery job {job_id} submitted to queue"
        }
        
    except Exception as e:
        logger.error(f"Failed to submit gallery job to queue: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/v1/queue/submit/scene")
async def submit_scene_to_queue(request: SceneIdentificationRequest):
    """Submit a scene identification job to the queue"""
    try:
        # Convert request to dict for storage
        request_data = request.dict()
        
        # Submit to queue and get job_id (queue handles database record creation)
        job_id = await simple_queue.submit_job("scene", request_data)
        
        return {
            "success": True,
            "job_id": job_id,
            "message": f"Scene job {job_id} submitted to queue"
        }
        
    except Exception as e:
        logger.error(f"Failed to submit scene job to queue: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@app.get("/api/v1/queue/status/{job_id}")
async def get_queue_job_status(job_id: str):
    """Get the status of a queued job"""
    try:
        status = simple_queue.get_job_status(job_id)
        
        if not status:
            raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
        
        return status
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to get job status")

# =============================================================================
# WebSocket Endpoints
# =============================================================================

@app.websocket("/ws/queue")
async def websocket_queue_updates(websocket: WebSocket):
    """WebSocket endpoint for real-time queue updates"""
    await websocket_manager.connect(websocket)
    
    try:
        # Send initial queue status when client connects using consistent queue status
        queue_status = get_active_queue_status()
        
        initial_status = {
            "type": "queue_status",
            "data": {
                "active_jobs": queue_status.get("active_jobs", []),
                "active_jobs_count": queue_status.get("active_jobs_count", 0),
                "recent_completed_jobs": queue_status.get("recent_completed_jobs", []),
                "timestamp": datetime.utcnow().isoformat()
            }
        }
        await websocket_manager.send_personal_message(initial_status, websocket)
        
        # Keep connection alive and handle client messages
        while True:
            try:
                # Wait for client messages (like ping/keepalive)
                data = await websocket.receive_text()
                
                # Handle different message types
                try:
                    # Try to parse as JSON first
                    import json
                    message = json.loads(data)
                    message_type = message.get("type", data)
                except (json.JSONDecodeError, TypeError):
                    # Fallback to treating as plain string
                    message_type = data
                    message = {"type": data}
                
                if message_type == "ping":
                    await websocket_manager.send_personal_message({"type": "pong"}, websocket)
                elif message_type == "get_status":
                    # Send current queue status using consistent queue status
                    queue_status = get_active_queue_status()
                    
                    status = {
                        "type": "queue_status",
                        "data": {
                            "active_jobs": queue_status.get("active_jobs", []),
                            "active_jobs_count": queue_status.get("active_jobs_count", 0),
                            "recent_completed_jobs": queue_status.get("recent_completed_jobs", []),
                            "timestamp": datetime.utcnow().isoformat()
                        }
                    }
                    await websocket_manager.send_personal_message(status, websocket)
                    
                elif message_type == "cancel_job":
                    # Handle job cancellation request
                    job_id = message.get("job_id")
                    if job_id:
                        try:
                            success = await simple_queue.cancel_job(job_id)
                            response = {
                                "type": "cancel_response",
                                "job_id": job_id,
                                "success": success,
                                "message": "Job cancelled successfully" if success else "Failed to cancel job"
                            }
                        except Exception as e:
                            logger.error(f"Error cancelling job {job_id}: {e}")
                            response = {
                                "type": "cancel_response",
                                "job_id": job_id,
                                "success": False,
                                "message": f"Error cancelling job: {str(e)}"
                            }
                    else:
                        response = {
                            "type": "cancel_response",
                            "success": False,
                            "message": "No job_id provided"
                        }
                    
                    await websocket_manager.send_personal_message(response, websocket)
                    
            except WebSocketDisconnect:
                break
            except Exception as e:
                logger.error(f"WebSocket error: {e}")
                break
                
    except WebSocketDisconnect:
        pass
    finally:
        websocket_manager.disconnect(websocket)

# =============================================================================
# Application Entry Point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8080,
        reload=True,
        log_level="info"
    )