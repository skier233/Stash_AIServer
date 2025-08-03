# =============================================================================
# StashAI Server - Database Migrations
# =============================================================================
# Handles database schema migrations and version management

import logging
import os
import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)

# Database version management
CURRENT_SCHEMA_VERSION = "2.1.0"
MINIMUM_SUPPORTED_VERSION = "1.0.0"

class DatabaseMigrator:
    """Handles database migrations and version management"""
    
    def __init__(self, database_path: str):
        self.database_path = database_path
        self.backup_dir = Path(database_path).parent / "backups"
        self.backup_dir.mkdir(exist_ok=True)
    
    def get_database_version(self) -> Optional[str]:
        """Get current database schema version"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            # Check if version table exists
            cursor.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='schema_version'
            """)
            
            if not cursor.fetchone():
                # No version table - assume legacy v1.0.0
                conn.close()
                return "1.0.0"
            
            # Get current version
            cursor.execute("SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1")
            result = cursor.fetchone()
            conn.close()
            
            return result[0] if result else "1.0.0"
            
        except Exception as e:
            logger.error(f"Error getting database version: {e}")
            return None
    
    def create_version_table(self) -> bool:
        """Create schema version tracking table"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    version TEXT NOT NULL,
                    description TEXT,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    migration_file TEXT,
                    rollback_sql TEXT
                )
            """)
            
            # Insert initial version if table was just created
            cursor.execute("SELECT COUNT(*) FROM schema_version")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO schema_version (version, description, migration_file)
                    VALUES (?, ?, ?)
                """, ("1.0.0", "Initial legacy schema", "baseline"))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error creating version table: {e}")
            return False
    
    def backup_database(self, version: str) -> str:
        """Create backup of database before migration"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"stash_ai_backup_v{version}_{timestamp}.db"
        backup_path = self.backup_dir / backup_filename
        
        try:
            # Copy database file
            import shutil
            shutil.copy2(self.database_path, backup_path)
            logger.info(f"Database backup created: {backup_path}")
            return str(backup_path)
            
        except Exception as e:
            logger.error(f"Error creating database backup: {e}")
            raise
    
    def verify_tables_exist(self, required_tables: List[str]) -> Dict[str, bool]:
        """Verify that required tables exist in database"""
        try:
            conn = sqlite3.connect(self.database_path)
            cursor = conn.cursor()
            
            results = {}
            for table in required_tables:
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name=?
                """, (table,))
                results[table] = cursor.fetchone() is not None
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Error verifying tables: {e}")
            return {table: False for table in required_tables}
    
    def migrate_to_v2(self) -> bool:
        """Migrate from v1.x to v2.0.0 schema"""
        logger.info("Starting migration to database schema v2.0.0")
        
        try:
            # 1. Create backup
            current_version = self.get_database_version()
            backup_path = self.backup_database(current_version)
            
            # 2. Create version table if it doesn't exist
            if not self.create_version_table():
                raise Exception("Failed to create version table")
            
            # 3. Create V2 tables
            self._create_v2_tables()
            
            # 4. Migrate existing data
            if current_version.startswith("1."):
                self._migrate_v1_to_v2_data()
            
            # 5. Update schema version
            self._update_schema_version("2.0.0", "Migration to robust hybrid schema with Model Evaluators", "migrate_to_v2")
            
            logger.info("Successfully migrated to database schema v2.0.0")
            return True
            
        except Exception as e:
            logger.error(f"Migration to v2.0.0 failed: {e}")
            import traceback
            logger.error(f"Migration traceback: {traceback.format_exc()}")
            return False
    
    def migrate_to_v21(self) -> bool:
        """Migrate from v2.0.0 to v2.1.0 - Unified interactions table"""
        logger.info("Starting migration to database schema v2.1.0")
        
        try:
            # 1. Create backup
            current_version = self.get_database_version()
            backup_path = self.backup_database(current_version)
            
            # 2. Apply v2.1.0 changes
            self._apply_v21_changes()
            
            # 3. Update schema version
            self._update_schema_version("2.1.0", "Unified interactions table schema consolidation", "migrate_to_v21")
            
            logger.info("Successfully migrated to database schema v2.1.0")
            return True
            
        except Exception as e:
            logger.error(f"Migration to v2.0.0 failed: {e}")
            import traceback
            logger.error(f"Migration traceback: {traceback.format_exc()}")
            return False
    
    def _create_v2_tables(self):
        """Create V2 schema tables"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        try:
            # ProcessingJob table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT UNIQUE NOT NULL,
                    job_name TEXT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_name TEXT,
                    action_type TEXT NOT NULL,
                    status TEXT DEFAULT 'pending' NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    started_at DATETIME,
                    completed_at DATETIME,
                    processing_time_seconds REAL,
                    job_config JSON,
                    service_name TEXT,
                    ai_model TEXT,
                    total_tests_planned INTEGER DEFAULT 0 NOT NULL,
                    test_entity_list JSON,
                    tests_completed INTEGER DEFAULT 0 NOT NULL,
                    tests_passed INTEGER DEFAULT 0 NOT NULL,
                    tests_failed INTEGER DEFAULT 0 NOT NULL,
                    tests_error INTEGER DEFAULT 0 NOT NULL,
                    progress_percentage REAL DEFAULT 0.0 NOT NULL,
                    overall_result TEXT,
                    performers_found_total INTEGER DEFAULT 0 NOT NULL,
                    confidence_scores_summary JSON,
                    tags_applied_summary JSON,
                    error_message TEXT,
                    error_details JSON
                )
            """)
            
            # ProcessingTest table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS processing_tests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    test_id TEXT UNIQUE NOT NULL,
                    job_id INTEGER NOT NULL,
                    job_uuid TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    entity_filepath TEXT,
                    entity_name TEXT,
                    test_name TEXT,
                    action_type TEXT NOT NULL,
                    ai_model TEXT NOT NULL,
                    model_version TEXT,
                    test_config JSON,
                    status TEXT DEFAULT 'pending' NOT NULL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    started_at DATETIME,
                    completed_at DATETIME,
                    processing_time_seconds REAL,
                    request_data JSON,
                    response_data JSON,
                    result TEXT,
                    performers_found INTEGER DEFAULT 0 NOT NULL,
                    confidence_scores JSON,
                    max_confidence REAL,
                    avg_confidence REAL,
                    tags_applied JSON,
                    evaluation_criteria JSON,
                    evaluation_reason TEXT,
                    evaluation_score REAL,
                    error_message TEXT,
                    error_type TEXT,
                    FOREIGN KEY (job_id) REFERENCES processing_jobs (id) ON DELETE CASCADE
                )
            """)
            
            # ModelEvaluator table removed - not needed
            
            # Unified Interactions table following old schema pattern
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    service TEXT NOT NULL,
                    action_type TEXT,
                    user_id TEXT,
                    interaction_metadata JSON
                )
            """)
            
            # Create indexes for performance
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_processing_jobs_status_created ON processing_jobs (status, created_at)",
                "CREATE INDEX IF NOT EXISTS idx_processing_jobs_entity_action ON processing_jobs (entity_type, action_type)",
                "CREATE INDEX IF NOT EXISTS idx_processing_jobs_progress ON processing_jobs (status, progress_percentage)",
                "CREATE INDEX IF NOT EXISTS idx_processing_tests_job_status ON processing_tests (job_id, status)",
                "CREATE INDEX IF NOT EXISTS idx_processing_tests_entity_model ON processing_tests (entity_type, ai_model)",
                "CREATE INDEX IF NOT EXISTS idx_processing_tests_result_confidence ON processing_tests (result, max_confidence)",
                "CREATE INDEX IF NOT EXISTS idx_processing_tests_created ON processing_tests (created_at)",
                "CREATE INDEX IF NOT EXISTS idx_interactions_entity ON interactions (entity_type, entity_id)",
                "CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions (session_id, timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_interactions_service ON interactions (service, timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_interactions_action ON interactions (action_type, timestamp)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            conn.commit()
            logger.info("V2 schema tables created successfully")
            
        finally:
            conn.close()
    
    def _migrate_v1_to_v2_data(self):
        """Migrate data from V1 schema to V2 schema"""
        logger.info("Migrating V1 data to V2 schema")
        
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        try:
            # Check if V1 tables exist
            v1_tables = self.verify_tables_exist(['ai_jobs', 'ai_tests', 'entity_interactions'])
            
            if v1_tables.get('ai_jobs'):
                self._migrate_ai_jobs_to_processing_jobs(cursor)
            
            if v1_tables.get('ai_tests'):
                self._migrate_ai_tests_to_processing_tests(cursor)
            
            # Migrate all old interaction tables to new unified table
            self._migrate_old_interactions_to_unified_table(cursor)
            
            # Drop old interaction tables after successful migration
            self._drop_old_interaction_tables(cursor)
            
            # Default model evaluators removed - not needed
            
            conn.commit()
            logger.info("V1 to V2 data migration completed successfully")
            
        except Exception as e:
            conn.rollback()
            logger.error(f"Error migrating V1 to V2 data: {e}")
            raise
        finally:
            conn.close()
    
    def _migrate_ai_jobs_to_processing_jobs(self, cursor):
        """Migrate ai_jobs to processing_jobs"""
        logger.info("Migrating ai_jobs to processing_jobs")
        
        cursor.execute("""
            INSERT INTO processing_jobs (
                job_id, job_name, entity_type, entity_id, entity_name, action_type,
                status, created_at, started_at, completed_at, processing_time_seconds,
                job_config, service_name, ai_model, total_tests_planned,
                progress_percentage, performers_found_total, confidence_scores_summary,
                tags_applied_summary, error_message
            )
            SELECT 
                job_id,
                job_name,
                entity_type,
                entity_id,
                entity_name,
                action_type,
                CASE status
                    WHEN 'pending' THEN 'pending'
                    WHEN 'processing' THEN 'processing'
                    WHEN 'completed' THEN 'completed'
                    WHEN 'failed' THEN 'failed'
                    ELSE 'failed'
                END,
                created_at,
                started_at,
                completed_at,
                processing_time,
                job_config,
                service_name,
                COALESCE(JSON_EXTRACT(ai_model_info, '$.model'), 'visage'),
                COALESCE(total_items, 1),
                COALESCE(progress_percentage, 0),
                COALESCE(JSON_EXTRACT(performers_found, '$.total'), 0),
                CASE 
                    WHEN top_confidence_score IS NOT NULL AND avg_confidence_score IS NOT NULL
                    THEN JSON_OBJECT(
                        'min', COALESCE(avg_confidence_score - 0.1, 0),
                        'max', top_confidence_score,
                        'avg', avg_confidence_score
                    )
                    ELSE NULL
                END,
                tags_applied,
                error_summary
            FROM ai_jobs
            WHERE job_id NOT IN (SELECT job_id FROM processing_jobs)
        """)
        
        migrated_count = cursor.rowcount
        logger.info(f"Migrated {migrated_count} jobs from ai_jobs to processing_jobs")
    
    def _migrate_ai_tests_to_processing_tests(self, cursor):
        """Migrate ai_tests to processing_tests"""
        logger.info("Migrating ai_tests to processing_tests")
        
        cursor.execute("""
            INSERT INTO processing_tests (
                test_id, job_id, job_uuid, entity_type, entity_id, entity_name,
                test_name, action_type, ai_model, status, created_at, started_at,
                completed_at, processing_time_seconds, request_data, response_data,
                result, performers_found, confidence_scores, max_confidence
            )
            SELECT 
                t.test_id,
                COALESCE(pj.id, 0) as job_id,
                t.job_uuid,
                t.entity_type,
                t.entity_id,
                t.entity_name,
                t.test_name,
                COALESCE(t.action_type, 'facial_recognition'),
                COALESCE(JSON_EXTRACT(t.ai_model_info, '$.model'), 'visage'),
                CASE t.status
                    WHEN 'pending' THEN 'pending'
                    WHEN 'processing' THEN 'processing'
                    WHEN 'completed' THEN 'pass'
                    WHEN 'failed' THEN 'fail'
                    ELSE 'error'
                END,
                t.created_at,
                t.started_at,
                t.completed_at,
                t.processing_time,
                t.request_data,
                t.response_data,
                CASE t.status
                    WHEN 'completed' THEN 'pass'
                    WHEN 'failed' THEN 'fail'
                    ELSE 'error'
                END,
                COALESCE(t.performers_found, 0),
                t.confidence_scores,
                t.max_confidence
            FROM ai_tests t
            LEFT JOIN processing_jobs pj ON pj.job_id = t.job_uuid
            WHERE t.test_id NOT IN (SELECT test_id FROM processing_tests)
        """)
        
        migrated_count = cursor.rowcount
        logger.info(f"Migrated {migrated_count} tests from ai_tests to processing_tests")
    
    def _migrate_old_interactions_to_unified_table(self, cursor):
        """Migrate old interaction tables to new unified interactions table"""
        logger.info("Migrating old interaction tables to unified interactions table")
        
        # First, check if old user_interactions table exists and migrate data
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='user_interactions'
        """)
        
        if cursor.fetchone():
            cursor.execute("""
                INSERT INTO interactions (
                    entity_type, entity_id, session_id, timestamp, service,
                    action_type, user_id, interaction_metadata
                )
                SELECT 
                    COALESCE(entity_type, 'unknown'),
                    COALESCE(entity_id, 'unknown'),
                    COALESCE(session_id, 'legacy_session'),
                    timestamp,
                    'stash_ai_server',
                    COALESCE(interaction_type, 'unknown'),
                    user_id,
                    JSON_OBJECT(
                        'page_url', page_url,
                        'element_selector', element_selector,
                        'button_text', button_text,
                        'entity_name', entity_name,
                        'job_id', job_id,
                        'test_id', test_id,
                        'interaction_data', interaction_data,
                        'scene_id', scene_id,
                        'scene_title', scene_title,
                        'current_time', current_time,
                        'duration', duration
                    )
                FROM user_interactions
            """)
            
            migrated_count = cursor.rowcount
            logger.info(f"Migrated {migrated_count} interactions from user_interactions to interactions")
        
        # Also migrate from entity_interactions if it exists
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='entity_interactions'
        """)
        
        if cursor.fetchone():
            cursor.execute("""
                INSERT INTO interactions (
                    entity_type, entity_id, session_id, timestamp, service,
                    action_type, user_id, interaction_metadata
                )
                SELECT 
                    entity_type,
                    entity_id,
                    COALESCE(session_id, 'legacy_session'),
                    timestamp,
                    'stash_ai_server',
                    action_type,
                    user_id,
                    JSON_OBJECT(
                        'job_uuid', job_uuid,
                        'test_uuid', test_uuid,
                        'success', success,
                        'performers_found', performers_found,
                        'confidence_scores', confidence_scores,
                        'tags_added', tags_added,
                        'metadata_extracted', metadata_extracted,
                        'request_id', request_id
                    )
                FROM entity_interactions
                WHERE NOT EXISTS (
                    SELECT 1 FROM interactions i 
                    WHERE i.entity_type = entity_interactions.entity_type 
                    AND i.entity_id = entity_interactions.entity_id 
                    AND i.timestamp = entity_interactions.timestamp
                )
            """)
            
            migrated_count = cursor.rowcount
            logger.info(f"Migrated {migrated_count} interactions from entity_interactions to interactions")
    
    def _apply_v21_changes(self):
        """Apply v2.1.0 schema changes - unified interactions table"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        try:
            # 1. Create new unified interactions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                    service TEXT NOT NULL,
                    action_type TEXT,
                    user_id TEXT,
                    interaction_metadata JSON
                )
            """)
            
            # 2. Create indexes for the new table
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_interactions_entity ON interactions (entity_type, entity_id)",
                "CREATE INDEX IF NOT EXISTS idx_interactions_session ON interactions (session_id, timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_interactions_service ON interactions (service, timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_interactions_action ON interactions (action_type, timestamp)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
            
            # 3. Migrate data from old tables to new unified table
            self._migrate_old_interactions_to_unified_table(cursor)
            
            # 4. Drop old interaction tables
            self._drop_old_interaction_tables(cursor)
            
            # 5. Add missing columns to processing_jobs table if needed
            cursor.execute("""
                ALTER TABLE processing_jobs ADD COLUMN results_json JSON
            """)
            cursor.execute("""
                ALTER TABLE processing_jobs ADD COLUMN results_summary JSON  
            """)
            
            conn.commit()
            logger.info("V2.1.0 schema changes applied successfully")
            
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("Columns already exist, skipping ALTER TABLE")
            else:
                raise
        finally:
            conn.close()
    
    def _drop_old_interaction_tables(self, cursor):
        """Drop old interaction tables after successful migration"""
        logger.info("Dropping old interaction tables")
        
        old_tables = [
            'interaction_tags',
            'interaction_studios', 
            'interaction_performers',
            'interaction_markers',
            'user_interactions',
            'entity_interactions'
        ]
        
        for table in old_tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS {table}")
                logger.info(f"Dropped table: {table}")
            except Exception as e:
                logger.warning(f"Failed to drop table {table}: {e}")
    
    def _update_schema_version(self, version: str, description: str, migration_file: str):
        """Update schema version in database"""
        conn = sqlite3.connect(self.database_path)
        cursor = conn.cursor()
        
        try:
            cursor.execute("""
                INSERT INTO schema_version (version, description, migration_file)
                VALUES (?, ?, ?)
            """, (version, description, migration_file))
            
            conn.commit()
            logger.info(f"Updated schema version to {version}")
            
        finally:
            conn.close()
    
    def needs_migration(self) -> bool:
        """Check if database needs migration"""
        current_version = self.get_database_version()
        if not current_version:
            return True
        
        # Compare versions (simplified version comparison)
        current_parts = [int(x) for x in current_version.split('.')]
        target_parts = [int(x) for x in CURRENT_SCHEMA_VERSION.split('.')]
        
        # If current version is less than target version, migration is needed
        for i in range(max(len(current_parts), len(target_parts))):
            current_part = current_parts[i] if i < len(current_parts) else 0
            target_part = target_parts[i] if i < len(target_parts) else 0
            
            if current_part < target_part:
                return True
            elif current_part > target_part:
                return False
        
        return False
    
    def run_migration(self) -> bool:
        """Run database migration if needed"""
        if not self.needs_migration():
            logger.info("Database is up to date, no migration needed")
            return True
        
        current_version = self.get_database_version()
        logger.info(f"Migrating database from version {current_version} to {CURRENT_SCHEMA_VERSION}")
        
        # Support multiple migration paths
        if current_version and current_version.startswith("1."):
            return self.migrate_to_v2()
        elif current_version == "2.0.0":
            return self.migrate_to_v21()
        else:
            logger.error(f"Unsupported migration path from {current_version} to {CURRENT_SCHEMA_VERSION}")
            return False

# Convenience functions
def verify_database_version(database_path: str) -> Dict[str, Any]:
    """Verify database version and return status information"""
    migrator = DatabaseMigrator(database_path)
    
    current_version = migrator.get_database_version()
    needs_migration = migrator.needs_migration()
    
    # Check V2 tables exist
    v2_tables = ['processing_jobs', 'processing_tests', 'user_interactions']
    table_status = migrator.verify_tables_exist(v2_tables)
    
    return {
        'current_version': current_version,
        'target_version': CURRENT_SCHEMA_VERSION,
        'needs_migration': needs_migration,
        'schema_tables_exist': all(table_status.values()),
        'table_status': table_status,
        'database_path': database_path
    }

def run_startup_migration(database_path: str) -> bool:
    """Run database migration on startup if needed"""
    try:
        migrator = DatabaseMigrator(database_path)
        return migrator.run_migration()
    except Exception as e:
        logger.error(f"Startup migration failed: {e}")
        return False