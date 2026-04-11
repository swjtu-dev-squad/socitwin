"""
Database Initialization - Create indexes for OASIS metrics optimization

This module provides database initialization utilities for creating
indexes that optimize metrics calculation queries.
"""

import logging
import sqlite3
import os
from pathlib import Path
from typing import Dict


logger = logging.getLogger(__name__)


# SQL statements to create indexes for metrics optimization
METRICS_INDEXES = [
    # Propagation query optimization
    """
    -- 传播查询优化
    -- 这些索引加速信息传播指标的递归CTE查询
    """,
    "CREATE INDEX IF NOT EXISTS idx_post_original ON post(original_post_id);",
    "CREATE INDEX IF NOT EXISTS idx_post_user ON post(user_id);",
    "CREATE INDEX IF NOT EXISTS idx_post_created ON post(created_at);",

    # Engagement query optimization
    """
    -- 互动查询优化
    -- 这些索引加速羊群效应指标的参与度查询
    """,
    "CREATE INDEX IF NOT EXISTS idx_post_engagement ON post(num_likes, num_dislikes, created_at);",

    # Social network query optimization
    """
    -- 社交网络查询优化
    -- 这些索引加速关注关系的网络分析
    """,
    "CREATE INDEX IF NOT EXISTS idx_follow_follower ON follow(follower_id);",
    "CREATE INDEX IF NOT EXISTS idx_follow_followee ON follow(followee_id);",

    # Composite index for time-series queries
    "CREATE INDEX IF NOT EXISTS idx_post_time_user ON post(created_at, user_id);",
]


def create_indexes_for_database(db_path: str) -> bool:
    """
    Create indexes for a specific OASIS database

    Args:
        db_path: Path to SQLite database file

    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return False

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()

            logger.info(f"Creating indexes for database: {db_path}")

            for index_sql in METRICS_INDEXES:
                if index_sql.strip() and not index_sql.startswith('"""'):
                    # Execute index creation
                    cursor.execute(index_sql)
                    logger.debug(f"Executed: {index_sql[:80]}...")

            conn.commit()
            logger.info("Successfully created all metrics indexes")

        return True

    except sqlite3.Error as e:
        logger.error(f"Failed to create indexes: {e}")
        return False

    except Exception as e:
        logger.error(f"Unexpected error creating indexes: {e}")
        return False


def ensure_oasis_databases_have_indexes(
    db_directory: str = "./data/simulations"
) -> Dict[str, bool]:
    """
    Ensure all OASIS databases have required indexes

    Args:
        db_directory: Directory containing OASIS database files

    Returns:
        Dict mapping database filename to success status
    """
    results = {}

    if not os.path.exists(db_directory):
        logger.warning(f"Database directory not found: {db_directory}")
        return results

    # Find all .db files
    db_files = list(Path(db_directory).glob("*.db"))

    if not db_files:
        logger.info(f"No database files found in {db_directory}")
        return results

    logger.info(f"Found {len(db_files)} database files to index")

    for db_file in db_files:
        db_path = str(db_file)
        logger.info(f"Processing {db_file.name}")

        results[db_file.name] = create_indexes_for_database(db_path)

    success_count = sum(1 for status in results.values() if status)
    logger.info(f"Index creation complete: {success_count}/{len(results)} succeeded")

    return results


def main():
    """
    Main entry point for standalone execution

    Usage:
        python -m app.utils.db_init
    """
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # Get database directory from settings
    from app.core.config import get_settings
    settings = get_settings()

    db_directory = settings.OASIS_DB_PATH
    logger.info(f"Ensuring indexes for databases in: {db_directory}")

    results = ensure_oasis_databases_have_indexes(db_directory)

    # Print summary
    print("\n" + "="*60)
    print("Database Index Creation Summary")
    print("="*60)

    for db_name, success in results.items():
        status = "✓ Success" if success else "✗ Failed"
        print(f"{status}: {db_name}")

    print("="*60)

    # Exit with appropriate code
    sys.exit(0 if all(results.values()) else 1)


if __name__ == "__main__":
    main()
