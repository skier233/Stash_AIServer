# =============================================================================
# StashAI Server - Database Configuration and Session Management
# =============================================================================

import os
import logging
from typing import Any, Dict, Generator, Optional
from database.migrations import CURRENT_SCHEMA_VERSION, DatabaseMigrator
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base

logger = logging.getLogger(__name__)

# =============================================================================
# Database Configuration
# =============================================================================

# Database URL - use SQLite for simplicity, but can be configured for PostgreSQL/MySQL
DATABASE_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")
os.makedirs(DATABASE_DIR, exist_ok=True)

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    f"sqlite:///{os.path.join(DATABASE_DIR, 'stash_ai.db')}"
)

# Configure engine based on database type
if DATABASE_URL.startswith("sqlite"):
    # SQLite configuration with proper threading support
    engine = create_engine(
        DATABASE_URL,
        connect_args={
            "check_same_thread": False,
            "timeout": 20
        },
        poolclass=StaticPool,
        echo=False  # Set to True for SQL logging
    )
    
    # Enable WAL mode for better concurrency
    @event.listens_for(engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA temp_store=MEMORY")
        cursor.execute("PRAGMA mmap_size=268435456")  # 256MB
        cursor.close()
        
else:
    # PostgreSQL/MySQL configuration
    engine = create_engine(
        DATABASE_URL,
        pool_size=10,
        max_overflow=20,
        pool_pre_ping=True,
        echo=False
    )

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# =============================================================================
# Database Initialization
# =============================================================================

def create_tables():
    """Create all database tables"""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
    except Exception as e:
        logger.error(f"Failed to create database tables: {e}")
        raise

def drop_tables():
    """Drop all database tables (for testing/reset)"""
    try:
        Base.metadata.drop_all(bind=engine)
        logger.info("Database tables dropped successfully")
    except Exception as e:
        logger.error(f"Failed to drop database tables: {e}")
        raise

# =============================================================================
# Session Management
# =============================================================================

def get_db() -> Generator[Session, None, None]:
    """
    Database session dependency for FastAPI.
    Creates a new database session for each request and closes it when done.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class DatabaseManager:
    """Database manager for handling connections and transactions"""
    
    def __init__(self):
        self.engine = engine
        self.SessionLocal = SessionLocal
    
    def get_session(self) -> Session:
        """Get a new database session"""
        return SessionLocal()
    
    def create_all_tables(self):
        """Create all database tables"""
        create_tables()
    
    def drop_all_tables(self):
        """Drop all database tables"""
        drop_tables()
    
    def health_check(self) -> bool:
        """Check if database is accessible"""
        try:
            with SessionLocal() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return False
    
    def get_database_info(self) -> dict:
        """Get database information"""
        try:
            with SessionLocal() as session:
                if DATABASE_URL.startswith("sqlite"):
                    # SQLite specific info
                    result = session.execute(text("PRAGMA database_list")).fetchall()
                    db_file = result[0][2] if result else "unknown"
                    size_result = session.execute(text("PRAGMA page_count")).fetchone()
                    page_size_result = session.execute(text("PRAGMA page_size")).fetchone()
                    
                    page_count = size_result[0] if size_result else 0
                    page_size = page_size_result[0] if page_size_result else 0
                    db_size = page_count * page_size
                    
                    return {
                        "type": "sqlite",
                        "file": db_file,
                        "size_bytes": db_size,
                        "page_count": page_count,
                        "page_size": page_size
                    }
                else:
                    # Other database types
                    result = session.execute(text("SELECT version()")).fetchone()
                    version = result[0] if result else "unknown"
                    
                    return {
                        "type": "other",
                        "version": version,
                        "url": DATABASE_URL.split("@")[-1] if "@" in DATABASE_URL else "configured"
                    }
                    
        except Exception as e:
            logger.error(f"Failed to get database info: {e}")
            return {"error": str(e)}

# Global database manager instance
db_manager = DatabaseManager()

# =============================================================================
# Database Context Manager
# =============================================================================

class DatabaseSession:
    """Context manager for database sessions with automatic rollback on error"""
    
    def __init__(self):
        self.session: Optional[Session] = None
    
    def __enter__(self) -> Session:
        self.session = SessionLocal()
        return self.session
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            try:
                if exc_type:
                    self.session.rollback()
                    logger.error(f"Database transaction rolled back due to: {exc_val}")
                else:
                    self.session.commit()
            except Exception as e:
                self.session.rollback()
                logger.error(f"Failed to commit database transaction: {e}")
                raise
            finally:
                self.session.close()

# =============================================================================
# Database Migration Support
# =============================================================================

def migrate_database():
    """
    Run database migrations if needed.
    This handles both table creation and schema updates for existing tables.
    """
    try:
        logger.info("Starting database migration...")
        
        # First, create any new tables
        create_tables()
        
        # Then run specific migrations for schema changes
        run_schema_migrations()
        
        logger.info("Database migration completed successfully")
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise

def run_schema_migrations():
    """Run specific schema migrations for existing tables"""
    try:
        logger.info("Running schema migrations...")
        
        # Migration: Add Job/Test columns to entity_interactions table
        migrate_entity_interactions_job_columns()
        
        logger.info("Schema migrations completed successfully")
    except Exception as e:
        logger.error(f"Schema migration failed: {e}")
        raise

def migrate_entity_interactions_job_columns():
    """Add job_id, job_uuid, test_id, test_uuid columns to entity_interactions table if they don't exist"""
    try:
        with engine.connect() as conn:
            # First check if the entity_interactions table exists (it was removed in cleanup)
            if DATABASE_URL.startswith('sqlite'):
                # Check if table exists
                table_check = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='entity_interactions'")).fetchall()
                if not table_check:
                    logger.info("entity_interactions table doesn't exist (was removed in cleanup) - skipping migration")
                    return
                
                # For SQLite, check column existence  
                result = conn.execute(text("PRAGMA table_info(entity_interactions)")).fetchall()
                existing_columns = [row[1] for row in result]  # Column names are in index 1
                
                columns_to_add = [
                    ('job_id', 'INTEGER'),
                    ('job_uuid', 'VARCHAR(36)'),
                    ('test_id', 'INTEGER'),
                    ('test_uuid', 'VARCHAR(36)')
                ]
                
                for column_name, column_type in columns_to_add:
                    if column_name not in existing_columns:
                        logger.info(f"Adding column {column_name} to entity_interactions table")
                        conn.execute(text(f"ALTER TABLE entity_interactions ADD COLUMN {column_name} {column_type}"))
                        conn.commit()
                        logger.info(f"Successfully added column {column_name}")
                    else:
                        logger.debug(f"Column {column_name} already exists in entity_interactions table")
            else:
                # For PostgreSQL/MySQL, first check if table exists
                table_check = conn.execute(text("SELECT COUNT(*) FROM information_schema.tables WHERE table_name = 'entity_interactions'")).scalar()
                if table_check == 0:
                    logger.info("entity_interactions table doesn't exist (was removed in cleanup) - skipping migration")
                    return
                
                # For PostgreSQL/MySQL, use information_schema
                columns_to_add = [
                    ('job_id', 'INTEGER'),
                    ('job_uuid', 'VARCHAR(36)'),
                    ('test_id', 'INTEGER'),
                    ('test_uuid', 'VARCHAR(36)')
                ]
                
                for column_name, column_type in columns_to_add:
                    # Check if column exists
                    check_query = text("""
                        SELECT COUNT(*) FROM information_schema.columns 
                        WHERE table_name = 'entity_interactions' AND column_name = :column_name
                    """)
                    result = conn.execute(check_query, {"column_name": column_name}).scalar()
                    
                    if result == 0:
                        logger.info(f"Adding column {column_name} to entity_interactions table")
                        conn.execute(text(f"ALTER TABLE entity_interactions ADD COLUMN {column_name} {column_type}"))
                        conn.commit()
                        logger.info(f"Successfully added column {column_name}")
                    else:
                        logger.debug(f"Column {column_name} already exists in entity_interactions table")
                        
    except Exception as e:
        logger.error(f"Failed to migrate entity_interactions table: {e}")
        raise

# =============================================================================
# Initialization Function
# =============================================================================

def initialize_database():
    """Initialize database on startup"""
    try:
        logger.info(f"Initializing database: {DATABASE_URL}")
        
        # Run migrations
        migrate_database()
        
        # Health check
        if not db_manager.health_check():
            raise Exception("Database health check failed after initialization")
        
        # Log database info
        db_info = db_manager.get_database_info()
        logger.info(f"Database initialized successfully: {db_info}")
        
    except Exception as e:
        logger.error(f"Database initialization failed: {e}")
        raise


        # Don't raise - allow server to continue with legacy support

# Initialize database when module is imported
if __name__ != "__main__":
    try:
        initialize_database()
    except Exception as e:
        logger.warning(f"Database initialization failed during import: {e}")
        logger.warning("Database will be initialized when first accessed")


def get_database_path() -> str:
    """Get the path to the database file"""
    if DATABASE_URL.startswith("sqlite"):
        return DATABASE_URL.split("///")[-1]
    else:
        raise NotImplementedError("Database path retrieval is only implemented for SQLite")