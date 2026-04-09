"""
FinAI — SQLite Database Backup Service
=======================================
Provides automated backup of the SQLite database with rotation.

Usage:
    from app.services.db_backup import backup_database

    # Manual backup
    backup_path = await backup_database()

    # Scheduled (called from scheduler or cron)
    backup_path = await backup_database(max_backups=7)
"""

import os
import shutil
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config import settings

logger = logging.getLogger(__name__)

BACKUP_DIR = Path("./backups")


async def backup_database(max_backups: int = 7) -> Optional[str]:
    """Create a backup of the SQLite database.

    Uses sqlite3.backup() for a consistent, hot backup that doesn't
    require stopping the server. Rotates old backups to keep disk usage bounded.

    Args:
        max_backups: Maximum number of backup files to retain (default 7).

    Returns:
        Path to the backup file, or None if backup failed.
    """
    # Extract SQLite path from DATABASE_URL
    db_url = settings.DATABASE_URL
    if "sqlite" not in db_url:
        logger.info("Database backup skipped: not using SQLite (url=%s)", db_url[:30])
        return None

    # Parse path from URL like "sqlite+aiosqlite:///./finai.db"
    db_path = db_url.split("///")[-1] if "///" in db_url else db_url.split("://")[-1]
    if not os.path.exists(db_path):
        logger.warning("Database file not found: %s", db_path)
        return None

    # Create backup directory
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    # Generate backup filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    db_name = Path(db_path).stem
    backup_filename = f"{db_name}_backup_{timestamp}.db"
    backup_path = BACKUP_DIR / backup_filename

    try:
        # Use sqlite3.backup() for consistent hot backup
        source = sqlite3.connect(db_path)
        dest = sqlite3.connect(str(backup_path))
        source.backup(dest)
        dest.close()
        source.close()

        backup_size = backup_path.stat().st_size
        logger.info(
            "Database backup created: %s (%.1f MB)",
            backup_path, backup_size / (1024 * 1024),
        )

        # Rotate old backups
        _rotate_backups(max_backups)

        return str(backup_path)

    except Exception as e:
        logger.error("Database backup failed: %s", e)
        # Clean up partial backup
        if backup_path.exists():
            try:
                backup_path.unlink()
            except OSError:
                pass
        return None


def _rotate_backups(max_backups: int) -> None:
    """Remove old backup files, keeping only the most recent `max_backups`."""
    if not BACKUP_DIR.exists():
        return

    backups = sorted(
        BACKUP_DIR.glob("*_backup_*.db"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,  # Newest first
    )

    if len(backups) > max_backups:
        for old_backup in backups[max_backups:]:
            try:
                old_backup.unlink()
                logger.debug("Removed old backup: %s", old_backup.name)
            except OSError as e:
                logger.warning("Failed to remove old backup %s: %s", old_backup.name, e)


def get_backup_status() -> dict:
    """Return backup status information for monitoring."""
    if not BACKUP_DIR.exists():
        return {"backup_dir": str(BACKUP_DIR), "backups": [], "total_size_mb": 0}

    backups = sorted(BACKUP_DIR.glob("*_backup_*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    total_size = sum(b.stat().st_size for b in backups)

    return {
        "backup_dir": str(BACKUP_DIR),
        "backup_count": len(backups),
        "total_size_mb": round(total_size / (1024 * 1024), 1),
        "latest_backup": backups[0].name if backups else None,
        "latest_backup_time": datetime.fromtimestamp(backups[0].stat().st_mtime).isoformat() if backups else None,
        "backups": [
            {
                "name": b.name,
                "size_mb": round(b.stat().st_size / (1024 * 1024), 1),
                "created": datetime.fromtimestamp(b.stat().st_mtime).isoformat(),
            }
            for b in backups[:10]
        ],
    }
