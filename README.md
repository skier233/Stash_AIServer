# StashAI Server

Advanced API gateway with queue-based batch processing for AI services, featuring real-time WebSocket monitoring, user interaction tracking, and modular service integration.

## 🎯 Key Features

- **Queue-First Architecture**: Huey + SQLite for lightweight background processing
- **Real-Time WebSocket Queue Tracking**: Monitor task and job progress in real-time
- **Batch Processing**: Add parallel processing to any API service
- **Service Integration Templates**: Easy integration of new AI services (Visage included)
- **User Interaction Tracking**: Real-time WebSocket monitoring
- **Intelligent Fallbacks**: Direct processing when queue unavailable
- **Environment-Based Switching**: Development vs production modes
- **Normalized Database Schema**: Universal task/job tracking across all services

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Client Apps   │───▶│  StashAI Server │───▶│  Huey Workers   │
│                 │    │    (Gateway)    │    │                 │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │                        │
                              ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │ SQLite Queue    │    │ AI Services     │
                       │    Database     │    │ (Visage, etc.)  │
                       └─────────────────┘    └─────────────────┘
```

### Core Services

- **FastAPI Gateway** (Port 9998) - Main API endpoints
- **SQLite Queue Database** - Lightweight queue storage
- **Huey Workers** - Background task processing
- **AI Services** - Pluggable AI service integrations (e.g., Visage)

## 🚀 Quick Start

### Prerequisites
- Docker and Docker Compose
- Python 3.11+ (for development)

### Docker Deployment (Recommended)
```bash
# Start all services
docker-compose up -d

# View logs
docker-compose logs -f stash-ai-server

# Monitor logs (Huey uses simple logging)
docker-compose logs -f huey-worker

# Check health
curl http://localhost:9998/health
```

### Development Mode
```bash
# Install dependencies
pip install -r requirements.txt

# Set environment for direct processing (no queue)
export QUEUE_ENABLED=false
export DIRECT_MODE=true

# Run server
python main.py
```

## 📡 API Endpoints

### Core Application Endpoints
- **`GET /`** - Service status and basic health
- **`GET /health`** - Comprehensive health check (includes database and queue status)

### User Interaction Endpoints
- **`POST /api/interactions`** - Submit user interaction (queue-processed with fallback)
  ```json
  {
    "session_id": "string",
    "user_id": "string",
    "action_type": "string",
    "page_path": "string", 
    "element_type": "string",
    "element_id": "string",
    "metadata": {}
  }
  ```
- **`GET /api/interactions`** - Retrieve user interactions with filtering
  - Query params: `session_id`, `limit`, `offset`

### Session Management Endpoints  
- **`POST /api/sessions`** - Create/update user session (queue-processed with fallback)
  ```json
  {
    "session_id": "string",
    "user_id": "string", 
    "page_views": 0,
    "total_interactions": 0,
    "metadata": {},
    "end_time": "2024-01-01T00:00:00Z"
  }
  ```
- **`GET /api/sessions/{session_id}`** - Get session details

### Queue Management Endpoints
- **`GET /api/queue/status/{task_id}`** - Get task execution status and results
- **`POST /api/queue/cancel/{task_id}`** - Cancel a queued task
- **`GET /api/queue/stats`** - Get queue statistics (active/scheduled/reserved tasks)
- **`GET /api/queue/health`** - Dedicated queue health check
- **`POST /api/batch`** - Submit batch processing job
  ```json
  {
    "type": "interactions|sessions",
    "items": [...],
    "config": {}
  }
  ```

### WebSocket Endpoints
- **`WS /ws/{session_id}`** - Real-time interaction updates and queue monitoring
  - **Basic Communication**:
    - Send: `{"type": "ping"}` → Receive: `{"type": "pong", "timestamp": "..."}`
    - Receive: `{"type": "new_interaction", "data": {...}}`
  
  - **Queue Subscriptions** (Subscribe to real-time task/job updates):
    - **Task Monitoring**: `{"type": "subscribe_task", "task_id": "uuid"}`
    - **Job Monitoring**: `{"type": "subscribe_job", "job_id": "uuid"}`
    - **Queue Statistics**: `{"type": "subscribe_queue_stats"}`
  
  - **Real-Time Updates Received**:
    - **Task Status**: `{"type": "task_status", "task_id": "uuid", "status": "running", "progress": {...}}`
    - **Job Progress**: `{"type": "job_progress", "job_id": "uuid", "completed_tasks": 3, "total_tasks": 10, "progress_percentage": 30.0}`
    - **Queue Stats**: `{"type": "queue_stats", "data": {"total_tasks": 50, "pending": 10, "running": 5}}`

### Visage Integration Endpoints
- **`POST /api/visage/job`** - Create batch Visage face identification job with custom API endpoint
  ```json
  {
    "images": ["base64_image_1", "base64_image_2", ...],
    "visage_api_url": "http://your-visage-api.com/api/identify",
    "config": {
      "threshold": 0.7,
      "job_name": "Custom Job Name",
      "user_id": "user_123",
      "session_id": "session_456",
      "additional_params": {"max_faces": 10, "return_embeddings": true}
    }
  }
  ```
- **`POST /api/visage/task`** - Create single Visage face identification task
  ```json
  {
    "image": "base64_encoded_image_data",
    "visage_api_url": "http://your-visage-api.com/api/identify",
    "config": {
      "threshold": 0.8,
      "additional_params": {"max_faces": 5}
    }
  }
  ```

### Demo and Testing Endpoints
- **`POST /api/demo/visage/job`** - Create demo batch job for WebSocket testing
- **`POST /api/demo/visage/task`** - Create demo single task for WebSocket testing
- **`GET /api/demo/websocket/instructions`** - Complete WebSocket usage documentation

### Future Service Endpoints (Template-Ready)
The system is designed to easily add service-specific batch endpoints:
- **`POST /api/transcription/batch`** - Batch audio transcription (template available)
- **`POST /api/translation/batch`** - Batch text translation (template available)
- **`POST /api/your-service/batch/operation`** - Any service batch operation (template available)

## 🔧 Queue Manager: Adding Batch Processing to Any API

The StashAI Server includes a **Database Queue Adapter** system located in `Database/adapters/` that allows you to add batch processing and parallel execution capabilities to any API service, even if the service doesn't natively support it.

### How It Works

**Problem**: Many AI services (like Visage) only handle individual requests:
```bash
# Visage can only process one image at a time
POST /identify -> {"image": "base64_data"}
```

**Solution**: The Queue Manager orchestrates multiple individual calls:
```bash
# Submit batch job
POST /api/visage/batch/identify -> {"images": ["img1", "img2", ...]}

# Queue Manager automatically:
# 1. Creates a Job record
# 2. Splits into individual Tasks
# 3. Processes Tasks in parallel via Celery
# 4. Aggregates results
# 5. Returns consolidated response
```

### Template Architecture

**Job = Batch Operation (1:N Tasks)**
- Example: "Identify faces in 100 images"
- Tracks progress, manages results, handles failures

**Task = Individual API Call (1:1 Service Call)**  
- Example: "Identify face in image_001.jpg"
- Atomic operation, can be retried independently

```
Job: "Batch Face Identification" (100 images)
├── Task 1: Identify face in image_001.jpg  
├── Task 2: Identify face in image_002.jpg
├── ...
└── Task 100: Identify face in image_100.jpg
```

### Creating New Service Adapters

#### Step 1: Copy the Template
```bash
cp Database/adapters/VisageDatabaseQueueAdapter.py Database/adapters/YourServiceDatabaseQueueAdapter.py
```

#### Step 2: Customize Enums
```python
class YourServiceJobType(Enum):
    BATCH_TRANSCRIPTION = "your_service_batch_transcription"
    BATCH_TRANSLATION = "your_service_batch_translation"
    BULK_ANALYSIS = "your_service_bulk_analysis"

class YourServiceTaskType(Enum):  
    SINGLE_TRANSCRIBE = "your_service_single_transcribe"
    SINGLE_TRANSLATE = "your_service_single_translate"
    SINGLE_ANALYZE = "your_service_single_analyze"
```

#### Step 3: Customize Database Models
```python
class YourServiceJob(Base):
    __tablename__ = "your_service_jobs"
    
    # Universal fields (keep these)
    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(String, unique=True, index=True)
    status = Column(String, index=True)
    # ... other universal fields
    
    # Your service-specific fields
    language = Column(String, default="en")
    quality_level = Column(String, default="high") 
    custom_model = Column(String, nullable=True)
```

#### Step 4: Create Celery Tasks
```python
# Services/queue/tasks/your_service_tasks.py
@celery_app.task(bind=True)
def your_service_single_transcribe_task(self, task_data):
    """Process single transcription task"""
    # Call your service API
    # Update task status in database
    # Return result
```

#### Step 5: Add API Endpoints
```python
# api/endpoints.py
@router.post("/api/your-service/batch/transcribe")
async def batch_transcribe(request: Request):
    # Create Job and Tasks
    # Submit to queue
    # Return job_id for tracking
```

### Example: Visage Integration

The included Visage adapter demonstrates the complete pattern:

**1. Job Types**:
```python
class VisageJobType(Enum):
    BATCH_FACE_IDENTIFICATION = "visage_batch_face_identification"
    BATCH_FACE_COMPARISON = "visage_batch_face_comparison"
    BATCH_ONE_TO_MANY_COMPARE = "visage_batch_one_to_many_compare"
```

**2. Visage-Specific Fields**:
```python
class VisageJob(Base):
    # Universal fields...
    
    # Visage-specific
    face_threshold = Column(Float, default=0.5)
    model_type = Column(String, default="arc") 
    return_face_locations = Column(String, default="true")
```

**3. Usage Example**:
```bash
# Submit batch face identification job
POST /api/visage/batch/identify
{
  "images": ["base64_img1", "base64_img2", ...],
  "config": {
    "face_threshold": 0.7,
    "model_type": "arc", 
    "batch_size": 4
  }
}

# Response
{
  "job_id": "uuid-123",
  "status": "queued",
  "total_tasks": 100,
  "estimated_completion": "2min"
}

# Check progress
GET /api/queue/status/uuid-123
{
  "job_id": "uuid-123",
  "status": "running",
  "progress": 45.0,
  "completed_tasks": 45,
  "failed_tasks": 2,
  "results": [...]
}
```

### Benefits of This Approach

✅ **Parallel Processing**: 4+ concurrent API calls instead of sequential
✅ **Fault Tolerance**: Individual task failures don't break entire job
✅ **Progress Tracking**: Real-time progress updates via WebSocket
✅ **Result Aggregation**: Consolidated results from multiple API calls
✅ **Retry Logic**: Smart retry with exponential backoff
✅ **Resource Management**: Queue handles rate limiting and throttling

## 🔧 Configuration

### Environment Variables

```bash
# Queue Configuration  
QUEUE_ENABLED=true          # Enable/disable queue system
DIRECT_MODE=false           # Bypass queue for development

# Huey SQLite Configuration
QUEUE_DB_PATH=/app/data/queue.db    # SQLite database for queue

# Application
PYTHONPATH=/app
LOG_LEVEL=info
```

### Development vs Production

**Development Mode** (Direct Processing):
```bash
export QUEUE_ENABLED=false
export DIRECT_MODE=true
# All requests processed immediately, no queue overhead
```

**Production Mode** (Queue Processing):
```bash
export QUEUE_ENABLED=true  
export DIRECT_MODE=false
# All requests queued for background processing
```

### Monitoring

**Simple Logging**: Huey provides straightforward logging
- Monitor workers: `docker-compose logs -f huey-worker`
- View queue activity in container logs

**Health Checks**: Multi-level health monitoring
```bash
curl http://localhost:9998/health
{
  "status": "healthy",
  "database": "connected", 
  "queue": {
    "queue_healthy": true,
    "queue_enabled": true
  }
}
```

## 📡 WebSocket Real-Time Queue Tracking

The StashAI Server provides comprehensive real-time monitoring of queue operations through WebSocket connections. Frontend applications can subscribe to task-level, job-level, and system-level events.

### 🔌 Connection and Basic Usage

**Connect to WebSocket**:
```javascript
const ws = new WebSocket('ws://localhost:9998/ws/demo_session');

// Basic ping-pong for connection health
ws.send(JSON.stringify({"type": "ping"}));
// Receives: {"type": "pong", "timestamp": "2024-01-01T00:00:00Z"}
```

### 📋 Subscription Types

#### 1. Task-Level Monitoring
Monitor individual task progress from creation to completion:

```javascript
// Subscribe to specific task updates
ws.send(JSON.stringify({
    "type": "subscribe_task",
    "task_id": "task-uuid-here"
}));

// Receive real-time updates:
// {"type": "task_status", "task_id": "task-uuid", "status": "running", 
//  "adapter_name": "visage", "task_type": "face_identify", 
//  "processing_time_ms": 1500.0, "timestamp": "..."}
```

#### 2. Job-Level Monitoring  
Monitor batch job progress across all constituent tasks:

```javascript
// Subscribe to job progress updates
ws.send(JSON.stringify({
    "type": "subscribe_job", 
    "job_id": "job-uuid-here"
}));

// Receive progress updates:
// {"type": "job_progress", "job_id": "job-uuid", "status": "running",
//  "total_tasks": 10, "completed_tasks": 6, "failed_tasks": 1,
//  "progress_percentage": 60.0, "timestamp": "..."}
```

#### 3. Queue Statistics Monitoring
Monitor overall system queue health and activity:

```javascript
// Subscribe to queue statistics
ws.send(JSON.stringify({"type": "subscribe_queue_stats"}));

// Receive system updates:
// {"type": "queue_stats", "data": {
//   "total_tasks": 150, "pending_tasks": 25, "running_tasks": 8,
//   "completed_tasks": 115, "failed_tasks": 2
// }, "timestamp": "..."}
```

### 🎯 Complete Frontend Integration Example

```javascript
class QueueMonitor {
    constructor(baseUrl = 'ws://localhost:9998') {
        this.ws = new WebSocket(`${baseUrl}/ws/demo_session`);
        this.setupEventHandlers();
    }
    
    setupEventHandlers() {
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            switch(data.type) {
                case 'task_status':
                    this.handleTaskUpdate(data);
                    break;
                case 'job_progress':
                    this.handleJobProgress(data);
                    break;
                case 'queue_stats':
                    this.handleQueueStats(data);
                    break;
            }
        };
    }
    
    // Create Visage job and monitor progress
    async createAndMonitorVisageJob(images, visageApiUrl) {
        // 1. Create the job
        const response = await fetch('/api/visage/job', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                images: images,
                visage_api_url: visageApiUrl,
                config: { threshold: 0.7 }
            })
        });
        
        const jobData = await response.json();
        
        // 2. Subscribe to real-time updates
        this.subscribeToJob(jobData.job_id);
        
        return jobData;
    }
    
    subscribeToJob(jobId) {
        this.ws.send(JSON.stringify({
            type: "subscribe_job",
            job_id: jobId
        }));
    }
    
    subscribeToTask(taskId) {
        this.ws.send(JSON.stringify({
            type: "subscribe_task", 
            task_id: taskId
        }));
    }
    
    handleJobProgress(data) {
        console.log(`Job ${data.job_id}: ${data.progress_percentage}% complete`);
        console.log(`${data.completed_tasks}/${data.total_tasks} tasks finished`);
        
        // Update UI progress bar
        document.getElementById('progress').value = data.progress_percentage;
    }
    
    handleTaskUpdate(data) {
        console.log(`Task ${data.task_id} is now ${data.status}`);
        if (data.status === 'completed' && data.output_json) {
            console.log('Task results:', data.output_json);
        }
    }
}

// Usage
const monitor = new QueueMonitor();
```

### 🧪 Testing WebSocket Integration

1. **Start the demo workflow**:
   ```bash
   # Create demo job
   curl -X POST http://localhost:9998/api/demo/visage/job
   
   # Get WebSocket instructions  
   curl http://localhost:9998/api/demo/websocket/instructions
   ```

2. **Connect and subscribe via WebSocket client**:
   ```javascript
   ws.send(JSON.stringify({"type": "subscribe_job", "job_id": "job-uuid-from-step-1"}));
   ```

3. **Watch real-time progress** as tasks move through: `pending` → `running` → `completed`

### 🚀 Advanced Usage Patterns

**Multi-Level Monitoring**: Subscribe to both job and individual tasks for comprehensive tracking:
```javascript
// Monitor overall job progress
monitor.subscribeToJob(jobId);

// Also monitor critical individual tasks
criticalTaskIds.forEach(taskId => monitor.subscribeToTask(taskId));
```

**Error Handling and Retry Logic**: 
```javascript
handleTaskUpdate(data) {
    if (data.status === 'failed' && data.error_message) {
        console.error(`Task failed: ${data.error_message}`);
        // Implement retry logic or user notification
        this.retryFailedTask(data.task_id);
    }
}
```

## 📊 Database Schema

### Core Tables
- `user_interactions` - User behavior tracking
- `user_sessions` - Session management

### Normalized Queue System Tables
- `queue_tasks` - Universal task tracking across all service adapters
- `queue_jobs` - Universal batch job orchestration and progress tracking

### Service-Specific Adapters
Located in `Database/data/` - normalized schema integration:
- `visage_adapter.py` - Facial recognition service adapter
- `queue_models.py` - Universal task/job schema definitions

### Migration Support
- Alembic integration for database migrations
- Located in `Database/alembic/`

## 🛠️ Development

### Project Structure
```
StashAIServer/
├── Database/                    # Database models and migrations
│   ├── models.py               # Core user interaction models
│   ├── database.py             # Database configuration
│   ├── data/                   # Normalized queue schema and service adapters
│   │   ├── queue_models.py     # Universal task/job schema definitions
│   │   └── visage_adapter.py   # Visage service adapter with WebSocket integration
│   └── alembic/                # Database migrations
├── Services/                   # All service implementations
│   ├── queue/                  # Queue management system
│   │   ├── huey_app.py         # Huey SQLite configuration
│   │   ├── tasks.py            # General-purpose queue tasks
│   │   └── manager.py          # Queue manager with intelligent fallback
│   ├── websocket/              # Real-time WebSocket system
│   │   ├── manager.py          # WebSocket connection and subscription management
│   │   └── broadcaster.py     # Queue-to-WebSocket event broadcasting
│   └── visage/                 # Visage facial recognition service
├── api/                        # API endpoints and service integrations
│   ├── endpoints.py            # REST API definitions with WebSocket integration
│   └── VisageFrontendAdapter.py # Visage-specific API integration and queue tasks
├── main.py                     # FastAPI application entry point with WebSocket support
├── worker.py                   # Huey worker entry point for task processing
├── requirements.txt            # Python dependencies (Huey, FastAPI, WebSocket support)
└── docker-compose.yml          # Multi-container deployment (SQLite + Huey)
```

### Adding New Services

1. **Create Service Adapter**: Copy and customize from `Database/data/visage_adapter.py`
2. **Create Frontend Adapter**: Copy and customize from `api/VisageFrontendAdapter.py` 
3. **Add API Endpoints**: Extend `api/endpoints.py` with service-specific endpoints
4. **WebSocket Integration**: Automatic via normalized schema and broadcaster system
5. **Update Docker**: Add service to `docker-compose.yml` if needed

**Example**: Adding a transcription service:
```python
# Database/data/transcription_adapter.py
class TranscriptionDatabaseAdapter:
    ADAPTER_NAME = "transcription"
    # Uses same normalized schema as Visage
    
# api/TranscriptionFrontendAdapter.py  
@huey.task(retries=DEFAULT_RETRY_CONFIG["retries"])
def transcription_task(task_data):
    # Call external transcription API
    # Automatically gets WebSocket broadcasting
```

### Testing

```bash
# Install test dependencies
pip install -r requirements.txt

# Run tests
pytest

# Test with queue disabled (direct mode)
QUEUE_ENABLED=false pytest

# Test specific service
pytest tests/test_visage_integration.py
```

## 📈 Scaling

### Horizontal Scaling
```yaml
# docker-compose.yml
huey-worker:
  deploy:
    replicas: 4  # Multiple workers
  command: python -m huey.bin.huey_consumer Services.queue.huey_app.huey --workers=4

huey-worker-gpu:
  # GPU-enabled workers for AI tasks
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
```

### Queue Optimization
```python
# Services/queue/huey_app.py
huey = SqliteHuey(
    name="stash_ai_queue",
    filename="/app/data/queue.db",
    consumer={"workers": 4, "worker_type": "thread"}
)
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Follow the Database Queue Adapter template for new services
4. Add comprehensive tests
5. Update documentation
6. Submit pull request

## 📝 License

[Your License Here]

---

**StashAI Server** - Transforming single-use APIs into powerful batch processing systems through intelligent queue orchestration.