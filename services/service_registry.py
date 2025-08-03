# =============================================================================
# StashAI Server - Service Registry and Discovery
# =============================================================================

import asyncio
import aiohttp
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum
import json

from schemas.api_schema import ServiceInfo, ServiceType, HealthCheckResponse

logger = logging.getLogger(__name__)

# =============================================================================
# Service Status and Configuration
# =============================================================================

class ServiceStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"
    MAINTENANCE = "maintenance"
    BUSY = "busy"  # Service is healthy but under load
    DEGRADED = "degraded"  # Service responding but slowly

@dataclass
class RegisteredService:
    """Internal representation of a registered service"""
    name: str
    type: ServiceType
    version: str
    endpoint: str
    health_check_url: str
    capabilities: List[str]
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_health_check: Optional[datetime] = None
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

# =============================================================================
# Service Registry Class
# =============================================================================

class ServiceRegistry:
    """
    Manages service registration, discovery, and health monitoring
    """
    
    def __init__(self, health_check_interval: int = 30, max_failures: int = 3, batch_processing_timeout: int = 30):
        self.services: Dict[str, RegisteredService] = {}
        self.health_check_interval = health_check_interval
        self.max_failures = max_failures
        self.batch_processing_timeout = batch_processing_timeout  # Extended timeout during batch processing
        self._health_check_task: Optional[asyncio.Task] = None
        self._running = False
        self._batch_processing_active: bool = False  # Track if batch processing is active
        
    async def start(self):
        """Start the service registry and health monitoring"""
        if self._running:
            return
            
        self._running = True
        self._health_check_task = asyncio.create_task(self._health_check_loop())
        logger.info("Service registry started with health check interval: %ds", self.health_check_interval)
        
    async def stop(self):
        """Stop the service registry"""
        self._running = False
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
        logger.info("Service registry stopped")
        
    def register_service(
        self,
        name: str,
        service_type: ServiceType,
        version: str,
        endpoint: str,
        health_check_url: str,
        capabilities: List[str],
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Register a new service"""
        try:
            service = RegisteredService(
                name=name,
                type=service_type,
                version=version,
                endpoint=endpoint,
                health_check_url=health_check_url,
                capabilities=capabilities,
                metadata=metadata or {}
            )
            
            self.services[name] = service
            logger.info(f"Registered service: {name} ({service_type}) at {endpoint}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to register service {name}: {e}")
            return False
            
    def unregister_service(self, name: str) -> bool:
        """Unregister a service"""
        if name in self.services:
            del self.services[name]
            logger.info(f"Unregistered service: {name}")
            return True
        return False
        
    def get_service(self, name: str) -> Optional[RegisteredService]:
        """Get a specific service by name"""
        return self.services.get(name)
        
    def get_healthy_services(self, service_type: Optional[ServiceType] = None) -> List[RegisteredService]:
        """Get all healthy services, optionally filtered by type"""
        services = self.services.values()
        if service_type:
            services = [s for s in services if s.type == service_type]
        return [s for s in services if s.status == ServiceStatus.HEALTHY]
    
    def get_available_services(self, service_type: Optional[ServiceType] = None, include_busy: bool = True) -> List[RegisteredService]:
        """Get all available services (healthy, degraded, or busy), optionally filtered by type"""
        services = self.services.values()
        if service_type:
            services = [s for s in services if s.type == service_type]
        
        available_statuses = [ServiceStatus.HEALTHY, ServiceStatus.DEGRADED]
        if include_busy:
            available_statuses.append(ServiceStatus.BUSY)
            
        return [s for s in services if s.status in available_statuses]
        
    def get_service_for_capability(self, capability: str) -> Optional[RegisteredService]:
        """Find a healthy service that has a specific capability"""
        for service in self.services.values():
            if (service.status == ServiceStatus.HEALTHY and 
                capability in service.capabilities):
                return service
        return None
        
    def list_all_services(self) -> List[ServiceInfo]:
        """Get public service information for all registered services"""
        return [
            ServiceInfo(
                name=service.name,
                type=service.type,
                version=service.version,
                endpoint=service.endpoint,
                health_check_url=service.health_check_url,
                capabilities=service.capabilities,
                status=service.status.value,
                last_health_check=service.last_health_check
            )
            for service in self.services.values()
        ]
        
    async def check_service_health(self, service: RegisteredService, is_batch_processing: bool = False) -> bool:
        """Check the health of a specific service with batch processing awareness"""
        try:
            # Use extended timeout during batch processing
            timeout_duration = self.batch_processing_timeout if is_batch_processing else 10
            timeout = aiohttp.ClientTimeout(total=timeout_duration)
            
            start_time = datetime.utcnow()
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(service.health_check_url) as response:
                    response_time = (datetime.utcnow() - start_time).total_seconds()
                    
                    if response.status == 200:
                        # Determine service status based on response time and context
                        if response_time > 15 and is_batch_processing:
                            service.status = ServiceStatus.BUSY
                            logger.debug(f"Service {service.name} is BUSY (response time: {response_time:.2f}s)")
                        elif response_time > 5:
                            service.status = ServiceStatus.DEGRADED
                            logger.debug(f"Service {service.name} is DEGRADED (response time: {response_time:.2f}s)")
                        else:
                            service.status = ServiceStatus.HEALTHY
                            logger.debug(f"Service {service.name} is HEALTHY (response time: {response_time:.2f}s)")
                        
                        service.consecutive_failures = 0
                        service.last_health_check = datetime.utcnow()
                        return True
                    elif response.status == 503 and is_batch_processing:
                        # 503 during batch processing might mean busy, not down
                        service.status = ServiceStatus.BUSY
                        service.last_health_check = datetime.utcnow()
                        logger.warning(f"Service {service.name} returned 503 during batch processing - marking as BUSY")
                        return True  # Still consider it available
                            
        except asyncio.TimeoutError:
            if is_batch_processing and service.consecutive_failures < 2:
                # Be more lenient during batch processing
                service.status = ServiceStatus.BUSY
                service.consecutive_failures += 1
                service.last_health_check = datetime.utcnow()
                logger.warning(f"Service {service.name} timed out during batch processing - marking as BUSY")
                return True
            else:
                logger.warning(f"Health check timeout for {service.name} (timeout: {timeout_duration}s)")
        except Exception as e:
            logger.warning(f"Health check failed for {service.name}: {e}")
            
        # Mark as unhealthy only after multiple failures
        service.consecutive_failures += 1
        if service.consecutive_failures >= self.max_failures:
            service.status = ServiceStatus.UNHEALTHY
            logger.error(f"Service {service.name} marked as UNHEALTHY after {service.consecutive_failures} failures")
        else:
            service.status = ServiceStatus.DEGRADED
            logger.warning(f"Service {service.name} marked as DEGRADED (failure {service.consecutive_failures}/{self.max_failures})")
        
        service.last_health_check = datetime.utcnow()
        return service.consecutive_failures < self.max_failures
        
    async def _health_check_loop(self):
        """Background task to periodically check service health"""
        while self._running:
            try:
                if self.services:
                    logger.debug(f"Running health checks for {len(self.services)} services")
                    
                    # Check all services concurrently with batch processing context
                    tasks = [
                        self.check_service_health(service, is_batch_processing=self._batch_processing_active)
                        for service in self.services.values()
                    ]
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    
                    healthy_count = sum(1 for r in results if r is True)
                    logger.debug(f"Health check complete: {healthy_count}/{len(self.services)} services healthy")
                    
                await asyncio.sleep(self.health_check_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(5)  # Brief pause before retrying

# =============================================================================
# Service Discovery Helpers
# =============================================================================

class ServiceDiscovery:
    """Helper class for service discovery operations"""
    
    def __init__(self, registry: ServiceRegistry):
        self.registry = registry
        
    def set_batch_processing_active(self, active: bool):
        """Set batch processing active state to inform health checks"""
        self._batch_processing_active = active
        logger.info(f"Batch processing {'activated' if active else 'deactivated'}")
        

class BatchProcessingContext:
    """Context manager for batch processing operations"""
    
    def __init__(self, service_discovery: 'ServiceDiscovery'):
        self.service_discovery = service_discovery
        
    async def __aenter__(self):
        """Enter batch processing context"""
        self.service_discovery.registry._batch_processing_active = True
        logger.info("Batch processing activated")
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit batch processing context"""
        self.service_discovery.registry._batch_processing_active = False
        logger.info("Batch processing deactivated")

# =============================================================================
# Default Service Configurations
# =============================================================================

DEFAULT_SERVICES = {
    "visage": {
        "name": "visage",
        "service_type": ServiceType.FACIAL_RECOGNITION,
        "version": "1.0.0",
        "endpoint": "http://visage:8000",
        "health_check_url": "http://visage:8000/api/person_names",
        "capabilities": [
            "facial_recognition",
            "performer_identification", 
            "face_comparison",
            "batch_processing",
            "ensemble_models"
        ],
        "metadata": {
            "models": ["arcface", "facenet"],
            "max_batch_size": 50,
            "supported_formats": ["jpeg", "png", "webp"]
        }
    }
}

def create_default_registry() -> ServiceRegistry:
    """Create a service registry with default services"""
    registry = ServiceRegistry()
    
    # Register default services with environment variable overrides
    for service_name, service_config in DEFAULT_SERVICES.items():
        config = service_config.copy()
        
        # Override Visage URL with environment variable if available
        if service_name == "visage":
            visage_url = os.getenv("VISAGE_URL", config["endpoint"])
            config["endpoint"] = visage_url
            config["health_check_url"] = f"{visage_url}/api/person_names"
            logger.info(f"Visage service configured with URL: {visage_url}")
        
        registry.register_service(**config)
        
    return registry