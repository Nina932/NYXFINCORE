"""
Float → Decimal Migration Script
==================================
Idempotent script that adds _decimal (String) columns alongside existing
Float columns in critical financial tables. Populates them with
Decimal(str(float_value)) to preserve displayed precision.

Usage:
    cd backend
    python scripts/migrate_float_to_decimal.py

This is a NON-DESTRUCTIVE migration:
- Original Float columns are preserved for rollback
- New _decimal columns store String representations
- v2 modules can read from _decimal columns for precision
"""

import asyncio
import logging
import sys
from decimal import Decimal
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Tables and their Float columns that need Decimal equivalents
MIGRATION_TARGETS = {
    "prediction_records": ["predicted_value", "confidence"],
    "prediction_outcomes": ["actual_value", "error_pct", "magnitude_accuracy"],
    "alerts": ["threshold_value", "current_value"],
    "monitoring_rules": ["threshold"],
    "decision_actions": ["expected_impact", "implementation_cost", "roi_estimate", "composite_score"],
    "learning_records": ["confidence"],
}


async def run_migration():
    from app.database import engine
    from sqlalchemy import text

    logger.info("Starting float→Decimal migration...")

    async with engine.begin() as conn:
        for table, columns in MIGRATION_TARGETS.items():
            for col in columns:
                decimal_col = f"{col}_decimal"

                # Check if column already exists
                try:
                    await conn.execute(text(
                        f"SELECT {decimal_col} FROM {table} LIMIT 1"
                    ))
                    logger.info(f"  {table}.{decimal_col} already exists — skipping")
                    continue
                except Exception:
                    pass  # Column doesn't exist, add it

                # Add the _decimal column
                try:
                    await conn.execute(text(
                        f"ALTER TABLE {table} ADD COLUMN {decimal_col} VARCHAR(50)"
                    ))
                    logger.info(f"  Added {table}.{decimal_col}")
                except Exception as e:
                    logger.warning(f"  Failed to add {table}.{decimal_col}: {e}")
                    continue

                # Populate from existing Float values
                try:
                    rows = await conn.execute(text(
                        f"SELECT id, {col} FROM {table} WHERE {col} IS NOT NULL"
                    ))
                    count = 0
                    for row in rows:
                        float_val = row[1]
                        if float_val is not None:
                            decimal_str = str(Decimal(str(float_val)))
                            await conn.execute(text(
                                f"UPDATE {table} SET {decimal_col} = :val WHERE id = :id"
                            ), {"val": decimal_str, "id": row[0]})
                            count += 1
                    logger.info(f"  Populated {count} rows in {table}.{decimal_col}")
                except Exception as e:
                    logger.warning(f"  Failed to populate {table}.{decimal_col}: {e}")

    logger.info("Migration complete.")


if __name__ == "__main__":
    asyncio.run(run_migration())
