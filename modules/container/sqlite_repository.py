from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from .repository import ContainerRepository


class SQLiteContainerRepository(ContainerRepository):
    """Persistence adapter only; all schema evolution is runtime-migration owned."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = Path(db_path)

    @contextmanager
    def transaction(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def read(self):
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()
