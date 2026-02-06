"""Simple SQLite migration utilities for Lust Rentals data stores."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Tuple

Migration = Tuple[int, str]


def apply_migrations(db_path: Path, migrations: Iterable[Migration]) -> None:
    """Apply ordered migrations to a SQLite database.

    Args:
        db_path: Target database file.
        migrations: Iterable of (version, sql_script) pairs. Scripts are executed
            when a higher version than the current schema_version is encountered.
    """

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_version (\n"
            "    version INTEGER PRIMARY KEY,\n"
            "    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP\n"
            ")"
        )

        row = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
        current_version = row[0] or 0

        for version, sql in sorted(migrations, key=lambda item: item[0]):
            if version <= current_version:
                continue
            with conn:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version) VALUES (?)",
                    (version,),
                )
