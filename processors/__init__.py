# =============================================================================
# Processors Package - Modular API Processing Framework
# =============================================================================

from .base_processor import BaseAPIProcessor
from .scene_processor import SceneProcessor
from .gallery_processor import GalleryProcessor
from .image_processor import ImageProcessor

# Processor Registry - Easy way to get processors by type
PROCESSOR_REGISTRY = {
    'scene': SceneProcessor,
    'gallery': GalleryProcessor,
    'image': ImageProcessor,
}

def get_processor(processor_type: str) -> BaseAPIProcessor:
    """
    Get a processor instance by type.
    
    Args:
        processor_type: The type of processor ('scene', 'gallery', 'image')
        
    Returns:
        An instance of the appropriate processor
        
    Raises:
        ValueError: If processor_type is not recognized
    """
    if processor_type not in PROCESSOR_REGISTRY:
        raise ValueError(f"Unknown processor type: {processor_type}. Available: {list(PROCESSOR_REGISTRY.keys())}")
    
    processor_class = PROCESSOR_REGISTRY[processor_type]
    return processor_class()

__all__ = [
    'BaseAPIProcessor',
    'SceneProcessor', 
    'GalleryProcessor',
    'ImageProcessor',
    'PROCESSOR_REGISTRY',
    'get_processor'
]