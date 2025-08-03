# =============================================================================
# Simple Queue for StashAI Server
# =============================================================================

import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from enum import Enum
import uuid

logger = logging.getLogger(__name__)

# Import database services for job status updates
try:
    from database.interactions_service import interactions_service
    ENABLE_DB_INTEGRATION = True
except ImportError:
    logger.warning("Database integration not available - job status updates will be in-memory only")
    interactions_service = None
    ENABLE_DB_INTEGRATION = False

# Import database models and evaluators
try:
    from database.models import ProcessingJob, ProcessingTest, ProcessingJobCreate, ProcessingTestCreate, ProcessingTestUpdate, AIModel, TestResult
    ENABLE_SCHEMA = True
    logger.info("Database schema available")
except ImportError:
    logger.warning("Database schema not available - using legacy schema only")
    ProcessingJob = None
    ProcessingTest = None
    ENABLE_SCHEMA = False

# Import WebSocket manager for real-time updates
try:
    # This will be imported when simple_queue is imported from main.py
    websocket_manager = None
    ENABLE_WEBSOCKET = False
except ImportError:
    websocket_manager = None
    ENABLE_WEBSOCKET = False

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing" 
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class QueueJob:
    def __init__(self, job_id: str, job_type: str, request_data: Dict[str, Any]):
        self.job_id = job_id
        self.job_type = job_type
        self.request_data = request_data
        self.status = JobStatus.PENDING
        self.created_at = datetime.utcnow()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.result: Optional[Dict[str, Any]] = None
        self.error: Optional[str] = None

class SimpleQueue:
    def __init__(self):
        self.jobs: Dict[str, QueueJob] = {}
        self.pending_jobs: Optional[asyncio.Queue] = None
        self.processing = False
        self.worker_task: Optional[asyncio.Task] = None
        self.websocket_manager = None  # Will be set by main.py
        
    def set_websocket_manager(self, manager):
        """Set the WebSocket manager for real-time updates"""
        self.websocket_manager = manager
        logger.info("WebSocket manager connected to simple_queue")
    
    async def _broadcast_queue_update(self, event_type: str, job_id: str, data: Dict[str, Any] = None):
        """Broadcast queue updates to all connected WebSocket clients"""
        if not self.websocket_manager:
            return
            
        try:
            # Get current queue status - use actual running jobs from simple_queue
            active_jobs = []
            recent_completed = []
            
            # Get active jobs from simple_queue itself (the source of truth)
            print(f"DEBUG: Checking self.jobs for active jobs. Total jobs: {len(self.jobs)}")
            for job in self.jobs.values():
                print(f"DEBUG: Job {job.job_id} status: {job.status}")
                if job.status in [JobStatus.PENDING, JobStatus.PROCESSING]:
                    # Properly serialize the QueueJob object
                    active_job = {
                        'job_id': job.job_id,
                        'job_type': job.job_type,
                        'status': job.status.value,  # Convert enum to string
                        'created_at': job.created_at.isoformat(),  # Convert datetime to string
                        'started_at': job.started_at.isoformat() if job.started_at else None,
                        'entity_name': f"{job.job_type.title()} Job {job.job_id[:8]}..."
                    }
                    active_jobs.append(active_job)
                    print(f"DEBUG: Added active job: {active_job}")
            
            print(f"DEBUG: Total active jobs found: {len(active_jobs)}")
            
            # Get recent completed from database if available
            if ENABLE_DB_INTEGRATION and interactions_service:
                recent_completed = interactions_service.get_recent_completed_jobs(limit=10)
                
                # Manually serialize jobs to ensure proper datetime handling
                def serialize_job(job):
                    job_dict = job.model_dump()
                    # Ensure datetime fields are properly serialized
                    for field in ['created_at', 'started_at', 'completed_at', 'updated_at']:
                        if field in job_dict and job_dict[field] is not None:
                            if hasattr(job_dict[field], 'isoformat'):
                                job_dict[field] = job_dict[field].isoformat()
                    return job_dict
                
                message = {
                    "type": "queue_update",
                    "event": event_type,
                    "job_id": job_id,
                    "data": data or {},
                    "queue_status": {
                        "active_jobs": active_jobs,  # Already serialized above
                        "active_jobs_count": len(active_jobs),
                        "recent_completed_jobs": [serialize_job(job) for job in recent_completed],
                        "timestamp": datetime.utcnow().isoformat()
                    }
                }
                
                await self.websocket_manager.broadcast(message)
                if event_type == "job_completed":
                    logger.info(f"📡 Successfully broadcasted {event_type} update for job {job_id}")
                else:
                    logger.debug(f"Broadcasted {event_type} update for job {job_id}")
            
        except Exception as e:
            logger.error(f"Failed to broadcast queue update: {e}")
    
    async def broadcast_progress(self, job_id: str, current: int, total: int, message: str = ""):
        """Broadcast job progress update"""
        await self._broadcast_queue_update("job_progress", job_id, {
            "current": current,
            "total": total,
            "progress_percentage": (current / total * 100) if total > 0 else 0,
            "message": message
        })
        
    def start(self):
        """Start the queue worker"""
        if not self.processing:
            # Create queue in the current event loop
            self.pending_jobs = asyncio.Queue()
            self.processing = True
            self.worker_task = asyncio.create_task(self._worker())
            logger.info("Simple queue worker started")
    
    def stop(self):
        """Stop the queue worker"""
        self.processing = False
        if self.worker_task:
            self.worker_task.cancel()
            logger.info("Simple queue worker stopped")
    
    async def submit_job(self, job_type: str, request_data: Dict[str, Any]) -> str:
        """Submit a job to the queue"""
        if not self.pending_jobs:
            raise RuntimeError("Queue not started")
            
        job_id = f"{job_type}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{str(uuid.uuid4())[:8]}"
        
        job = QueueJob(job_id, job_type, request_data)
        self.jobs[job_id] = job
        
        # Create database record BEFORE adding to queue
        self._create_database_job_record(job_id, job_type, request_data)
        
        await self.pending_jobs.put(job)
        logger.info(f"Submitted job {job_id} of type {job_type}")
        
        # Broadcast job submitted event
        await self._broadcast_queue_update("job_submitted", job_id, {
            "job_type": job_type,
            "submitted_at": job.created_at.isoformat()
        })
        
        return job_id
    
    def get_job_status(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job status"""
        if job_id not in self.jobs:
            return None
            
        job = self.jobs[job_id]
        return {
            "job_id": job.job_id,
            "job_type": job.job_type,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "result": job.result,
            "error": job.error
        }
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a job if it's pending or processing"""
        if job_id not in self.jobs:
            logger.warning(f"Attempted to cancel non-existent job {job_id}")
            return False
            
        job = self.jobs[job_id]
        
        # Can only cancel pending or processing jobs
        if job.status not in [JobStatus.PENDING, JobStatus.PROCESSING]:
            logger.warning(f"Cannot cancel job {job_id} with status {job.status.value}")
            return False
            
        # Mark job as cancelled
        old_status = job.status.value
        job.status = JobStatus.CANCELLED
        job.completed_at = datetime.utcnow()
        job.error = "Job cancelled by user"
        
        logger.info(f"Job {job_id} cancelled successfully (was {old_status}, now {job.status.value})")
        
        # Update database job status to cancelled
        self._update_database_job_status(job_id, "cancelled", error="Job cancelled by user")
        
        # Broadcast job cancelled event
        await self._broadcast_queue_update("job_cancelled", job_id, {
            "job_type": job.job_type,
            "cancelled_at": job.completed_at.isoformat(),
            "reason": "User requested cancellation"
        })
        
        return True
    
    def _create_database_job_record(self, job_id: str, job_type: str, request_data: Dict[str, Any]):
        """Create initial database record for job"""
        if not ENABLE_DB_INTEGRATION:
            return
            
        try:
            # Try main schema first
            if ENABLE_SCHEMA:
                self._create_main_database_job_record(job_id, job_type, request_data)
            elif interactions_service:
                self._create_legacy_database_job_record(job_id, job_type, request_data)
                
        except Exception as e:
            logger.error(f"Failed to create database record for job {job_id}: {e}")
            import traceback
            logger.error(f"Database creation traceback: {traceback.format_exc()}")
    
    def _create_main_database_job_record(self, job_id: str, job_type: str, request_data: Dict[str, Any]):
        """Create database record using ProcessingJob"""
        from database.models import AIActionType, EntityType, AIModel
        from database.database import DatabaseSession
        
        # Map job types to action types and extract entity info
        action_type_map = {
            "image": AIActionType.IMAGE_IDENTIFICATION,
            "gallery": AIActionType.GALLERY_IDENTIFICATION, 
            "scene": AIActionType.SCENE_IDENTIFICATION
        }
        
        entity_type_map = {
            "image": EntityType.IMAGE,
            "gallery": EntityType.GALLERY,
            "scene": EntityType.SCENE
        }
        
        action_type = action_type_map.get(job_type, AIActionType.FACIAL_RECOGNITION)
        entity_type = entity_type_map.get(job_type, EntityType.IMAGE)
        
        # Extract entity info from request data
        entity_id = "unknown"
        entity_name = f"{job_type.title()} Job"
        total_tests_planned = 1
        test_entity_list = []
        
        if "entity" in request_data and request_data["entity"]:
            entity_id = request_data["entity"].get("id", "unknown")
            
            # Enhanced entity name extraction with multiple fallbacks
            entity_title = request_data["entity"].get("title")
            entity_name_fallback = request_data["entity"].get("name")  # Some requests use 'name'
            entity_path = request_data["entity"].get("path", "")
            
            # Priority order: title > name > formatted path > default
            if entity_title:
                entity_name = entity_title
            elif entity_name_fallback:
                entity_name = entity_name_fallback
            elif entity_path:
                # Extract filename from path and format nicely
                import os
                filename = os.path.basename(entity_path)
                if filename:
                    # Format as "filename | EntityType | Stash" to match local job format
                    entity_name = f"{filename} | {job_type.title()}s | Stash"
                else:
                    entity_name = f"{job_type.title()} {entity_id}"
            else:
                entity_name = f"{job_type.title()} {entity_id}"
                
            test_entity_list = [{"entity_id": entity_id, "filepath": entity_path}]
            logger.info(f"Job {job_id} entity naming: id={entity_id}, name='{entity_name}', path='{entity_path}'")
        
        # Check for images array to get accurate count and build test list
        if "images" in request_data and isinstance(request_data["images"], list):
            total_tests_planned = len(request_data["images"])
            entity_name = f"Gallery with {total_tests_planned} images"
            test_entity_list = [
                {"entity_id": img.get("id", f"img_{i}"), "filepath": img.get("path", "")} 
                for i, img in enumerate(request_data["images"])
            ]
            logger.info(f"Found {total_tests_planned} images in gallery job {job_id}")
        
        # Create ProcessingJob record
        with DatabaseSession() as db:
            processing_job = ProcessingJob(
                job_id=job_id,
                job_name=f"{job_type.title()} Processing",
                entity_type=entity_type.value,
                entity_id=entity_id,
                entity_name=entity_name,
                action_type=action_type.value,
                status="pending",
                created_at=datetime.utcnow(),
                ai_model=AIModel.VISAGE.value,
                total_tests_planned=total_tests_planned,
                test_entity_list=test_entity_list,
                job_config=request_data
            )
            
            db.add(processing_job)
            db.commit()
            
            logger.info(f"Created database record for job {job_id} with {total_tests_planned} planned tests")
    
    def _create_legacy_database_job_record(self, job_id: str, job_type: str, request_data: Dict[str, Any]):
        """Create database record using legacy schema"""
        from database.models import AIActionType, EntityType, AIJobCreate
        
        # Legacy creation logic (existing code)
        action_type_map = {
            "image": AIActionType.IMAGE_IDENTIFICATION,
            "gallery": AIActionType.GALLERY_IDENTIFICATION, 
            "scene": AIActionType.SCENE_IDENTIFICATION
        }
        
        entity_type_map = {
            "image": EntityType.IMAGE,
            "gallery": EntityType.GALLERY,
            "scene": EntityType.SCENE
        }
        
        action_type = action_type_map.get(job_type, AIActionType.FACIAL_RECOGNITION)
        entity_type = entity_type_map.get(job_type, EntityType.IMAGE)
        
        entity_id = "unknown"
        entity_name = f"{job_type.title()} Job"
        total_items = 1
        
        if "entity" in request_data and request_data["entity"]:
            entity_id = request_data["entity"].get("id", "unknown")
            
            # Enhanced entity name extraction with multiple fallbacks (same as main method)
            entity_title = request_data["entity"].get("title")
            entity_name_fallback = request_data["entity"].get("name")  # Some requests use 'name'
            entity_path = request_data["entity"].get("path", "")
            
            # Priority order: title > name > formatted path > default
            if entity_title:
                entity_name = entity_title
            elif entity_name_fallback:
                entity_name = entity_name_fallback
            elif entity_path:
                # Extract filename from path and format nicely
                import os
                filename = os.path.basename(entity_path)
                if filename:
                    # Format as "filename | EntityType | Stash" to match local job format
                    entity_name = f"{filename} | {job_type.title()}s | Stash"
                else:
                    entity_name = f"{job_type.title()} {entity_id}"
            else:
                entity_name = f"{job_type.title()} {entity_id}"
        
        if "images" in request_data and isinstance(request_data["images"], list):
            total_items = len(request_data["images"])
            entity_name = f"Gallery with {total_items} images"
        
        job_data = AIJobCreate(
            job_name=f"{job_type.title()} Processing",
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            action_type=action_type
        )
        
        interactions_service.create_ai_job(job_data, job_id)
        logger.info(f"Created legacy database record for job {job_id}")
    
    def _update_database_job_status(self, job_id: str, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """Update job status in database if database integration is available"""
        if not ENABLE_DB_INTEGRATION or not interactions_service:
            return
        
        # Try main schema first if available
        if ENABLE_SCHEMA:
            try:
                self._update_job_status_and_results(job_id, status, result, error)
                logger.info(f"Updated database job status for {job_id}: {status}")
                return
            except Exception as e:
                logger.warning(f"Failed to update database job status for {job_id}: {e}")
                # Fall through to legacy update
            
        try:
            from database.models import JobStatus, ProcessingJob, ProcessingTest, TestResult
            from database.database import DatabaseSession
            
            # Map simple queue status to database status
            db_status = status
            if status == "completed":
                db_status = JobStatus.COMPLETED.value
            elif status == "failed":
                db_status = JobStatus.FAILED.value
            elif status == "processing":
                db_status = JobStatus.PROCESSING.value
            elif status == "cancelled":
                db_status = JobStatus.FAILED.value  # Map cancelled to failed in database
            
            # Update job directly in database
            with DatabaseSession() as db:
                db_job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
                if db_job:
                    db_job.status = db_status
                    if status in ["completed", "failed"]:
                        db_job.completed_at = datetime.utcnow()
                    
                    # Store results if job completed successfully
                    if status == "completed" and result:
                        # Update job statistics from result data
                        try:
                            # Extract stats from result
                            if isinstance(result, dict):
                                total_items = 0
                                successful_items = 0
                                failed_items = 0
                                
                                # For gallery jobs, first check if we have the original job data to get total count
                                if db_job.total_tests_planned and db_job.total_tests_planned > 0:
                                    # Use the total_tests_planned from job creation
                                    total_items = db_job.total_tests_planned
                                else:
                                    # Extract from job data if available
                                    original_data = self.jobs.get(job_id)
                                    if original_data and 'images' in original_data.request_data:
                                        total_items = len(original_data.request_data['images'])
                                    else:
                                        total_items = 1  # default for single entity
                                
                                # Count successful items from result data
                                if 'performers' in result and isinstance(result['performers'], list):
                                    successful_items = len([p for p in result['performers'] if p.get('confidence', 0) > 0])
                                elif 'faces' in result and isinstance(result['faces'], list):
                                    successful_items = len([f for f in result['faces'] if f.get('confidence', 0) > 0])
                                elif 'entity' in result:
                                    successful_items = 1 if result.get('success', False) else 0
                                else:
                                    successful_items = 0
                                
                                failed_items = total_items - successful_items
                                
                                # Update job statistics
                                if total_items > 0:
                                    db_job.tests_completed = successful_items + failed_items
                                    db_job.tests_passed = successful_items
                                    db_job.tests_failed = failed_items
                                    db_job.progress_percentage = (successful_items / total_items) * 100 if total_items > 0 else 0
                                    
                                    # Extract confidence scores if available
                                    confidences = []
                                    if 'performers' in result:
                                        confidences = [p.get('confidence', 0) for p in result['performers'] if p.get('confidence', 0) > 0]
                                    elif 'faces' in result:
                                        confidences = [f.get('confidence', 0) for f in result['faces'] if f.get('confidence', 0) > 0]
                                    
                                    if confidences:
                                        # Store confidence summary in JSON field
                                        db_job.confidence_scores_summary = {
                                            'min': min(confidences),
                                            'max': max(confidences),
                                            'avg': sum(confidences) / len(confidences),
                                            'count': len(confidences)
                                        }
                                        
                        except Exception as e:
                            logger.warning(f"Failed to extract job statistics from result: {e}")
                        
                        # Create or update a test record to store the results
                        test_id = f"{job_id}_result"
                        db_test = db.query(ProcessingTest).filter(ProcessingTest.test_id == test_id).first()
                        
                        # Serialize result to ensure JSON compatibility
                        def serialize_result(obj):
                            if isinstance(obj, dict):
                                return {k: serialize_result(v) for k, v in obj.items()}
                            elif isinstance(obj, list):
                                return [serialize_result(item) for item in obj]
                            elif hasattr(obj, 'isoformat'):  # datetime objects
                                return obj.isoformat()
                            elif hasattr(obj, 'dict'):  # Pydantic models
                                return obj.dict()
                            else:
                                return obj
                        
                        serialized_result = serialize_result(result)
                        
                        if not db_test:
                            # Create new test record for storing results
                            db_test = ProcessingTest(
                                test_id=test_id,
                                job_id=db_job.id,  # Fix: Set the foreign key properly
                                job_uuid=job_id,
                                entity_type=db_job.entity_type,
                                entity_id=db_job.entity_id,
                                action_type=db_job.action_type,
                                ai_model=db_job.ai_model or 'visage',  # Fix: Required field
                                status=TestResult.PASS.value,  # Fix: Use TestResult enum
                                created_at=datetime.utcnow(),
                                completed_at=datetime.utcnow(),
                                response_data=serialized_result
                            )
                            db.add(db_test)
                            logger.info(f"Created test record {test_id} to store job results")
                        else:
                            # Update existing test with results
                            db_test.response_data = serialized_result
                            db_test.status = TestResult.PASS.value
                            db_test.completed_at = datetime.utcnow()
                            logger.info(f"Updated test record {test_id} with job results")
                    
                    db.commit()
                    logger.info(f"Updated legacy database job status for {job_id}: {db_status}")
                else:
                    logger.warning(f"Job {job_id} not found in legacy database for status update")
            
        except Exception as e:
            logger.error(f"Failed to update database job status for {job_id}: {e}")
            import traceback
            logger.error(f"Database update traceback: {traceback.format_exc()}")
    
    def _update_job_status_and_results(self, job_id: str, status: str, result: Optional[Dict[str, Any]] = None, error: Optional[str] = None):
        """Update job status in database"""
        from database.database import DatabaseSession
        from database.models import ProcessingJob
        
        with DatabaseSession() as db:
            # Find the job
            job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if not job:
                logger.warning(f"Job {job_id} not found in database for status update")
                return
            
            # Update job status
            job.status = status
            if status in ["completed", "failed"]:
                job.completed_at = datetime.utcnow()
            
            if error:
                job.error_message = error
            
            # If job completed successfully, store result data
            if status == "completed" and result:
                try:
                    # Extract stats from result data
                    if isinstance(result, dict):
                        # Count performers found - handle gallery results format
                        performers_count = 0
                        
                        # Check if this is a gallery result with nested structure
                        gallery_results = None
                        if 'ai_model_info' in result and isinstance(result['ai_model_info'], dict):
                            gallery_results = result['ai_model_info'].get('gallery_results', {})
                        
                        if gallery_results and 'performers' in gallery_results:
                            performers_count = len(gallery_results['performers'])
                        elif 'performers' in result and isinstance(result['performers'], list):
                            performers_count = len([p for p in result['performers'] if p.get('confidence', 0) > 0])
                        elif 'performerFrequencies' in result and isinstance(result['performerFrequencies'], list):
                            performers_count = len(result['performerFrequencies'])
                        
                        job.performers_found_total = performers_count
                        
                        # Extract confidence scores if available
                        confidences = []
                        if gallery_results and 'performers' in gallery_results:
                            confidences = [p.get('averageConfidence', 0) for p in gallery_results['performers'] if p.get('averageConfidence', 0) > 0]
                        elif 'performers' in result:
                            confidences = [p.get('confidence', 0) for p in result['performers'] if p.get('confidence', 0) > 0]
                        elif 'performerFrequencies' in result:
                            confidences = [p.get('averageConfidence', 0) for p in result['performerFrequencies'] if p.get('averageConfidence', 0) > 0]
                        
                        if confidences:
                            job.confidence_scores_summary = {
                                "max": max(confidences),
                                "min": min(confidences),
                                "avg": sum(confidences) / len(confidences),
                                "count": len(confidences)
                            }
                        
                        # Get all tests for this job to include in results
                        from database.models import ProcessingTest
                        job_tests = db.query(ProcessingTest).filter(ProcessingTest.job_uuid == job_id).all()
                        
                        # Build comprehensive results including test information
                        comprehensive_results = {
                            # Original gallery results
                            **result,
                            
                            # Job summary
                            "job_summary": {
                                "job_id": job_id,
                                "total_tests": len(job_tests),
                                "tests_passed": sum(1 for t in job_tests if t.status == "pass"),
                                "tests_failed": sum(1 for t in job_tests if t.status == "fail"),
                                "tests_error": sum(1 for t in job_tests if t.status == "error"),
                                "performers_found_total": performers_count,
                                "confidence_summary": job.confidence_scores_summary if hasattr(job, 'confidence_scores_summary') and job.confidence_scores_summary else None
                            },
                            
                            # Individual test results
                            "test_results": [
                                {
                                    "test_id": test.test_id,
                                    "entity_id": test.entity_id,
                                    "entity_name": test.entity_name,
                                    "status": test.status,
                                    "performers_found": test.performers_found,
                                    "max_confidence": test.max_confidence,
                                    "processing_time": test.processing_time_seconds,
                                    "created_at": test.created_at.isoformat() if test.created_at else None,
                                    "completed_at": test.completed_at.isoformat() if test.completed_at else None,
                                    "response_data": test.response_data  # Full response for each test
                                } for test in job_tests
                            ]
                        }
                        
                        # Serialize comprehensive result data to ensure JSON compatibility
                        def serialize_for_json(obj):
                            if isinstance(obj, dict):
                                return {k: serialize_for_json(v) for k, v in obj.items()}
                            elif isinstance(obj, list):
                                return [serialize_for_json(item) for item in obj]
                            elif hasattr(obj, 'isoformat'):  # datetime objects
                                return obj.isoformat()
                            elif hasattr(obj, 'dict'):  # Pydantic models
                                return obj.dict()
                            else:
                                return obj
                        
                        # Store comprehensive result data
                        job.results_json = serialize_for_json(comprehensive_results)
                        
                        # Create or update test record to store the results (for compatibility)
                        from database.models import ProcessingTest, TestResult
                        test_id = f"{job_id}_result"  
                        db_test = db.query(ProcessingTest).filter(ProcessingTest.test_id == test_id).first()
                        
                        if not db_test:
                            # Create new test record for storing results
                            db_test = ProcessingTest(
                                test_id=test_id,
                                job_id=job.id,  # Foreign key reference
                                job_uuid=job_id,
                                entity_type=job.entity_type,
                                entity_id=job.entity_id,
                                action_type=job.action_type,
                                ai_model=job.ai_model or 'visage',
                                status=TestResult.PASS.value,
                                created_at=datetime.utcnow(),
                                completed_at=datetime.utcnow(),
                                response_data=serialize_for_json(result)
                            )
                            db.add(db_test)
                            logger.info(f"Created test record {test_id} to store job results")
                        else:
                            # Update existing test with results
                            db_test.response_data = serialize_for_json(result)
                            db_test.status = TestResult.PASS.value
                            db_test.completed_at = datetime.utcnow()
                            logger.info(f"Updated test record {test_id} with job results")
                        
                except Exception as e:
                    logger.warning(f"Failed to extract job statistics from result: {e}")
            
            db.commit()
            logger.info(f"Updated database job {job_id} to status: {status}")
    
    async def _worker(self):
        """Background worker to process jobs"""
        logger.info("Queue worker started processing")
        
        while self.processing:
            try:
                # Wait for a job (with timeout to allow checking self.processing)
                job = await asyncio.wait_for(self.pending_jobs.get(), timeout=1.0)
                
                # Check if job was cancelled before processing
                if job.status == JobStatus.CANCELLED:
                    logger.info(f"Job {job.job_id} was cancelled before processing")
                    continue
                    
                logger.info(f"Processing job {job.job_id}")
                job.status = JobStatus.PROCESSING
                job.started_at = datetime.utcnow()
                
                # Update database job status to processing
                self._update_database_job_status(job.job_id, "processing")
                
                # Broadcast job started event
                await self._broadcast_queue_update("job_started", job.job_id, {
                    "job_type": job.job_type,
                    "started_at": job.started_at.isoformat()
                })
                
                try:
                    # Process the job based on type
                    if job.job_type == "image":
                        result = await self._process_image_job(job)
                    elif job.job_type == "gallery":
                        result = await self._process_gallery_job(job)
                    elif job.job_type == "scene":
                        result = await self._process_scene_job(job)
                    else:
                        raise ValueError(f"Unknown job type: {job.job_type}")
                    
                    # Job completed successfully
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.utcnow()
                    job.result = result
                    logger.info(f"Job {job.job_id} completed successfully")
                    
                    # Update database job status to completed
                    logger.info(f"Updating database status for job {job.job_id} to completed")
                    self._update_database_job_status(job.job_id, "completed", result)
                    logger.info(f"Database update finished for job {job.job_id}")
                    
                    # Gather evaluation results for broadcast
                    evaluation_data = {}
                    if ENABLE_SCHEMA:
                        try:
                            # Get evaluation results from the database if available
                            from database.database import DatabaseSession
                            with DatabaseSession() as db:
                                job_record = db.query(ProcessingJob).filter(ProcessingJob.job_id == job.job_id).first()
                                if job_record:
                                    evaluation_data = {
                                        "overall_result": job_record.overall_result,
                                        "tests_passed": job_record.tests_passed,
                                        "tests_failed": job_record.tests_failed,
                                        "tests_error": job_record.tests_error,
                                        "performers_found_total": job_record.performers_found_total,
                                        "confidence_scores_summary": job_record.confidence_scores_summary,
                                        "evaluation_available": True
                                    }
                        except Exception as e:
                            logger.debug(f"Could not fetch evaluation data for broadcast: {e}")
                            evaluation_data = {"evaluation_available": False}
                    
                    # Broadcast job completed event with evaluation results
                    logger.info(f"📡 Broadcasting job_completed event for {job.job_id}")
                    await self._broadcast_queue_update("job_completed", job.job_id, {
                        "job_type": job.job_type,
                        "completed_at": job.completed_at.isoformat(),
                        "processing_time": (job.completed_at - job.started_at).total_seconds() if job.started_at else None,
                        "evaluation_results": evaluation_data
                    })
                    
                except asyncio.CancelledError:
                    # Job was cancelled during processing
                    if job.status != JobStatus.CANCELLED:
                        job.status = JobStatus.CANCELLED
                        job.completed_at = datetime.utcnow()
                        job.error = "Job cancelled during processing"
                        
                        # Update database job status to cancelled
                        self._update_database_job_status(job.job_id, "cancelled", error="Job cancelled during processing")
                        
                        # Broadcast job cancelled event
                        await self._broadcast_queue_update("job_cancelled", job.job_id, {
                            "job_type": job.job_type,
                            "cancelled_at": job.completed_at.isoformat(),
                            "reason": "Job cancelled during processing"
                        })
                    
                    logger.info(f"Job {job.job_id} was cancelled during processing")
                    
                except Exception as e:
                    # Job failed
                    job.status = JobStatus.FAILED
                    job.completed_at = datetime.utcnow()
                    job.error = str(e)
                    logger.error(f"Job {job.job_id} failed: {e}")
                    
                    # Update database job status to failed
                    self._update_database_job_status(job.job_id, "failed", error=str(e))
                    
                    # Broadcast job failed event
                    await self._broadcast_queue_update("job_failed", job.job_id, {
                        "job_type": job.job_type,
                        "failed_at": job.completed_at.isoformat(),
                        "error": str(e),
                        "processing_time": (job.completed_at - job.started_at).total_seconds() if job.started_at else None
                    })
                
            except asyncio.TimeoutError:
                # No job available, continue loop
                continue
            except asyncio.CancelledError:
                # Worker was cancelled
                break
            except Exception as e:
                logger.error(f"Queue worker error: {e}")
    
    async def _process_image_job(self, job: QueueJob) -> Dict[str, Any]:
        """Process an image identification job using the modular processor framework"""
        return await self._process_job_with_processor(job, 'image')

    async def _process_gallery_job(self, job: QueueJob) -> Dict[str, Any]:
        """Process a gallery identification job using the modular processor framework with progress tracking"""
        return await self._process_job_with_processor_and_progress(job, 'gallery')
    
    async def _process_gallery_job_legacy(self, job: QueueJob) -> Dict[str, Any]:
        """Legacy gallery processing method - kept for reference"""
        from main import identify_gallery_performers
        from schemas.api_schema import GalleryIdentificationRequest
        
        # Convert job data back to the request format your working function expects
        request = GalleryIdentificationRequest(**job.request_data)
        
        # Get image count for progress tracking
        total_images = len(request.images) if request.images else 1
        
        # Send initial progress
        await self.broadcast_progress(job.job_id, 0, total_images, "Starting gallery processing...")
        
        # Create real-time progress callback
        async def progress_callback(current, total, message):
            """Real-time progress callback for actual processing"""
            if job.status != JobStatus.CANCELLED:
                await self.broadcast_progress(job.job_id, current, total, message)
        
        # Create cancellation check callback
        async def cancellation_check():
            """Check if job has been cancelled"""
            return job.status == JobStatus.CANCELLED
        
        try:
            # Call your existing working function
            logger.info(f"Starting identify_gallery_performers for job {job.job_id}")
            
            # Check if job was cancelled before starting processing
            if job.status == JobStatus.CANCELLED:
                raise asyncio.CancelledError("Job was cancelled")
            
            response = await identify_gallery_performers(request, progress_callback, cancellation_check, job.job_id)
            logger.info(f"identify_gallery_performers completed for job {job.job_id}, response type: {type(response)}")
            
            # Check if job was cancelled during processing
            if job.status == JobStatus.CANCELLED:
                raise asyncio.CancelledError("Job was cancelled during processing")
            
            # Send final progress
            await self.broadcast_progress(job.job_id, total_images, total_images, "Gallery processing completed!")
            
        except asyncio.CancelledError:
            logger.info(f"Gallery processing cancelled for job {job.job_id}")
            raise asyncio.CancelledError("Job was cancelled")
        except Exception as e:
            logger.error(f"Error in identify_gallery_performers for job {job.job_id}: {e}")
            import traceback
            logger.error(f"Gallery processing traceback: {traceback.format_exc()}")
            raise e
        
        # Convert response to dict
        if hasattr(response, 'dict'):
            return response.dict()
        else:
            return {
                "success": getattr(response, 'success', True),
                "message": getattr(response, 'message', 'Completed'),
                "request_id": getattr(response, 'request_id', job.job_id),
                "processing_time": getattr(response, 'processing_time', 0.0),
                "service_name": getattr(response, 'service_name', 'visage')
            }

    async def _process_scene_job(self, job: QueueJob) -> Dict[str, Any]:
        """Process a scene identification job using the modular processor framework"""
        return await self._process_job_with_processor(job, 'scene')
    
    async def _process_job_with_processor_and_progress(self, job: QueueJob, processor_type: str) -> Dict[str, Any]:
        """
        Process job with modular processor framework including progress tracking for gallery jobs.
        """
        from processors import get_processor
        from schemas.api_schema import SceneIdentificationRequest, GalleryIdentificationRequest, FacialRecognitionRequest
        
        # Check for cancellation before processing
        if job.status == JobStatus.CANCELLED:
            raise asyncio.CancelledError("Job was cancelled")
        
        # Get the appropriate processor
        processor = get_processor(processor_type)
        
        # Convert job data back to the request format
        request_class_map = {
            'scene': SceneIdentificationRequest,
            'gallery': GalleryIdentificationRequest,
            'image': FacialRecognitionRequest
        }
        
        if processor_type not in request_class_map:
            raise ValueError(f"Unknown processor type: {processor_type}")
        
        request_class = request_class_map[processor_type]
        request = request_class(**job.request_data)
        
        # Progress tracking for gallery jobs
        if processor_type == 'gallery':
            total_images = len(request.images) if request.images else 1
            await self.broadcast_progress(job.job_id, 0, total_images, "Starting gallery processing...")
            
            # Create real-time progress callback
            async def progress_callback(current, total, message):
                """Real-time progress callback for actual processing"""
                if job.status != JobStatus.CANCELLED:
                    await self.broadcast_progress(job.job_id, current, total, message)
        else:
            progress_callback = None
        
        # Create cancellation check callback
        async def cancellation_check():
            """Check if job has been cancelled"""
            return job.status == JobStatus.CANCELLED
        
        try:
            logger.info(f"Starting {processor_type} processing for job {job.job_id}")
            
            # Process with full database tracking using modular framework
            response, _ = await processor.process_with_tracking(
                request=request,
                job_id=job.job_id,
                progress_callback=progress_callback,
                cancellation_check=cancellation_check
            )
            
            logger.info(f"{processor_type} processing completed for job {job.job_id}, response type: {type(response)}")
            
            # Check if job was cancelled during processing  
            if job.status == JobStatus.CANCELLED:
                raise asyncio.CancelledError("Job was cancelled during processing")
            
            # Send final progress for gallery jobs
            if processor_type == 'gallery':
                await self.broadcast_progress(job.job_id, total_images, total_images, "Gallery processing completed!")
            
        except asyncio.CancelledError:
            logger.info(f"{processor_type} processing cancelled for job {job.job_id}")
            raise asyncio.CancelledError("Job was cancelled")
        except Exception as e:
            logger.error(f"Error in {processor_type} processing for job {job.job_id}: {e}")
            import traceback
            logger.error(f"{processor_type} processing traceback: {traceback.format_exc()}")
            raise e
        
        # Convert response to dict
        if hasattr(response, 'dict'):
            return response.dict()
        else:
            return {
                "success": getattr(response, 'success', True),
                "message": getattr(response, 'message', 'Completed'),
                "request_id": getattr(response, 'request_id', job.job_id),
                "processing_time": getattr(response, 'processing_time', 0.0),
                "service_name": getattr(response, 'service_name', 'visage')
            }
    
    async def _process_job_with_processor(self, job: QueueJob, processor_type: str) -> Dict[str, Any]:
        """
        Generic job processing method using the modular processor framework.
        This provides consistent database tracking and job management across all API types.
        """
        from processors import get_processor
        from schemas.api_schema import SceneIdentificationRequest, GalleryIdentificationRequest, FacialRecognitionRequest
        
        # Check for cancellation before processing
        if job.status == JobStatus.CANCELLED:
            raise asyncio.CancelledError("Job was cancelled")
        
        # Get the appropriate processor
        processor = get_processor(processor_type)
        
        # Convert job data back to the request format
        request_class_map = {
            'scene': SceneIdentificationRequest,
            'gallery': GalleryIdentificationRequest,
            'image': FacialRecognitionRequest
        }
        
        if processor_type not in request_class_map:
            raise ValueError(f"Unknown processor type: {processor_type}")
        
        request_class = request_class_map[processor_type]
        request = request_class(**job.request_data)
        
        # Create cancellation check callback
        async def cancellation_check():
            """Check if job has been cancelled"""
            return job.status == JobStatus.CANCELLED
        
        # Process with full database tracking
        response, _ = await processor.process_with_tracking(
            request=request,
            job_id=job.job_id,
            cancellation_check=cancellation_check
        )
        
        # Convert response to dict
        if hasattr(response, 'dict'):
            return response.dict()
        else:
            return {
                "success": getattr(response, 'success', True),
                "message": getattr(response, 'message', 'Completed'),
                "request_id": getattr(response, 'request_id', job.job_id),
                "processing_time": getattr(response, 'processing_time', 0.0),
                "service_name": getattr(response, 'service_name', 'visage')
            }

# Global queue instance
simple_queue = SimpleQueue()