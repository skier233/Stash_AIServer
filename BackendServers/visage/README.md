# Visage Facial Recognition Service

## Required Model Files

The service requires two model files in the `models/` directory:

```
BackendServers/visage/models/
├── face_arc.voy      ✅ Present
└── face_facenet.voy  ✅ Present
```

## Setup Instructions

1. **Verify model files are present:**
   ```bash
   ls -la models/
   # Should show both .voy files (already included)
   ```

2. **Run the service:**
   ```bash
   cd ../../  # Back to StashAIServer root
   docker-compose up --build -d
   ```

## For New Users

If you're setting this up from scratch and missing model files:

1. **Create models directory:**
   ```bash
   mkdir -p models
   ```

2. **Add your ArcFace and FaceNet model files:**
   - Copy `face_arc.voy` to `models/face_arc.voy`
   - Copy `face_facenet.voy` to `models/face_facenet.voy`

## Troubleshooting

If you see `RuntimeError: Failed to open file for reading: face_arc.voy`:
- ✅ Check that model files exist in the `models/` directory
- ✅ Ensure Docker has access to the models directory
- ✅ Verify file permissions are readable
- ✅ Try rebuilding: `docker-compose up --build -d`

## Model File Details

These are standard facial recognition model files:
- **face_arc.voy**: ArcFace model for face embeddings
- **face_facenet.voy**: FaceNet model for face recognition

The service automatically detects and loads these models on startup.
