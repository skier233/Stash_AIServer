"""
Centralized configuration for service URLs and settings.

Loads environment variables from a .env file if present and exposes
typed, centralized access to configuration values so code doesn't
need to read os.environ in many places.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# Load environment variables from .env if available
try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:
    # If python-dotenv isn't installed or any other issue occurs,
    # just rely on existing environment variables.
    pass


def _env(key: str, default: str | None = None) -> str | None:
    val = os.getenv(key)
    return val if val is not None and val != "" else default


@dataclass(frozen=True)
class Config:
    """Application configuration values.

    Notes on defaults:
    - Defaults favor Docker Compose service names when applicable so
      inter-container calls work without extra setup. Override in .env
      for local development.
    """

    # Base URLs for internal services
    VISAGE_API_URL: str = _env("VISAGE_API_URL", "http://visage:8000/api/predict_1")

    # Optional external services; set in .env or the adapters will raise
    CONTENT_ANALYSIS_API_URL: str | None = _env("CONTENT_ANALYSIS_API_URL")
    SCENE_ANALYSIS_API_URL: str | None = _env("SCENE_ANALYSIS_API_URL")

    # FastAPI app base URL (used by internal HTTP callbacks / websocket broadcaster)
    # Prefer Docker service name, then fall back to localhost variants as needed.
    STASH_INTERNAL_BASE_URL: str = _env("STASH_INTERNAL_BASE_URL", "http://stash-ai-server:9998")
    STASH_LOCAL_BASE_URL: str = _env("STASH_LOCAL_BASE_URL", "http://localhost:9998")
    STASH_LOOPBACK_BASE_URL: str = _env("STASH_LOOPBACK_BASE_URL", "http://127.0.0.1:9998")


# A singleton-style exported configuration instance for easy imports
config = Config()
