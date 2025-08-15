# =============================================================================
# StashAI Server - Main FastAPI Service
# =============================================================================

import logging
import uvicorn
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

# Import our custom modules
from Database.database import init_database
from api.endpoints import router as api_router, set_websocket_manager, set_queue_manager
from Services.websocket.manager import WebSocketManager, websocket_endpoint_handler
from Services.websocket.broadcaster import queue_broadcaster
from Services.queue.manager import queue_manager

# =============================================================================
# Logging Configuration
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# WebSocket Manager
# =============================================================================

websocket_manager = WebSocketManager()

def get_websocket_manager():
    """Get the global WebSocket manager instance"""
    return websocket_manager

# Also register in builtins for cross-process access
import builtins
builtins._websocket_manager_registry = websocket_manager

# =============================================================================
# Application Lifespan Events
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Starting StashAI Server...")
    init_database()
    set_websocket_manager(websocket_manager)
    set_queue_manager(queue_manager)
    
    # Connect WebSocket broadcaster to manager
    queue_broadcaster.set_websocket_manager(websocket_manager)
    
    # Initialize queue manager as first-class citizen
    await queue_manager.startup()
    
    logger.info("StashAI Server started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down StashAI Server...")
    await queue_manager.shutdown()

# =============================================================================
# FastAPI Application
# =============================================================================

app = FastAPI(
    title="StashAI Server",
    description="Simplified StashAI Server for User Interaction Tracking",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(api_router)

# =============================================================================
# WebSocket Endpoints
# =============================================================================

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time interaction updates"""
    await websocket_endpoint_handler(websocket, session_id, websocket_manager)

# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=9998,
        reload=True,
        log_level="info"
    )