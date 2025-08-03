# =============================================================================
# StashAI Server - Interactions Database Service
# =============================================================================

import os
import json
import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_, or_, func, text

from .database import DatabaseSession, db_manager
from .models import (
    # Use ProcessingJob, ProcessingTest directly (clean schema)
    ProcessingJob, ProcessingTest, Interaction,
    ProcessingJobCreate, ProcessingJobUpdate, ProcessingTestCreate, ProcessingTestUpdate,
    # API Models
    JobCreate, JobUpdate, JobResponse,
    TestCreate, TestUpdate, TestResponse,
    InteractionCreate, InteractionResponse,
    JobHistoryQuery, JobHistoryResponse,
    # Enums
    EntityType, AIActionType, JobStatus, TestResult, AIModel,
    # Legacy aliases for API compatibility
    AIJob, AITest,
    AIJobCreate, AIJobUpdate, AIJobResponse,
    AITestCreate, AITestUpdate, AITestResponse,
    AIJobHistoryQuery, AIJobHistoryResponse
)

logger = logging.getLogger(__name__)

# =============================================================================
# AI Runs Directory Management
# =============================================================================

class AIRunsStorage:
    """Manages file storage for AI run results"""
    
    def __init__(self, base_path: str = None):
        if base_path is None:
            # Default to AIruns folder in StashAIServer directory
            server_dir = os.path.dirname(os.path.dirname(__file__))
            base_path = os.path.join(server_dir, "AIruns")
        
        self.base_path = base_path
        self.ensure_directories()
    
    def ensure_directories(self):
        """Create necessary directories"""
        directories = [
            self.base_path,
            os.path.join(self.base_path, "facial_recognition"),
            os.path.join(self.base_path, "scene_identification"),
            os.path.join(self.base_path, "gallery_identification"),
            os.path.join(self.base_path, "batch_processing"),
            os.path.join(self.base_path, "content_analysis")
        ]
        
        for directory in directories:
            os.makedirs(directory, exist_ok=True)
    
    def get_result_file_path(self, run_id: str, action_type: AIActionType) -> str:
        """Get the file path for storing a run's results"""
        # Create subdirectory based on action type
        subdir = action_type.value
        filename = f"{run_id}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        return os.path.join(self.base_path, subdir, filename)
    
    def save_results_to_file(self, file_path: str, results: Dict[str, Any]) -> Tuple[str, int]:
        """Save results to file and return checksum and file size"""
        try:
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write results to file
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, default=str)
            
            # Calculate checksum and file size
            file_size = os.path.getsize(file_path)
            
            with open(file_path, 'rb') as f:
                checksum = hashlib.sha256(f.read()).hexdigest()
            
            logger.info(f"Saved AI run results to {file_path} ({file_size} bytes)")
            return checksum, file_size
            
        except Exception as e:
            logger.error(f"Failed to save results to file {file_path}: {e}")
            raise
    
    def load_results_from_file(self, file_path: str) -> Dict[str, Any]:
        """Load results from file"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Results file not found: {file_path}")
            
            with open(file_path, 'r', encoding='utf-8') as f:
                results = json.load(f)
            
            logger.debug(f"Loaded AI run results from {file_path}")
            return results
            
        except Exception as e:
            logger.error(f"Failed to load results from file {file_path}: {e}")
            raise
    
    def cleanup_old_files(self, days_old: int = 30):
        """Clean up result files older than specified days"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        deleted_count = 0
        
        try:
            for root, dirs, files in os.walk(self.base_path):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                        
                        if file_mtime < cutoff_date:
                            os.remove(file_path)
                            deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} old result files (older than {days_old} days)")
            
        except Exception as e:
            logger.error(f"Failed to cleanup old result files: {e}")

# =============================================================================
# Interactions Database Service
# =============================================================================

class InteractionsService:
    """Service for managing AI jobs, tests, and interactions using Job ID → Test ID → Entity hierarchy"""
    
    def __init__(self):
        self.storage = AIRunsStorage()
    
    # =========================================================================
    # Job Management (Primary organizational unit) 
    # =========================================================================
    
    def create_ai_job(self, job_data: AIJobCreate, job_id: str = None) -> AIJobResponse:
        """Create a new AI job record"""
        import uuid
        
        return self._create_job(job_data, job_id)
    
    def _create_job(self, job_data: AIJobCreate, job_id: str = None) -> AIJobResponse:
        """Create job using ProcessingJob schema"""
        import uuid
        
        with DatabaseSession() as db:
            if job_id is None:
                # Create properly formatted job ID for UI to recognize as server job
                action_name = job_data.action_type.value.split('_')[0]  # Get 'image', 'gallery', 'scene' etc.
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                short_uuid = str(uuid.uuid4())[:8]
                job_id = f"{action_name}_{timestamp}_{short_uuid}"
            
            # Generate human-readable job name if not provided
            if not job_data.job_name:
                job_name = f"{job_data.action_type.value.title()} - {job_data.entity_type.value.title()}"
                if job_data.entity_name:
                    job_name += f" '{job_data.entity_name}'"
                job_data.job_name = job_name
            
            # Create ProcessingJob
            db_job = ProcessingJob(
                job_id=job_id,
                job_name=job_data.job_name,
                entity_type=job_data.entity_type.value,
                entity_id=job_data.entity_id,
                entity_name=job_data.entity_name,
                action_type=job_data.action_type.value,
                status=JobStatus.PENDING.value,
                created_at=datetime.utcnow(),
                job_config=job_data.job_config or {},
                ai_model=AIModel.VISAGE.value,  # Default model
                total_tests_planned=len(job_data.test_entity_list) if job_data.test_entity_list else 1,
                test_entity_list=job_data.test_entity_list or [{"entity_id": job_data.entity_id, "filepath": ""}]
            )
            
            db.add(db_job)
            db.commit()
            db.refresh(db_job)
            
            logger.info(f"Created AI job {job_id}: {job_data.job_name}")
            
            # Convert job to response format
            return self._convert_job_to_response(db_job)
    
    def _create_legacy_job(self, job_data: AIJobCreate, job_id: str = None) -> AIJobResponse:
        """Create job using legacy AIJob schema"""
        import uuid
        
        with DatabaseSession() as db:
            if job_id is None:
                # Create properly formatted job ID for UI to recognize as server job
                action_name = job_data.action_type.value.split('_')[0]  # Get 'image', 'gallery', 'scene' etc.
                timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
                short_uuid = str(uuid.uuid4())[:8]
                job_id = f"{action_name}_{timestamp}_{short_uuid}"
            
            # Generate human-readable job name if not provided
            if not job_data.job_name:
                job_name = f"{job_data.action_type.value.title()} - {job_data.entity_type.value.title()}"
                if job_data.entity_name:
                    job_name += f" '{job_data.entity_name}'"
                job_data.job_name = job_name
            
            db_job = AIJob(
                job_id=job_id,
                job_name=job_data.job_name,
                entity_type=job_data.entity_type.value,
                entity_id=job_data.entity_id,
                entity_name=job_data.entity_name,
                action_type=job_data.action_type.value,
                status=TestResult.PENDING.value,
                job_config=job_data.job_config,
                total_tests_planned=1  # Default for legacy compatibility
            )
            
            db.add(db_job)
            db.commit()
            db.refresh(db_job)
            
            logger.info(f"Created legacy AI job {job_id}: {job_data.job_name}")
            return AIJobResponse.from_orm(db_job)
    
    def _convert_job_to_response(self, job: ProcessingJob) -> AIJobResponse:
        """Convert ProcessingJob to AIJobResponse format"""
        return AIJobResponse(
            id=job.id,
            job_id=job.job_id,
            job_name=job.job_name,
            entity_type=EntityType(job.entity_type),
            entity_id=job.entity_id,
            entity_name=job.entity_name,
            action_type=AIActionType(job.action_type),
            status=JobStatus(job.status),
            created_at=job.created_at,
            started_at=job.started_at,
            completed_at=job.completed_at,
            processing_time=job.processing_time_seconds,
            service_name=job.service_name,
            progress_percentage=job.progress_percentage,
            total_items=job.total_tests_planned,
            successful_items=job.tests_passed,
            failed_items=job.tests_failed,
            skipped_items=job.tests_error,
            top_confidence_score=job.confidence_scores_summary.get('max') if job.confidence_scores_summary else None,
            avg_confidence_score=job.confidence_scores_summary.get('avg') if job.confidence_scores_summary else None,
            has_errors=job.error_message is not None
        )
    
    def create_ai_test(self, job_id: str, test_data: AITestCreate, test_id: str = None) -> AITestResponse:
        """Create a new AI test within a job - individual entity processing"""
        import uuid
        
        with DatabaseSession() as db:
            # Get the parent job
            db_job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
                
            if not db_job:
                raise ValueError(f"Job {job_id} not found")
            
            if test_id is None:
                test_id = str(uuid.uuid4())
            
            # Generate human-readable test name if not provided
            if not test_data.test_name:
                test_name = f"{test_data.entity_type.value.title()} {test_data.entity_id}"
                if test_data.entity_name:
                    test_name = f"{test_data.entity_name}"
                test_data.test_name = test_name
            
            db_test = ProcessingTest(
                test_id=test_id,
                job_id=db_job.id,
                job_uuid=job_id,
                entity_type=test_data.entity_type.value,
                entity_id=test_data.entity_id,
                entity_filepath=test_data.entity_filepath,
                entity_name=test_data.entity_name,
                test_name=test_data.test_name,
                action_type=test_data.action_type.value,
                ai_model=test_data.ai_model.value,
                status=TestResult.PENDING.value,
                test_config=test_data.test_config
            )
            
            db.add(db_test)
            db.commit()
            db.refresh(db_test)
            
            logger.info(f"Created AI test {test_id} in job {job_id} for {test_data.entity_type}:{test_data.entity_id}")
            return AITestResponse.from_orm(db_test)
    
    def complete_ai_test(self, test_id: str, response_data: Dict[str, Any], 
                        service_name: str = None, processing_time: float = None) -> Optional[AITestResponse]:
        """Mark an AI test as completed and store results"""
        import json
        
        with DatabaseSession() as db:
            db_test = db.query(ProcessingTest).filter(ProcessingTest.test_id == test_id).first()
            if not db_test:
                logger.warning(f"AI test {test_id} not found for completion")
                return None
            
            # Update test status
            db_test.status = TestResult.PASS.value
            db_test.completed_at = datetime.utcnow()
            db_test.response_data = response_data
            logger.info(f"Storing response_data for test {test_id}: {bool(response_data)} - Keys: {list(response_data.keys()) if response_data else 'None'}")
            if service_name:
                db_test.service_name = service_name
            
            if processing_time:
                db_test.processing_time = processing_time
            elif db_test.started_at:
                db_test.processing_time = (db_test.completed_at - db_test.started_at).total_seconds()
            
            # Extract result summary
            if response_data and "performers" in response_data:
                performers = response_data.get("performers", [])
                db_test.performers_found = len(performers)
                
                if performers:
                    confidences = []
                    for performer in performers:
                        if isinstance(performer, dict) and "confidence" in performer:
                            confidences.append(performer["confidence"])
                    
                    if confidences:
                        db_test.confidence_scores = confidences
                        db_test.max_confidence = max(confidences)
            
            # Update parent job statistics before committing
            self._update_job_statistics(db, db_test.job_uuid, commit=False)
            
            db.commit()
            db.refresh(db_test)
            
            # Entity registry removed - no longer needed
            
            logger.info(f"Completed AI test {test_id}")
            return AITestResponse.from_orm(db_test)
    
    def fail_ai_test(self, test_id: str, error_message: str) -> Optional[AITestResponse]:
        """Mark an AI test as failed"""
        
        with DatabaseSession() as db:
            db_test = db.query(ProcessingTest).filter(ProcessingTest.test_id == test_id).first()
            if not db_test:
                logger.warning(f"AI test {test_id} not found for failure")
                return None
            
            db_test.status = TestResult.FAIL.value
            db_test.completed_at = datetime.utcnow()
            db_test.error_message = error_message
            
            if db_test.started_at:
                db_test.processing_time = (db_test.completed_at - db_test.started_at).total_seconds()
            
            # Update parent job statistics before committing
            self._update_job_statistics(db, db_test.job_uuid, commit=False)
            
            db.commit()
            db.refresh(db_test)
            
            logger.warning(f"Failed AI test {test_id}: {error_message}")
            return AITestResponse.from_orm(db_test)
    
    def get_ai_job(self, job_id: str) -> Optional[AIJobResponse]:
        """Get AI job by ID"""
        return self._get_job(job_id)
    
    def _get_job(self, job_id: str) -> Optional[AIJobResponse]:
        """Get job using ProcessingJob schema"""
        with DatabaseSession() as db:
            db_job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if db_job:
                return self._convert_job_to_response(db_job)
            return None
    
    def _get_legacy_job(self, job_id: str) -> Optional[AIJobResponse]:
        """Get job using legacy AIJob schema"""
        with DatabaseSession() as db:
            db_job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if db_job:
                return AIJobResponse.from_orm(db_job)
            return None
    
    def get_active_jobs(self) -> List[AIJobResponse]:
        """Get all active jobs (pending or in_progress)"""
        with DatabaseSession() as db:
            active_jobs = db.query(ProcessingJob).filter(
                AIJob.status.in_(['pending', 'in_progress'])
            ).order_by(AIJob.created_at.desc()).all()
            
            return [AIJobResponse.from_orm(job) for job in active_jobs]
    
    def get_recent_completed_jobs(self, limit: int = 10) -> List[AIJobResponse]:
        """Get recently completed AI jobs for result viewing"""
        return self._get_completed_jobs(limit)
    
    def _get_completed_jobs(self, limit: int = 10) -> List[AIJobResponse]:
        """Get completed jobs"""
        with DatabaseSession() as db:
            completed_jobs = db.query(ProcessingJob).filter(
                ProcessingJob.status == JobStatus.COMPLETED.value
            ).order_by(ProcessingJob.completed_at.desc()).limit(limit).all()
            
            return [self._convert_job_to_response(job) for job in completed_jobs]
    
    def _get_legacy_completed_jobs(self, limit: int = 10) -> List[AIJobResponse]:
        """Get completed jobs using legacy schema"""
        with DatabaseSession() as db:
            completed_jobs = db.query(ProcessingJob).filter(
                AIJob.status == 'completed'
            ).order_by(AIJob.completed_at.desc()).limit(limit).all()
            
            return [AIJobResponse.from_orm(job) for job in completed_jobs]
    
    def get_ai_test(self, test_id: str) -> Optional[AITestResponse]:
        """Get AI test by ID"""
        with DatabaseSession() as db:
            db_test = db.query(ProcessingTest).filter(ProcessingTest.test_id == test_id).first()
            if db_test:
                return AITestResponse.from_orm(db_test)
            return None
    
    def start_ai_test(self, test_id: str) -> Optional[AITestResponse]:
        """Mark an AI test as started"""
        
        with DatabaseSession() as db:
            db_test = db.query(ProcessingTest).filter(ProcessingTest.test_id == test_id).first()
            if not db_test:
                logger.warning(f"AI test {test_id} not found for starting")
                return None
            
            db_test.status = TestResult.PENDING.value
            db_test.started_at = datetime.utcnow()
            
            db.commit()
            db.refresh(db_test)
            
            logger.info(f"Started AI test {test_id}")
            return AITestResponse.from_orm(db_test)
    
    def get_tests_for_job(self, job_id: str) -> List[AITestResponse]:
        """Get all tests for a job"""
        with DatabaseSession() as db:
            tests = db.query(ProcessingTest).filter(ProcessingTest.job_uuid == job_id).order_by(ProcessingTest.created_at).all()
            return [AITestResponse.from_orm(test) for test in tests]
    
    def cancel_ai_job(self, job_id: str) -> Optional[AIJobResponse]:
        """Cancel an AI job and all its pending/processing tests"""
        
        with DatabaseSession() as db:
            # Get the job
            db_job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if not db_job:
                logger.warning(f"AI job {job_id} not found for cancellation")
                return None
            
            # Can only cancel pending or in_progress jobs
            if db_job.status not in ['pending', 'in_progress']:
                logger.warning(f"Cannot cancel AI job {job_id} with status {db_job.status}")
                return None
            
            # Cancel the job
            db_job.status = JobStatus.CANCELLED.value
            db_job.completed_at = datetime.utcnow()
            
            # Cancel all pending/processing tests in this job
            cancelled_tests = db.query(ProcessingTest).filter(
                ProcessingTest.job_uuid == job_id,
                ProcessingTest.status.in_(['pending', 'processing'])
            ).all()
            
            for test in cancelled_tests:
                test.status = TestResult.ERROR.value
                test.completed_at = datetime.utcnow()
                test.error_message = "Cancelled by user request"
                logger.info(f"Cancelled AI test {test.test_id}")
            
            db.commit()
            db.refresh(db_job)
            
            # Update job statistics
            self._update_job_statistics(db, job_id)
            
            logger.info(f"Cancelled AI job {job_id} with {len(cancelled_tests)} tests")
            return AIJobResponse.from_orm(db_job)
    
    def cancel_ai_test(self, test_id: str) -> Optional[AITestResponse]:
        """Cancel a specific AI test"""
        
        with DatabaseSession() as db:
            db_test = db.query(ProcessingTest).filter(ProcessingTest.test_id == test_id).first()
            if not db_test:
                logger.warning(f"AI test {test_id} not found for cancellation")
                return None
            
            # Can only cancel pending or processing tests
            if db_test.status not in ['pending', 'processing']:
                logger.warning(f"Cannot cancel AI test {test_id} with status {db_test.status}")
                return None
            
            # Cancel the test
            db_test.status = TestResult.ERROR.value
            db_test.completed_at = datetime.utcnow()
            db_test.error_message = "Cancelled by user request"
            
            if db_test.started_at:
                db_test.processing_time = (db_test.completed_at - db_test.started_at).total_seconds()
            
            db.commit()
            db.refresh(db_test)
            
            # Update parent job statistics
            self._update_job_statistics(db, db_test.job_uuid)
            
            logger.info(f"Cancelled AI test {test_id}")
            return AITestResponse.from_orm(db_test)
    
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _update_job_statistics(self, db: Session, job_uuid: str, commit: bool = True):
        """Update job-level statistics based on test results"""
        db_job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_uuid).first()
        if not db_job:
            return
        
        # Count test statuses
        tests = db.query(ProcessingTest).filter(ProcessingTest.job_uuid == job_uuid).all()
        
        passed_tests = sum(1 for t in tests if t.status == TestResult.PASS.value)
        failed_tests = sum(1 for t in tests if t.status == TestResult.FAIL.value)
        error_tests = sum(1 for t in tests if t.status == TestResult.ERROR.value)
        completed_tests = passed_tests + failed_tests + error_tests
        total_tests = len(tests)
        
        # Update job statistics with correct field names
        db_job.tests_completed = completed_tests
        db_job.tests_passed = passed_tests
        db_job.tests_failed = failed_tests
        db_job.tests_error = error_tests
        db_job.progress_percentage = (completed_tests / max(total_tests, 1)) * 100
        
        # Aggregate confidence scores into JSON summary
        confidence_tests = [t for t in tests if t.status == TestResult.PASS.value and t.max_confidence]
        if confidence_tests:
            confidences = [t.max_confidence for t in confidence_tests]
            db_job.confidence_scores_summary = {
                'min': min(confidences),
                'max': max(confidences),
                'avg': sum(confidences) / len(confidences),
                'count': len(confidences)
            }
        
        # Update job status
        if completed_tests >= total_tests:
            db_job.status = JobStatus.COMPLETED.value if failed_tests == 0 and error_tests == 0 else JobStatus.FAILED.value
        
        if commit:
            db.commit()
    

    
    # =========================================================================
    # Entity Interaction Tracking
    # =========================================================================
    
    def track_interaction(self, interaction_data: InteractionCreate) -> InteractionResponse:
        """Track an interaction using the unified interactions table"""
        with DatabaseSession() as db:
            db_interaction = Interaction(
                entity_type=interaction_data.entity_type.value,
                entity_id=interaction_data.entity_id,
                session_id=interaction_data.session_id,
                service=interaction_data.service,
                action_type=interaction_data.action_type,
                user_id=interaction_data.user_id,
                interaction_metadata=interaction_data.metadata
            )
            
            db.add(db_interaction)
            db.commit()
            db.refresh(db_interaction)
            
            logger.debug(f"Tracked interaction for {interaction_data.entity_type}:{interaction_data.entity_id}")
            
            # Convert to response format
            return InteractionResponse(
                id=db_interaction.id,
                entity_type=EntityType(db_interaction.entity_type),
                entity_id=db_interaction.entity_id,
                session_id=db_interaction.session_id,
                timestamp=db_interaction.timestamp,
                service=db_interaction.service,
                action_type=db_interaction.action_type,
                user_id=db_interaction.user_id,
                metadata=db_interaction.interaction_metadata
            )
    
    def get_entity_last_interaction(self, entity_type: EntityType, entity_id: str, 
                                  action_type: str = None) -> Optional[InteractionResponse]:
        """Get the last interaction for a specific entity"""
        with DatabaseSession() as db:
            query = db.query(Interaction).filter(
                Interaction.entity_type == entity_type.value,
                Interaction.entity_id == entity_id
            )
            
            if action_type:
                query = query.filter(Interaction.action_type == action_type)
            
            interaction = query.order_by(desc(Interaction.timestamp)).first()
            
            if interaction:
                return InteractionResponse.from_orm(interaction)
            return None
    
    def get_entity_interaction_history(self, entity_type: EntityType, entity_id: str,
                                     limit: int = 10) -> List[InteractionResponse]:
        """Get interaction history for a specific entity"""
        with DatabaseSession() as db:
            interactions = db.query(Interaction).filter(
                Interaction.entity_type == entity_type.value,
                Interaction.entity_id == entity_id
            ).order_by(desc(Interaction.timestamp)).limit(limit).all()
            
            return [InteractionResponse.from_orm(i) for i in interactions]
    
    def get_interaction_by_id(self, interaction_id: int) -> Optional[InteractionResponse]:
        """Get a specific interaction by its database ID"""
        with DatabaseSession() as db:
            interaction = db.query(Interaction).filter(
                Interaction.id == interaction_id
            ).first()
            
            if interaction:
                return InteractionResponse.from_orm(interaction)
            return None
    
    def get_recent_interactions(self, limit: int = 100) -> List[InteractionResponse]:
        """Get recent interactions for general lookup"""
        with DatabaseSession() as db:
            interactions = db.query(Interaction).order_by(
                desc(Interaction.timestamp)
            ).limit(limit).all()
            
            return [InteractionResponse.from_orm(i) for i in interactions]
    
    # =========================================================================
    # Job History and Querying
    # =========================================================================
    
    def query_ai_job_history(self, query: AIJobHistoryQuery) -> AIJobHistoryResponse:
        """Query AI job history with filters and pagination"""
        with DatabaseSession() as db:
            # Build base query with test relationships loaded
            db_query = db.query(ProcessingJob)
            
            # Apply filters
            if query.entity_type:
                db_query = db_query.filter(ProcessingJob.entity_type == query.entity_type.value)
            
            if query.entity_id:
                db_query = db_query.filter(ProcessingJob.entity_id == query.entity_id)
            
            if query.action_type:
                db_query = db_query.filter(ProcessingJob.action_type == query.action_type.value)
            
            if query.status:
                db_query = db_query.filter(ProcessingJob.status == query.status.value)
            
            if query.job_name:
                db_query = db_query.filter(ProcessingJob.job_name.ilike(f"%{query.job_name}%"))
            
            if query.start_date:
                db_query = db_query.filter(ProcessingJob.created_at >= query.start_date)
            
            if query.end_date:
                db_query = db_query.filter(ProcessingJob.created_at <= query.end_date)
            
            # Get total count
            total_count = db_query.count()
            
            # Apply pagination and ordering
            jobs = db_query.order_by(desc(ProcessingJob.created_at)).offset(query.offset).limit(query.limit).all()
            
            # Check if there are more results
            has_more = (query.offset + len(jobs)) < total_count
            
            # Calculate pagination info
            page = (query.offset // query.limit) + 1 if query.limit > 0 else 1
            
            return JobHistoryResponse(
                jobs=[JobResponse.from_orm(job) for job in jobs],
                total_count=total_count,
                page=page,
                page_size=query.limit,
                has_more=has_more
            )
    
    def get_job_results(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed results for an AI job from the consolidated schema"""
        with DatabaseSession() as db:
            # Get job with results stored directly in the job table
            db_job = db.query(ProcessingJob).filter(ProcessingJob.job_id == job_id).first()
            if not db_job:
                return None
            
            # Return results directly from job table
            if db_job.results_json:
                return db_job.results_json
            
            # If no aggregated results, collect from individual tests
            tests = db.query(ProcessingTest).filter(ProcessingTest.job_uuid == job_id).all()
            if tests:
                aggregated_results = {
                    "job_id": job_id,
                    "tests": [
                        {
                            "test_id": test.test_id,
                            "entity_id": test.entity_id,
                            "entity_type": test.entity_type,
                            "status": test.status,
                            "response_data": test.response_data
                        } for test in tests
                    ]
                }
                return aggregated_results
            
            return None
    
    # =========================================================================
    # Caching and Performance
    # =========================================================================
    
    def check_cached_results(self, entity_type: EntityType, entity_id: str, 
                           action_type: AIActionType, max_age_hours: int = 24) -> Optional[Dict[str, Any]]:
        """Check for cached results within the specified age"""
        cutoff_time = datetime.utcnow() - timedelta(hours=max_age_hours)
        
        with DatabaseSession() as db:
            # Find recent successful test for this entity
            recent_test = db.query(ProcessingTest).filter(
                AITest.entity_type == entity_type.value,
                AITest.entity_id == entity_id,
                AITest.action_type == action_type.value,
                AITest.status == JobStatus.COMPLETED.value,
                AITest.completed_at >= cutoff_time
            ).order_by(desc(AITest.completed_at)).first()
            
            if recent_test:
                logger.info(f"Found cached results for {entity_type}:{entity_id} (test {recent_test.test_id})")
                return recent_test.response_data
            
            return None
    
    def cleanup_old_data(self, days_old: int = 90):
        """Clean up old AI jobs and results"""
        cutoff_date = datetime.utcnow() - timedelta(days=days_old)
        
        with DatabaseSession() as db:
            # Delete old AI jobs (cascade will handle related records)
            deleted_jobs = db.query(ProcessingJob).filter(ProcessingJob.created_at < cutoff_date).count()
            db.query(ProcessingJob).filter(ProcessingJob.created_at < cutoff_date).delete()
            
            db.commit()
            logger.info(f"Cleaned up {deleted_jobs} old AI jobs (older than {days_old} days)")
        
        # Clean up old result files
        self.storage.cleanup_old_files(days_old)
    
    # =========================================================================
    # Statistics and Analytics
    # =========================================================================
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get interaction statistics"""
        with DatabaseSession() as db:
            # AI job stats
            total_jobs = db.query(ProcessingJob).count()
            completed_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == JobStatus.COMPLETED.value).count()
            failed_jobs = db.query(ProcessingJob).filter(ProcessingJob.status == JobStatus.FAILED.value).count()
            
            # AI test stats
            total_tests = db.query(ProcessingTest).count()
            completed_tests = db.query(ProcessingTest).filter(ProcessingTest.status == TestResult.PASS.value).count()
            failed_tests = db.query(ProcessingTest).filter(ProcessingTest.status == TestResult.FAIL.value).count()
            
            # Recent activity (last 24 hours)
            recent_cutoff = datetime.utcnow() - timedelta(hours=24)
            recent_jobs = db.query(ProcessingJob).filter(ProcessingJob.created_at >= recent_cutoff).count()
            recent_tests = db.query(ProcessingTest).filter(ProcessingTest.created_at >= recent_cutoff).count()
            
            # Action type breakdown
            action_stats = db.query(
                ProcessingJob.action_type, 
                func.count(ProcessingJob.id).label('count')
            ).group_by(ProcessingJob.action_type).all()
            
            # Entity type breakdown
            entity_stats = db.query(
                ProcessingJob.entity_type,
                func.count(ProcessingJob.id).label('count')
            ).group_by(ProcessingJob.entity_type).all()
            
            # Average processing time
            avg_processing_time = db.query(func.avg(ProcessingTest.processing_time_seconds)).filter(
                ProcessingTest.processing_time_seconds.isnot(None)
            ).scalar()
            
            return {
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "failed_jobs": failed_jobs,
                "total_tests": total_tests,
                "completed_tests": completed_tests,
                "failed_tests": failed_tests,
                "job_success_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
                "test_success_rate": (completed_tests / total_tests * 100) if total_tests > 0 else 0,
                "recent_jobs_24h": recent_jobs,
                "recent_tests_24h": recent_tests,
                "average_processing_time": float(avg_processing_time) if avg_processing_time else 0,
                "action_type_breakdown": {stat.action_type: stat.count for stat in action_stats},
                "entity_type_breakdown": {stat.entity_type: stat.count for stat in entity_stats}
            }
    
    # =========================================================================
    # Enhanced Features
    # =========================================================================
    
    def get_jobs_with_evaluation_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get jobs with detailed evaluation results"""
        
        with DatabaseSession() as db:
            # Query ProcessingJobs with their tests
            jobs = db.query(ProcessingJob).order_by(ProcessingJob.created_at.desc()).limit(limit).all()
            
            result = []
            for job in jobs:
                # Get associated tests with evaluation results
                tests = db.query(ProcessingTest).filter(ProcessingTest.job_id == job.id).all()
                
                job_data = {
                    "job_id": job.job_id,
                    "job_name": job.job_name,
                    "entity_type": job.entity_type,
                    "entity_id": job.entity_id,
                    "action_type": job.action_type,
                    "status": job.status,
                    "overall_result": job.overall_result,
                    "created_at": job.created_at.isoformat() if job.created_at else None,
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None,
                    "processing_time_seconds": job.processing_time_seconds,
                    "progress_percentage": job.progress_percentage,
                    "tests_planned": job.total_tests_planned,
                    "tests_completed": job.tests_completed,
                    "tests_passed": job.tests_passed,
                    "tests_failed": job.tests_failed,
                    "tests_error": job.tests_error,
                    "performers_found_total": job.performers_found_total,
                    "confidence_scores_summary": job.confidence_scores_summary,
                    "error_message": job.error_message,
                    "tests": []
                }
                
                # Add detailed test results
                for test in tests:
                    test_data = {
                        "test_id": test.test_id,
                        "entity_filepath": test.entity_filepath,
                        "ai_model": test.ai_model,
                        "status": test.status,
                        "result": test.result,
                        "performers_found": test.performers_found,
                        "max_confidence": test.max_confidence,
                        "avg_confidence": test.avg_confidence,
                        "evaluation_score": test.evaluation_score,
                        "evaluation_reason": test.evaluation_reason,
                        "evaluation_criteria": test.evaluation_criteria,
                        "processing_time_seconds": test.processing_time_seconds,
                        "error_message": test.error_message,
                        "error_type": test.error_type
                    }
                    job_data["tests"].append(test_data)
                
                result.append(job_data)
            
            return result
    
    
    def get_evaluation_trends(self, days: int = 30) -> Dict[str, Any]:
        """Get evaluation trends over time"""
        
        
        with DatabaseSession() as db:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Daily evaluation results
            daily_results = db.query(
                func.date(ProcessingTest.completed_at).label('date'),
                ProcessingTest.result,
                func.count(ProcessingTest.id).label('count'),
                func.avg(ProcessingTest.evaluation_score).label('avg_score')
            ).filter(
                ProcessingTest.completed_at >= cutoff_date,
                ProcessingTest.result.isnot(None)
            ).group_by(
                func.date(ProcessingTest.completed_at),
                ProcessingTest.result
            ).order_by('date').all()
            
            # Organize by date
            trends = {}
            for result in daily_results:
                date_str = str(result.date)
                if date_str not in trends:
                    trends[date_str] = {
                        "date": date_str,
                        "pass_count": 0,
                        "fail_count": 0,
                        "error_count": 0,
                        "total_tests": 0,
                        "avg_evaluation_score": 0
                    }
                
                trends[date_str][f"{result.result}_count"] = result.count
                trends[date_str]["total_tests"] += result.count
                if result.avg_score:
                    trends[date_str]["avg_evaluation_score"] = float(result.avg_score)
            
            # Calculate daily success rates
            for trend in trends.values():
                total = trend["total_tests"]
                if total > 0:
                    trend["success_rate"] = (trend["pass_count"] / total) * 100
                else:
                    trend["success_rate"] = 0
            
            return {
                "period_days": days,
                "daily_trends": list(trends.values()),
                "summary": {
                    "total_tests": sum(t["total_tests"] for t in trends.values()),
                    "total_passed": sum(t["pass_count"] for t in trends.values()),
                    "total_failed": sum(t["fail_count"] for t in trends.values()),
                    "total_errors": sum(t["error_count"] for t in trends.values()),
                    "overall_success_rate": (sum(t["pass_count"] for t in trends.values()) / 
                                           max(sum(t["total_tests"] for t in trends.values()), 1)) * 100
                }
            }

# =============================================================================
# Global Service Instance
# =============================================================================

# Create global instance
interactions_service = InteractionsService()