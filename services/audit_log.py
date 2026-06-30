"""
Audit Log Service
==================
Write-once SQLite audit log for all compliance pipeline actions.
Records every agent action, routing decision, and validation result.
"""

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path(__file__).parent.parent / "data" / "audit_log.db"


class AuditLogService:
    """
    Immutable audit log backed by SQLite.
    All compliance pipeline actions are recorded here for RBI inspection readiness.
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = str(db_path or DB_PATH)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create audit log table if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    pipeline_run_id TEXT NOT NULL,
                    agent TEXT NOT NULL,
                    action TEXT NOT NULL,
                    map_id TEXT,
                    department TEXT,
                    ticket_id TEXT,
                    details TEXT,
                    status TEXT NOT NULL DEFAULT 'SUCCESS'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_run_id ON audit_log(pipeline_run_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_map_id ON audit_log(map_id)
            """)
            conn.commit()

    def log(
        self,
        pipeline_run_id: str,
        agent: str,
        action: str,
        map_id: str = "",
        department: str = "",
        ticket_id: str = "",
        details: dict = None,
        status: str = "SUCCESS",
    ):
        """Write an immutable audit log entry."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO audit_log 
                   (timestamp, pipeline_run_id, agent, action, map_id, department, 
                    ticket_id, details, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.utcnow().isoformat() + "Z",
                    pipeline_run_id,
                    agent,
                    action,
                    map_id,
                    department,
                    ticket_id,
                    json.dumps(details or {}),
                    status,
                ),
            )
            conn.commit()
        logger.info("Audit: [%s] %s - %s (map=%s)", agent, action, status, map_id)

    def get_logs(
        self, pipeline_run_id: Optional[str] = None, map_id: Optional[str] = None
    ) -> list[dict]:
        """Query audit logs with optional filters."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM audit_log WHERE 1=1"
            params = []
            if pipeline_run_id:
                query += " AND pipeline_run_id = ?"
                params.append(pipeline_run_id)
            if map_id:
                query += " AND map_id = ?"
                params.append(map_id)
            query += " ORDER BY timestamp DESC"

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]
