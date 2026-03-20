"""
Migration script for OASIS paper metrics tables.

This script adds the necessary database tables for implementing
the three metrics defined in the OASIS paper:
1. Information Propagation (propagation_cache)
2. Group Polarization (polarization_baseline, polarization_comparison)
3. Herd Effect (uses existing metrics_cache with new metric_type)

Usage:
    python -m oasis_dashboard.migrations.add_oasis_metrics_tables
    or
    OASIS_DB_PATH=/path/to/database.db python -m oasis_dashboard.migrations.add_oasis_metrics_tables
"""

from __future__ import annotations

import argparse
import logging
import os
import sqlite3
import sys
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logger = logging.getLogger(__name__)


def migrate(db_path: str, dry_run: bool = False) -> bool:
    """
    Add OASIS metrics tables to the database.

    Args:
        db_path: Path to the SQLite database file
        dry_run: If True, print SQL without executing

    Returns:
        True if migration succeeded, False otherwise
    """
    if not os.path.exists(db_path):
        logger.error(f"Database not found: {db_path}")
        return False

    logger.info(f"{'[DRY RUN] ' if dry_run else ''}Migrating database: {db_path}")

    # SQL statements for table creation
    sql_statements = [
        # 1. Propagation cache table
        """
        CREATE TABLE IF NOT EXISTS propagation_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_number INTEGER NOT NULL,
            scale INTEGER NOT NULL,
            depth INTEGER NOT NULL,
            max_breadth INTEGER NOT NULL,
            nrmse REAL,
            graph_summary TEXT,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(round_number)
        )
        """,
        # Index for propagation_cache
        """
        CREATE INDEX IF NOT EXISTS idx_propagation_round
        ON propagation_cache(round_number)
        """,
        # 2. Polarization baseline table
        """
        CREATE TABLE IF NOT EXISTS polarization_baseline (
            round_number INTEGER PRIMARY KEY,
            baseline_data TEXT NOT NULL,
            saved_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """,
        # 3. Polarization comparison table
        """
        CREATE TABLE IF NOT EXISTS polarization_comparison (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_n INTEGER NOT NULL,
            comparison_result TEXT NOT NULL,
            computed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(round_n)
        )
        """,
        # Index for polarization_comparison
        """
        CREATE INDEX IF NOT EXISTS idx_polarization_comparison_round
        ON polarization_comparison(round_n)
        """,
    ]

    if dry_run:
        for i, sql in enumerate(sql_statements, 1):
            print(f"\n-- SQL Statement {i}:")
            print(sql.strip())
        print("\n[DRY RUN] No changes were made.")
        return True

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Enable WAL mode for better concurrent access
        cursor.execute("PRAGMA journal_mode=WAL")

        # Execute each SQL statement
        for sql in sql_statements:
            cursor.execute(sql)

        conn.commit()
        conn.close()

        logger.info("✅ Migration completed successfully")
        logger.info("Created tables:")
        logger.info("  - propagation_cache")
        logger.info("  - polarization_baseline")
        logger.info("  - polarization_comparison")

        return True

    except sqlite3.Error as e:
        logger.error(f"❌ Migration failed: {e}")
        return False


def verify_tables(db_path: str) -> bool:
    """
    Verify that the new tables exist.

    Args:
        db_path: Path to the SQLite database file

    Returns:
        True if all tables exist, False otherwise
    """
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
            AND name IN ('propagation_cache', 'polarization_baseline', 'polarization_comparison')
        """)

        tables = {row[0] for row in cursor.fetchall()}
        conn.close()

        expected = {'propagation_cache', 'polarization_baseline', 'polarization_comparison'}
        missing = expected - tables

        if missing:
            logger.warning(f"Missing tables: {missing}")
            return False

        logger.info("✅ All tables verified")
        return True

    except sqlite3.Error as e:
        logger.error(f"❌ Verification failed: {e}")
        return False


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Migrate OASIS Dashboard database for paper metrics"
    )
    parser.add_argument(
        "--db-path",
        default=os.environ.get("OASIS_DB_PATH", "./oasis_simulation.db"),
        help="Path to the SQLite database file (default: ./oasis_simulation.db or OASIS_DB_PATH env var)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print SQL statements without executing them"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify that tables exist after migration"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s"
    )

    # Run migration
    success = migrate(args.db_path, dry_run=args.dry_run)

    if not success:
        return 1

    # Verify if requested
    if args.verify and not args.dry_run:
        if not verify_tables(args.db_path):
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
