# StashAI Server

Unified API gateway for AI services in Stash using Gateway Pattern architecture.

## Features

- **Unified API**: Single endpoint for all AI services
- **Service Discovery**: Automatic service registration and health monitoring
- **Facial Recognition**: Integration with Visage facial recognition service
- **Modular Architecture**: Easy to add new AI services
- **Docker Ready**: Containerized deployment with Docker Compose

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Stash Plugin  │───▶│  StashAI Server │───▶│  Visage Service │
│                 │    │    (Gateway)    │    │ (Face Recognition)
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │ Service Registry│
                       │ & Health Monitor│
                       └─────────────────┘
```

## Quick Start

### Prerequisites

**Model Files Required**: The Visage facial recognition service requires two model files:
- `BackendServers/visage/models/face_arc.voy`
- `BackendServers/visage/models/face_facenet.voy`

These are included in the repository. If missing, see `BackendServers/visage/README.md` for setup instructions.

### Using Docker Compose (Recommended)

#### CPU Only (Default)
```bash
# Start all services on CPU
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

#### With GPU Support (If Available)
```bash
# Create GPU-enabled compose file
cp docker-compose.yml docker-compose.gpu.yml

# Edit docker-compose.gpu.yml and add GPU configuration:
# deploy:
#   resources:
#     reservations:
#       devices:
#         - driver: nvidia
#           count: 1
#           capabilities: [gpu]

# Start with GPU support
docker-compose -f docker-compose.gpu.yml up -d
```

### Manual Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Start the server:
```bash
python main.py
```

## API Endpoints

### Health & System
- `GET /api/v1/health` - System health check
- `GET /api/v1/services` - List registered services

### Facial Recognition
- `POST /api/v1/facial-recognition/identify-scene` - Identify performers in scenes
- `POST /api/v1/facial-recognition/identify-gallery` - Identify performers in galleries
- `POST /api/v1/facial-recognition/identify-image` - Identify performers in single images
- `POST /api/v1/facial-recognition/compare-faces` - Compare faces between performers

### Content Analysis (Coming Soon)
- `POST /api/v1/content-analysis/analyze-scene` - Analyze scene content
- `POST /api/v1/content-analysis/extract-metadata` - Extract metadata

### Batch Processing (Coming Soon)
- `POST /api/v1/batch/submit` - Submit batch jobs
- `GET /api/v1/batch/{job_id}/status` - Get batch job status

## Configuration

### Environment Variables
- `LOG_LEVEL` - Logging level (default: info)
- `VISAGE_URL` - Visage service URL (default: http://visage:8000)

### Service Registry
Services are automatically registered with health monitoring. Default services:
- **Visage**: Facial recognition service with ArcFace and FaceNet models

## Development

### Project Structure
```
StashAIServer/
├── main.py              # Main FastAPI gateway application
├── schemas/             # API schema definitions
│   └── api_schema.py
├── services/            # Service adapters and registry
│   ├── service_registry.py
│   └── visage_adapter.py
├── BackendServers/      # All backend AI services
│   ├── README.md        # Backend services documentation
│   └── visage/          # Facial recognition service
│       ├── Dockerfile
│       ├── app.py       # Visage FastAPI service
│       ├── models/      # Pre-trained ML models
│       └── requirements.txt
├── requirements.txt     # Gateway dependencies
├── Dockerfile           # Gateway container configuration
└── docker-compose.yml  # Complete system orchestration
```

### Adding New APIs with Database Tracking

StashAI Server includes a modular processor framework that provides **automatic database tracking, job lifecycle management, and statistics collection** for all API endpoints. This ensures consistent monitoring and analytics across all AI services.

#### Framework Benefits
- **Automatic Database Integration**: All API calls are tracked with full job/test records
- **Progress Monitoring**: Real-time progress updates via WebSocket
- **Statistics Collection**: Performance metrics, confidence scores, and result aggregation
- **Error Handling**: Comprehensive error tracking and recovery
- **Cancellation Support**: Graceful job cancellation with proper cleanup
- **Consistent Architecture**: All APIs follow the same patterns and conventions

#### Quick Start: Adding a New API

1. **Create a Processor Class**
   ```python
   # processors/my_new_processor.py
   from processors.base_processor import BaseAPIProcessor
   from database.models import EntityType, AIActionType
   
   class MyNewProcessor(BaseAPIProcessor):
       async def process_request(self, request, **kwargs):
           # Your core business logic here
           return your_api_response
       
       def get_entity_info(self, request):
           # Extract entity info from request
           return EntityType.SCENE, entity_id, entity_name, entity_filepath
       
       def get_action_type(self):
           return AIActionType.CONTENT_ANALYSIS  # or your action type
       
       def extract_results(self, response):
           # Extract standardized results for database storage
           return {
               'success': response.success,
               'performers_found': len(response.performers),
               'confidence_scores': [...],
               # ... other metrics
           }
   ```

2. **Register Your Processor**
   ```python
   # processors/__init__.py
   from .my_new_processor import MyNewProcessor
   
   PROCESSOR_REGISTRY = {
       'scene': SceneProcessor,
       'gallery': GalleryProcessor,
       'image': ImageProcessor,
       'my_new_type': MyNewProcessor,  # Add your processor
   }
   ```

3. **Add API Endpoint**
   ```python
   # main.py
   @app.post("/api/v1/my-service/process")
   async def process_my_service(request: MyServiceRequest):
       from processors import get_processor
       
       processor = get_processor('my_new_type')
       response, job_id = await processor.process_with_tracking(request)
       return response
   ```

4. **Add Queue Support (Optional)**
   ```python
   # simple_queue.py - Add to the job type handler
   elif job.job_type == "my_new_type":
       result = await self._process_job_with_processor(job, 'my_new_type')
   ```

5. **Add Queue Endpoint (Optional)**
   ```python
   # main.py
   @app.post("/api/v1/queue/submit/my-service")
   async def submit_my_service_to_queue(request: MyServiceRequest):
       job_id = await simple_queue.submit_job("my_new_type", request.dict())
       return {"success": True, "job_id": job_id}
   ```

#### What You Get Automatically

When you use the modular processor framework, your API automatically gets:

**Database Tracking:**
- Job records in `processing_jobs` table with full lifecycle tracking
- Test records in `processing_tests` table with detailed results
- Interaction records in `user_interactions` table for analytics

**Job Management:**
- Job status tracking (pending → processing → completed/failed/cancelled)
- Processing time measurement
- Progress percentage calculation
- Error handling and recovery

**Statistics Collection:**
- Performance metrics (processing time, success rate)
- AI model results (confidence scores, performers found)
- Result aggregation and summaries
- Historical analytics data

**Real-time Features:**
- WebSocket progress updates via `/ws/queue`
- Live job status monitoring
- Cancellation support with proper cleanup

**API Endpoints (Automatic):**
- Direct processing: `POST /api/v1/your-service/process`
- Queue submission: `POST /api/v1/queue/submit/your-service`
- Job status: `GET /api/v1/queue/status/{job_id}`
- Queue monitoring: `WebSocket /ws/queue`

#### Advanced Configuration

**Custom Entity Types:**
```python
# database/models.py - Add new entity type
class EntityType(str, Enum):
    SCENE = "scene"
    GALLERY = "gallery"
    IMAGE = "image"
    VIDEO = "video"      # Your new type
    PERFORMER = "performer"
```

**Custom Action Types:**
```python
# database/models.py - Add new action type
class AIActionType(str, Enum):
    FACIAL_RECOGNITION = "facial_recognition"
    SCENE_IDENTIFICATION = "scene_identification"
    VIDEO_ANALYSIS = "video_analysis"  # Your new action
    CONTENT_MODERATION = "content_moderation"
```

**Progress Tracking:**
```python
async def process_request(self, request, **kwargs):
    progress_callback = kwargs.get('progress_callback')
    
    for i, item in enumerate(items_to_process):
        # Process item
        result = await process_item(item)
        
        # Report progress
        if progress_callback:
            await progress_callback(i + 1, len(items_to_process), f"Processed {item}")
```

#### Database Schema

All tracked APIs automatically populate these tables:

**processing_jobs** - Job-level tracking
- Job identification, entity info, status, timing
- Progress statistics, result summaries
- Error handling and recovery data

**processing_tests** - Individual test tracking  
- Test-level results, confidence scores
- Detailed AI model outputs, performance metrics
- Entity-specific data and file paths

**user_interactions** - Analytics and usage tracking
- User interaction patterns, API usage
- Success rates, performance trends
- Service utilization metrics

#### Best Practices

1. **Always inherit from BaseAPIProcessor**
2. **Implement all abstract methods**
3. **Use standard entity and action types when possible**
4. **Extract meaningful metrics in extract_results()**
5. **Handle cancellation gracefully**
6. **Provide progress updates for long-running operations**
7. **Test with both direct API calls and queue processing**

#### Migration from Legacy APIs

If you have existing APIs without tracking:

1. Create a processor class for your existing function
2. Update the API endpoint to use `processor.process_with_tracking()`
3. Test that database records are created correctly
4. Update queue processing if applicable
5. Verify WebSocket progress updates work

Your existing business logic doesn't need to change - just wrap it in a processor class!

### Adding New Services

1. Create service adapter in `services/`
2. Register service in `service_registry.py`
3. Add API endpoints in `main.py`
4. Update Docker Compose configuration
5. **Use the modular processor framework for automatic database tracking**

## Contributing

1. Follow the existing code structure
2. Add comprehensive error handling
3. Include health checks for new services
4. Update API documentation
5. **Use the modular processor framework for all new APIs**