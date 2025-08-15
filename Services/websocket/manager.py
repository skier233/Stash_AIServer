# =============================================================================
# WebSocket Manager for StashAI Server
# =============================================================================

import logging
from typing import List, Dict, Set, Optional
from fastapi import WebSocket, WebSocketDisconnect
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

class WebSocketManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_sessions: Dict[WebSocket, str] = {}
        
        # Queue-specific tracking
        self.task_subscribers: Dict[str, Set[WebSocket]] = {}  # task_id -> websockets
        self.job_subscribers: Dict[str, Set[WebSocket]] = {}   # job_id -> websockets
        self.queue_stats_subscribers: Set[WebSocket] = set()  # Global queue stats

    async def connect(self, websocket: WebSocket, session_id: str = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        if session_id:
            self.connection_sessions[websocket] = session_id
        logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_sessions:
            del self.connection_sessions[websocket]
        
        # Clean up queue subscriptions
        self.unsubscribe_from_queue_stats(websocket)
        
        # Clean up task subscriptions
        for task_id in list(self.task_subscribers.keys()):
            self.unsubscribe_from_task(websocket, task_id)
        
        # Clean up job subscriptions  
        for job_id in list(self.job_subscribers.keys()):
            self.unsubscribe_from_job(websocket, job_id)
            
        logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        if self.active_connections:
            for connection in self.active_connections.copy():
                try:
                    await connection.send_json(message)
                except:
                    self.disconnect(connection)

    async def send_to_session(self, session_id: str, message: dict):
        for websocket, ws_session_id in self.connection_sessions.items():
            if ws_session_id == session_id:
                try:
                    await websocket.send_json(message)
                except:
                    self.disconnect(websocket)
    
    # =========================================================================
    # Queue-Specific WebSocket Methods
    # =========================================================================
    
    def subscribe_to_task(self, websocket: WebSocket, task_id: str):
        """Subscribe a WebSocket connection to task updates"""
        if task_id not in self.task_subscribers:
            self.task_subscribers[task_id] = set()
        self.task_subscribers[task_id].add(websocket)
        logger.debug(f"WebSocket subscribed to task {task_id}")
    
    def subscribe_to_job(self, websocket: WebSocket, job_id: str):
        """Subscribe a WebSocket connection to job updates"""
        if job_id not in self.job_subscribers:
            self.job_subscribers[job_id] = set()
        self.job_subscribers[job_id].add(websocket)
        logger.debug(f"WebSocket subscribed to job {job_id}")
    
    def subscribe_to_queue_stats(self, websocket: WebSocket):
        """Subscribe a WebSocket connection to queue statistics"""
        self.queue_stats_subscribers.add(websocket)
        logger.debug("WebSocket subscribed to queue stats")
    
    def unsubscribe_from_task(self, websocket: WebSocket, task_id: str):
        """Unsubscribe from task updates"""
        if task_id in self.task_subscribers:
            self.task_subscribers[task_id].discard(websocket)
            if not self.task_subscribers[task_id]:
                del self.task_subscribers[task_id]
    
    def unsubscribe_from_job(self, websocket: WebSocket, job_id: str):
        """Unsubscribe from job updates"""
        if job_id in self.job_subscribers:
            self.job_subscribers[job_id].discard(websocket)
            if not self.job_subscribers[job_id]:
                del self.job_subscribers[job_id]
    
    def unsubscribe_from_queue_stats(self, websocket: WebSocket):
        """Unsubscribe from queue statistics"""
        self.queue_stats_subscribers.discard(websocket)
    
    async def broadcast_task_update(self, task_id: str, message: dict):
        """Broadcast task status update to subscribed clients"""
        logger.info(f"WebSocket Manager: Broadcasting task update for {task_id}")
        if task_id in self.task_subscribers:
            subscribers = self.task_subscribers[task_id]
            logger.info(f"Found {len(subscribers)} subscribers for task {task_id}")
            
            message.update({
                "type": "task_status",
                "task_id": task_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            for websocket in subscribers.copy():
                try:
                    logger.info(f"Sending message to WebSocket: {message}")
                    await websocket.send_json(message)
                    logger.info(f"Message sent successfully to WebSocket")
                except Exception as e:
                    logger.error(f"Failed to send message to WebSocket: {e}")
                    self.unsubscribe_from_task(websocket, task_id)
                    self.disconnect(websocket)
        else:
            logger.warning(f"No subscribers found for task {task_id}. Available task subscriptions: {list(self.task_subscribers.keys())}")
    
    async def broadcast_job_update(self, job_id: str, message: dict):
        """Broadcast job progress update to subscribed clients"""
        if job_id in self.job_subscribers:
            message.update({
                "type": "job_progress",
                "job_id": job_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
            for websocket in self.job_subscribers[job_id].copy():
                try:
                    await websocket.send_json(message)
                except:
                    self.unsubscribe_from_job(websocket, job_id)
                    self.disconnect(websocket)
    
    async def broadcast_queue_stats(self, stats: dict):
        """Broadcast queue statistics to subscribed clients"""
        message = {
            "type": "queue_stats",
            "data": stats,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        for websocket in self.queue_stats_subscribers.copy():
            try:
                await websocket.send_json(message)
            except:
                self.unsubscribe_from_queue_stats(websocket)
                self.disconnect(websocket)

# =============================================================================
# WebSocket Endpoint Handler
# =============================================================================

async def websocket_endpoint_handler(websocket: WebSocket, session_id: str, manager: WebSocketManager):
    """WebSocket endpoint handler for real-time interaction and queue updates"""
    await manager.connect(websocket, session_id)
    try:
        while True:
            # Wait for messages from client
            data = await websocket.receive_json()
            
            # Handle different message types
            if data.get("type") == "ping":
                await websocket.send_json({
                    "type": "pong", 
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            elif data.get("type") == "interaction":
                # Process interaction data if needed
                logger.info(f"Received interaction via WebSocket: {data}")
            
            # ===== Queue Subscription Messages =====
            elif data.get("type") == "subscribe_task":
                task_id = data.get("task_id")
                if task_id:
                    manager.subscribe_to_task(websocket, task_id)
                    await websocket.send_json({
                        "type": "subscription_confirmed",
                        "subscription": "task",
                        "task_id": task_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            
            elif data.get("type") == "subscribe_job":
                job_id = data.get("job_id")
                if job_id:
                    manager.subscribe_to_job(websocket, job_id)
                    await websocket.send_json({
                        "type": "subscription_confirmed", 
                        "subscription": "job",
                        "job_id": job_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            
            elif data.get("type") == "subscribe_queue_stats":
                manager.subscribe_to_queue_stats(websocket)
                await websocket.send_json({
                    "type": "subscription_confirmed",
                    "subscription": "queue_stats",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            elif data.get("type") == "unsubscribe_task":
                task_id = data.get("task_id")
                if task_id:
                    manager.unsubscribe_from_task(websocket, task_id)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "subscription": "task", 
                        "task_id": task_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            
            elif data.get("type") == "unsubscribe_job":
                job_id = data.get("job_id")
                if job_id:
                    manager.unsubscribe_from_job(websocket, job_id)
                    await websocket.send_json({
                        "type": "unsubscribed",
                        "subscription": "job",
                        "job_id": job_id,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
            elif data.get("type") == "unsubscribe_queue_stats":
                manager.unsubscribe_from_queue_stats(websocket)
                await websocket.send_json({
                    "type": "unsubscribed",
                    "subscription": "queue_stats",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
            else:
                # Unknown message type
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unknown message type: {data.get('type')}",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket client {session_id} disconnected")
    except Exception as e:
        logger.error(f"WebSocket error for session {session_id}: {e}")
        manager.disconnect(websocket)