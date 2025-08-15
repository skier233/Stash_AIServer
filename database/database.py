# =============================================================================
# Database Configuration for StashAI Server
# =============================================================================

import logging
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from Database.models import Base
# Import all models to ensure they are registered with Base
from Database.data.queue_models import QueueTask, QueueJob
from Database.data.visage_results_models import VisageResult

logger = logging.getLogger(__name__)

# =============================================================================
# Database Configuration
# =============================================================================

# Create data directory if it doesn't exist
import os
DATA_DIR = Path(os.getenv("DATA_DIR", "./data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/stash_ai.db"
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# =============================================================================
# Database Functions
# =============================================================================

def init_database():
    """Initialize database and create tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Error creating database tables: {e}")
        raise

def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_db_session():
    """Get database session for direct use"""
    return SessionLocal()