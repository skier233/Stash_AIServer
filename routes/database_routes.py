import logging

from fastapi import APIRouter

from database.database import get_database_path
from database.migrations import CURRENT_SCHEMA_VERSION, verify_database_version


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/database", tags=["serviceinfo"])


@router.get("/status")
async def get_database_status():
    """Get database version and migration status"""
    try:
        database_path = get_database_path()
        db_status = verify_database_version(database_path)
        
        return {
            "success": True,
            "database_path": database_path,
            "current_version": db_status['current_version'],
            "target_version": db_status['target_version'],
            "schema_up_to_date": not db_status['needs_migration'],
            "schema_available": db_status['schema_tables_exist'],
            "table_status": db_status['table_status'],
            "migration_required": db_status['needs_migration'],
            "schema_compatibility": {
                "legacy_v1_support": True,
                "features_available": db_status['schema_tables_exist'],
                "model_evaluators_available": db_status['table_status'].get('model_evaluators', False)
            }
        }
        
    except Exception as e:
        logger.error(f"Failed to get database status: {e}")
        return {
            "success": False,
            "error": str(e),
            "database_path": get_database_path(),
            "current_version": "unknown",
            "target_version": CURRENT_SCHEMA_VERSION,
            "schema_up_to_date": False,
            "schema_available": False
        }