# Backend Services

This directory contains all the backend AI services that integrate with the StashAI Server gateway.

## Services

### Visage - Facial Recognition Service
- **Location**: `./visage/`
- **Purpose**: Facial recognition and performer identification
- **Technology**: Python, DeepFace, ArcFace, FaceNet
- **Endpoints**: 
  - Port 8000: FastAPI service
  - Port 7860: Gradio web interface
- **Capabilities**:
  - Single performer identification
  - Multiple performer identification  
  - Face comparison and similarity
  - Batch processing
  - Ensemble model inference (ArcFace + FaceNet)

## Adding New Services

To add a new AI service:

1. Create a new directory under `BackendServers/`
2. Include Dockerfile and requirements
3. Update the main `docker-compose.yml` to include the service
4. Create an adapter in `../services/` to interface with the service
5. Register the service in `../services/service_registry.py`
6. Add API endpoints in `../main.py`

## Architecture

```
StashAIServer/
├── main.py                    # Gateway service
├── services/
│   ├── service_registry.py    # Service discovery
│   └── visage_adapter.py     # Visage integration
├── BackendServers/
│   ├── visage/               # Facial recognition
│   └── [future-services]/    # Additional AI services
└── docker-compose.yml        # Multi-service orchestration
```

Each backend service communicates with the StashAI Gateway through standardized adapters, providing a unified API interface for all AI capabilities.