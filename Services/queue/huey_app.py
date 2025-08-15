# =============================================================================
# Huey Application Configuration
# =============================================================================

import os
from pathlib import Path
from huey import SqliteHuey

# =============================================================================
# Environment Configuration
# =============================================================================

# Create data directory for queue database  
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

QUEUE_DB_PATH = os.getenv("QUEUE_DB_PATH", str(DATA_DIR / "queue.db"))
QUEUE_ENABLED = os.getenv("QUEUE_ENABLED", "true").lower() == "true"

# =============================================================================
# Huey Application
# =============================================================================

# Note: If SQLite locking issues persist, consider switching to Redis:
# from huey import RedisHuey
# huey = RedisHuey('stash_ai_queue', host='localhost', port=6379, db=0)

huey = SqliteHuey(
    name="stash_ai_queue",
    filename=QUEUE_DB_PATH,
    
    # Worker configuration
    immediate=not QUEUE_ENABLED,  # If queue disabled, run tasks immediately
    
    # Task settings  
    results=True,  # Store task results
    store_none=False,  # Don't store None results
    
    # SQLite timeout for database locks (this is the correct parameter)
    timeout=30.0,  # 30 second timeout for database locks
    check_same_thread=False  # Allow multiple threads
)

# =============================================================================
# SQLite Optimization - Run after Huey initialization
# =============================================================================

def optimize_sqlite_connection():
    """Apply SQLite optimizations for better concurrency"""
    try:
        # Get the storage instance and apply optimizations
        storage = huey.storage
        if hasattr(storage, '_create_connection'):
            # Create a connection to apply PRAGMA settings
            conn = storage._create_connection()
            cursor = conn.cursor()
            
            # Apply SQLite optimizations
            cursor.execute('PRAGMA journal_mode=WAL;')  # Write-Ahead Logging
            cursor.execute('PRAGMA synchronous=NORMAL;')  # Balance speed/safety
            cursor.execute('PRAGMA temp_store=memory;')  # Use memory for temp storage
            cursor.execute('PRAGMA mmap_size=268435456;')  # 256MB memory-mapped I/O
            cursor.execute('PRAGMA cache_size=-64000;')  # 64MB page cache
            cursor.execute('PRAGMA busy_timeout=30000;')  # 30 second busy timeout
            
            conn.commit()
            conn.close()
            print("✅ SQLite optimizations applied successfully")
            
    except Exception as e:
        print(f"⚠️ Warning: Could not apply SQLite optimizations: {e}")

# Apply optimizations when module is imported
optimize_sqlite_connection()

# =============================================================================
# Task Configuration
# =============================================================================

# Configure task priorities and routing
TASK_PRIORITIES = {
    "high": 10,
    "normal": 5, 
    "low": 1
}

# Task retry configuration
DEFAULT_RETRY_CONFIG = {
    "retries": 3,
    "retry_delay": 60,  # seconds
    "exponential_backoff": 2
}

# =============================================================================
# Task Registry - Import all tasks to register them with Huey
# =============================================================================

# Import all task modules so they are registered with Huey
# This is required for the worker to find and execute tasks
try:
    from Services.queue import tasks
    print("✅ Tasks imported successfully")
except ImportError as e:
    print(f"⚠️ Warning: Could not import tasks: {e}")

# =============================================================================
# Health Check
# =============================================================================

@huey.task()
def health_check_task():
    """Simple health check task for queue monitoring"""
    from datetime import datetime, timezone
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "queue_type": "huey_sqlite"
    }