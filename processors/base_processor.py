# =============================================================================
# Base API Processor - Modular Framework for API Tracking
# =============================================================================

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
import logging
import uuid
import asyncio

from database.models import (
    EntityType, AIActionType, JobStatus, TestResult, AIModel,
    ProcessingJob, ProcessingTest
)
from database.interactions_service import InteractionsService

logger = logging.getLogger(__name__)

class BaseAPIProcessor(ABC):
    """
    Base class for all API processors that provides consistent database tracking,
    job lifecycle management, and statistics updates.
    
    This modular framework ensures all APIs have the same level of database
    integration and monitoring capabilities.
    """
    
    def __init__(self):
        self.interactions_service = InteractionsService()
    
    # =========================================================================
    # Abstract Methods - Must be implemented by subclasses
    # =========================================================================
    
    @abstractmethod
    async def process_request(self, request: Any, **kwargs) -> Any:
        """
        Process the actual API request. This is the core business logic
        that each processor must implement.
        
        Args:
            request: The API request object
            **kwargs: Additional parameters like cancellation_check, progress_callback
            
        Returns:
            The API response object
        """
        pass
    
    @abstractmethod
    def get_entity_info(self, request: Any) -> Tuple[EntityType, str, str, str]:
        """
        Extract entity information from the request.
        
        Args:
            request: The API request object
            
        Returns:
            Tuple of (entity_type, entity_id, entity_name, entity_filepath)
        """
        pass
    
    @abstractmethod
    def get_action_type(self) -> AIActionType:
        """
        Get the AI action type for this processor.
        
        Returns:
            The AIActionType enum value
        """
        pass
    
    @abstractmethod
    def extract_results(self, response: Any) -> Dict[str, Any]:
        """
        Extract standardized results from the API response for database storage.
        
        Args:
            response: The API response object
            
        Returns:
            Dictionary containing standardized result data
        """
        pass
    
    # =========================================================================
    # Public Interface - Used by queue and direct API calls
    # =========================================================================
    
    async def process_with_tracking(
        self,
        request: Any,
        job_id: Optional[str] = None,
        progress_callback: Optional[callable] = None,
        cancellation_check: Optional[callable] = None
    ) -> Tuple[Any, str]:
        """
        Process an API request with full database tracking and job management.
        
        Args:
            request: The API request object
            job_id: Optional existing job ID, will create new if not provided
            progress_callback: Optional callback for progress updates
            cancellation_check: Optional callback to check for cancellation
            
        Returns:
            Tuple of (response, job_id)
        """
        # Extract entity information
        entity_type, entity_id, entity_name, entity_filepath = self.get_entity_info(request)
        
        # Create or get job and test records
        if not job_id:
            # Create properly formatted job ID for UI to recognize as server job
            processor_name = self.__class__.__name__.lower().replace('processor', '')
            timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
            short_uuid = str(uuid.uuid4())[:8]
            job_id = f"{processor_name}_{timestamp}_{short_uuid}"
        
        test_id = f"{job_id}_test"
        
        # Get or create job and test in database
        db_job = await self._get_or_create_job_record(
            job_id=job_id,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_filepath=entity_filepath,
            request_data=self._serialize_request(request)
        )
        
        db_test = await self._get_or_create_test_record(
            test_id=test_id,
            job_id=job_id,
            db_job=db_job,
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_filepath=entity_filepath,
            request_data=self._serialize_request(request)
        )
        
        try:
            # Start processing
            await self._start_processing(db_job, db_test)
            
            # Check for cancellation
            if cancellation_check and await cancellation_check():
                await self._handle_cancellation(db_job, db_test)
                raise asyncio.CancelledError("Processing was cancelled")
            
            # Process the actual request
            response = await self.process_request(
                request,
                progress_callback=progress_callback,
                cancellation_check=cancellation_check
            )
            
            # Complete processing with results
            await self._complete_processing(db_job, db_test, response)
            
            return response, job_id
            
        except Exception as e:
            # Handle failure
            await self._handle_failure(db_job, db_test, str(e))
            raise
    
    # =========================================================================
    # Database Operations
    # =========================================================================
    
    async def _get_or_create_job_record(
        self,
        job_id: str,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str,
        entity_filepath: str,
        request_data: Dict[str, Any]
    ) -> Any:
        """Get existing job record or create a new one if it doesn't exist"""
        # First try to get existing job
        existing_job = self.interactions_service.get_ai_job(job_id)
        if existing_job:
            logger.info(f"Using existing job record: {job_id}")
            return existing_job
        
        # If job doesn't exist, create it
        logger.info(f"Creating new job record: {job_id}")
        from database.models import AIJobCreate
        
        job_data = AIJobCreate(
            job_name=f"{self.get_action_type().value}_{entity_type.value}_{entity_id}",
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            action_type=self.get_action_type(),
            ai_model=AIModel.VISAGE,
            job_config=request_data
        )
        
        response = self.interactions_service.create_ai_job(job_data, job_id)
        return response
    
    async def _get_or_create_test_record(
        self,
        test_id: str,
        job_id: str,
        db_job: Any,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str,
        entity_filepath: str,
        request_data: Dict[str, Any]
    ) -> Any:
        """Get existing test record or create a new one if it doesn't exist"""
        # First try to get existing test
        existing_test = self.interactions_service.get_ai_test(test_id)
        if existing_test:
            logger.info(f"Using existing test record: {test_id}")
            return existing_test
        
        # If test doesn't exist, create it
        logger.info(f"Creating new test record: {test_id}")
        from database.models import AITestCreate
        
        test_data = AITestCreate(
            entity_type=entity_type,
            entity_id=entity_id,
            entity_name=entity_name,
            entity_filepath=entity_filepath,
            action_type=self.get_action_type(),
            ai_model=AIModel.VISAGE,
            test_config=request_data
        )
        
        response = self.interactions_service.create_ai_test(job_id, test_data, test_id)
        return response
    
    async def _start_processing(self, db_job: Any, db_test: Any):
        """Mark job and test as started"""
        from database.database import DatabaseSession
        now = datetime.utcnow()
        
        # Update job and test records directly using database session
        with DatabaseSession() as db:
            # Update job
            job_record = db.query(ProcessingJob).filter(ProcessingJob.job_id == db_job.job_id).first()
            if job_record:
                job_record.status = JobStatus.PROCESSING.value
                job_record.started_at = now
            
            # Update test
            test_record = db.query(ProcessingTest).filter(ProcessingTest.test_id == db_test.test_id).first()
            if test_record:
                test_record.status = TestResult.PENDING.value
                test_record.started_at = now
            
            db.commit()
    
    async def _complete_processing(self, db_job: Any, db_test: Any, response: Any):
        """Complete processing and store results"""
        now = datetime.utcnow()
        
        # Extract standardized results
        results = self.extract_results(response)
        
        # Determine success/failure
        success = getattr(response, 'success', True)
        test_status = TestResult.PASS.value if success else TestResult.FAIL.value
        job_status = JobStatus.COMPLETED.value if success else JobStatus.FAILED.value
        
        # Complete test using the interactions service method
        processing_time = None
        if hasattr(db_test, 'started_at') and db_test.started_at:
            processing_time = (now - db_test.started_at).total_seconds()
        
        # Pass the serialized response data, not the test update data
        serialized_response = self._serialize_response(response)
        self.interactions_service.complete_ai_test(
            test_id=db_test.test_id, 
            response_data=serialized_response,
            processing_time=processing_time
        )
        
        # Complete job with comprehensive results
        job_update = {
            'status': job_status,
            'completed_at': now,
            'tests_completed': 1,
            'tests_passed': 1 if success else 0,
            'tests_failed': 0 if success else 1,
            'progress_percentage': 100.0,
            'overall_result': test_status,
            'performers_found_total': results.get('performers_found', 0),
            'results_json': results,
            'results_summary': {
                'total_tests': 1,
                'successful_tests': 1 if success else 0,
                'failed_tests': 0 if success else 1,
                'performers_found': results.get('performers_found', 0),
                'processing_time': processing_time or 0
            }
        }
        
        if db_job.started_at:
            job_update['processing_time_seconds'] = (now - db_job.started_at).total_seconds()
        
        # Update job directly using database session
        from database.database import DatabaseSession
        with DatabaseSession() as db:
            job_record = db.query(ProcessingJob).filter(ProcessingJob.job_id == db_job.job_id).first()
            if job_record:
                for key, value in job_update.items():
                    setattr(job_record, key, value)
                db.commit()
        
        logger.info(f"Completed {self.get_action_type().value} processing for {db_job.entity_type}:{db_job.entity_id}")
    
    async def _handle_failure(self, db_job: Any, db_test: Any, error_message: str):
        """Handle processing failure"""
        now = datetime.utcnow()
        
        # Fail test
        self.interactions_service.fail_ai_test(db_test.test_id, error_message)
        
        # Fail job
        job_update = {
            'status': JobStatus.FAILED.value,
            'completed_at': now,
            'tests_completed': 1,
            'tests_failed': 1,
            'progress_percentage': 100.0,
            'overall_result': TestResult.FAIL.value,
            'error_message': error_message
        }
        
        if db_job.started_at:
            job_update['processing_time_seconds'] = (now - db_job.started_at).total_seconds()
        
        # Update job directly using database session
        from database.database import DatabaseSession
        with DatabaseSession() as db:
            job_record = db.query(ProcessingJob).filter(ProcessingJob.job_id == db_job.job_id).first()
            if job_record:
                for key, value in job_update.items():
                    setattr(job_record, key, value)
                db.commit()
        
        logger.error(f"Failed {self.get_action_type().value} processing for {db_job.entity_type}:{db_job.entity_id}: {error_message}")
    
    async def _handle_cancellation(self, db_job: Any, db_test: Any):
        """Handle processing cancellation"""
        now = datetime.utcnow()
        
        # Cancel test
        self.interactions_service.update_ai_test(db_test.test_id, {
            'status': TestResult.ERROR.value,
            'completed_at': now,
            'error_message': 'Processing was cancelled'
        })
        
        # Cancel job
        job_update = {
            'status': JobStatus.CANCELLED.value,
            'completed_at': now,
            'tests_completed': 1,
            'tests_error': 1,
            'progress_percentage': 100.0,
            'error_message': 'Processing was cancelled'
        }
        
        if db_job.started_at:
            job_update['processing_time_seconds'] = (now - db_job.started_at).total_seconds()
        
        # Update job directly using database session
        from database.database import DatabaseSession
        with DatabaseSession() as db:
            job_record = db.query(ProcessingJob).filter(ProcessingJob.job_id == db_job.job_id).first()
            if job_record:
                for key, value in job_update.items():
                    setattr(job_record, key, value)
                db.commit()
        
        logger.info(f"Cancelled {self.get_action_type().value} processing for {db_job.entity_type}:{db_job.entity_id}")
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    def _serialize_request(self, request: Any) -> Dict[str, Any]:
        """Serialize request object for database storage"""
        if hasattr(request, 'dict'):
            return request.dict()
        elif hasattr(request, '__dict__'):
            return request.__dict__
        else:
            return {'raw_request': str(request)}
    
    def _serialize_response(self, response: Any) -> Dict[str, Any]:
        """Serialize response object for database storage"""
        def serialize_for_json(obj):
            """Serialize objects to be JSON compatible"""
            if isinstance(obj, dict):
                return {k: serialize_for_json(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [serialize_for_json(item) for item in obj]
            elif hasattr(obj, 'isoformat'):  # datetime objects
                return obj.isoformat()
            elif hasattr(obj, 'dict'):  # Pydantic models
                return serialize_for_json(obj.dict())
            else:
                return obj
        
        if hasattr(response, 'dict'):
            return serialize_for_json(response.dict())
        elif hasattr(response, '__dict__'):
            return serialize_for_json(response.__dict__)
        else:
            return {'raw_response': str(response)}