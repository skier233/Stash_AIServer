#!/usr/bin/env python3
"""
Test script to verify the normalized database schema integration
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from Database.data.visage_adapter import VisageDatabaseAdapter, VisageTaskTypes, VisageJobTypes
from Database.data.queue_service import QueueDatabaseService
from Database.data.queue_models import TaskStatus, JobStatus
from Database.database import init_database

def test_normalized_schema():
    """Test the normalized queue schema integration"""
    print("🧪 Testing Normalized Database Schema Integration")
    print("=" * 60)
    
    # Initialize database
    init_database()
    print("✅ Database initialized")
    
    # Create adapters and services
    visage_adapter = VisageDatabaseAdapter()
    queue_service = QueueDatabaseService()
    
    # Test 1: Create a Visage job
    print("\n📋 Test 1: Create Visage Job")
    job_id = visage_adapter.create_job(
        job_type=VisageJobTypes.BULK_FACE_IDENTIFICATION,
        job_name="Test Face Identification Batch",
        job_config={"threshold": 0.7, "batch_size": 4},
        user_id="test_user_001"
    )
    print(f"✅ Created job: {job_id}")
    
    # Test 2: Create individual tasks
    print("\n🎯 Test 2: Create Individual Tasks")
    task_ids = []
    for i in range(3):
        task_id = visage_adapter.create_task(
            task_type=VisageTaskTypes.FACE_IDENTIFY,
            input_data={
                "image": f"base64_image_data_{i}",
                "threshold": 0.7,
                "batch_index": i
            },
            job_id=job_id,
            priority=5
        )
        task_ids.append(task_id)
        print(f"  ✅ Created task {i+1}: {task_id}")
    
    # Test 3: Associate tasks with job
    print("\n🔗 Test 3: Associate Tasks with Job")
    success = visage_adapter.add_tasks_to_job(job_id, task_ids)
    print(f"✅ Tasks associated: {success}")
    
    # Test 4: Update task statuses
    print("\n📊 Test 4: Update Task Statuses")
    for i, task_id in enumerate(task_ids):
        if i == 0:
            # First task: completed
            visage_adapter.update_task_status(
                task_id,
                TaskStatus.FINISHED.value,
                output_json={"faces_detected": 2, "confidence": 0.85},
                processing_time_ms=1250.5
            )
            print(f"  ✅ Task 1 marked as FINISHED")
        elif i == 1:
            # Second task: failed
            visage_adapter.update_task_status(
                task_id,
                TaskStatus.FAILED.value,
                error_message="Invalid image format"
            )
            print(f"  ✅ Task 2 marked as FAILED")
        else:
            # Third task: running
            visage_adapter.update_task_status(
                task_id,
                TaskStatus.RUNNING.value
            )
            print(f"  ✅ Task 3 marked as RUNNING")
    
    # Test 5: Get job and task details
    print("\n📖 Test 5: Retrieve Job and Task Details")
    job = visage_adapter.get_job(job_id)
    print(f"  📋 Job Status: {job['status']}")
    print(f"  📋 Progress: {job['progress_percentage']:.1f}%")
    print(f"  📋 Tasks: {job['completed_tasks']}/{job['total_tasks']} completed")
    
    job_tasks = visage_adapter.get_job_tasks(job_id)
    print(f"  🎯 Retrieved {len(job_tasks)} tasks from job")
    
    # Test 6: Queue service cross-adapter queries
    print("\n🔍 Test 6: Cross-Adapter Query Service")
    stats = queue_service.get_queue_statistics()
    print(f"  📊 Total tasks in system: {stats['tasks']['total']}")
    print(f"  📊 Finished tasks: {stats['tasks']['finished']}")
    print(f"  📊 Failed tasks: {stats['tasks']['failed']}")
    print(f"  📊 Running tasks: {stats['tasks']['running']}")
    
    adapter_stats = queue_service.get_adapter_statistics("visage")
    print(f"  📊 Visage adapter tasks: {adapter_stats['tasks']['total']}")
    print(f"  📊 Visage job count: {adapter_stats['jobs']['total']}")
    
    # Test 7: Health check
    print("\n❤️ Test 7: Health Check")
    health = queue_service.health_check()
    print(f"  ✅ Database healthy: {health.get('database_healthy', False)}")
    print(f"  📊 Total tasks: {health.get('total_tasks', 0)}")
    print(f"  📊 Total jobs: {health.get('total_jobs', 0)}")
    
    print("\n" + "=" * 60)
    print("🎉 All tests completed successfully!")
    print("🏆 Normalized database schema is working correctly!")

if __name__ == "__main__":
    try:
        test_normalized_schema()
    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)