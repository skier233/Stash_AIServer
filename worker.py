#!/usr/bin/env python3
"""
Huey Worker Entry Point
Ensures all tasks are imported before starting the worker
"""

import os
import sys
from pathlib import Path

# Add the application root to Python path
app_root = Path(__file__).parent
sys.path.insert(0, str(app_root))

# Set up environment
os.environ.setdefault("PYTHONPATH", str(app_root))

if __name__ == "__main__":
    print("🚀 Starting Huey Worker...")
    
    # Import huey app (this will import all tasks)
    from Services.queue.huey_app import huey
    
    # Import tasks explicitly to ensure registration
    from Services.queue import tasks
    print("✅ All tasks imported and registered")
    
    # Start the consumer using subprocess to avoid import issues
    import subprocess
    
    # Set up consumer arguments  
    consumer_cmd = [
        sys.executable, "-m", "huey.bin.huey_consumer",
        "Services.queue.huey_app.huey",
        "--workers=2",  # Reduced from 4 to 2 to minimize SQLite lock contention
        "--verbose"
    ]
    
    # Add any additional arguments from command line
    if len(sys.argv) > 1:
        consumer_cmd.extend(sys.argv[1:])
    
    print(f"🔄 Starting Huey consumer with command: {' '.join(consumer_cmd)}")
    
    # Run the consumer
    try:
        subprocess.run(consumer_cmd, check=True)
    except KeyboardInterrupt:
        print("👋 Worker shutdown gracefully")
    except Exception as e:
        print(f"❌ Worker failed: {e}")
        sys.exit(1)