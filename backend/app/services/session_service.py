"""Session Service - persist user sessions for cross-device synchronization

Provides simple SQLite-backed storage for sessions keyed by user_id and session_id.
"""

import sqlite3
import json
import time
import asyncio
from typing import List, Dict, Any, Optional
from pathlib import Path
from loguru import logger

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "sessions.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    session_id TEXT NOT NULL,
    title TEXT,
    content TEXT,
    updated_at INTEGER,
    UNIQUE(user_id, session_id)
)
"""


class SessionService:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(CREATE_SQL)
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize session DB: {e}")
        finally:
            conn.close()

    async def save_session(self, user_id: str, session: Dict[str, Any]):
        """Save or update a session for a user"""
        sid = session.get("id") or str(int(time.time()))
        title = session.get("title", "")
        content = json.dumps(session)
        updated_at = int(time.time())

        def _write():
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute(
                    "INSERT INTO sessions (user_id, session_id, title, content, updated_at) VALUES (?, ?, ?, ?, ?) ON CONFLICT(user_id, session_id) DO UPDATE SET title=excluded.title, content=excluded.content, updated_at=excluded.updated_at",
                    (user_id, sid, title, content, updated_at)
                )
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to save session: {e}")
            finally:
                conn.close()
        await asyncio.to_thread(_write)
        return sid

    async def list_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        def _read():
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.execute(
                    "SELECT session_id, title, content, updated_at FROM sessions WHERE user_id = ? ORDER BY updated_at DESC", (user_id,))
                rows = cur.fetchall()
                return [{"session_id": r[0], "title": r[1], "session": json.loads(r[2]), "updated_at": r[3]} for r in rows]
            except Exception as e:
                logger.error(f"Failed to list sessions: {e}")
                return []
            finally:
                conn.close()
        return await asyncio.to_thread(_read)

    async def get_session(self, user_id: str, session_id: str) -> Optional[Dict[str, Any]]:
        def _read():
            conn = sqlite3.connect(DB_PATH)
            try:
                cur = conn.execute(
                    "SELECT content FROM sessions WHERE user_id = ? AND session_id = ?", (user_id, session_id))
                row = cur.fetchone()
                if row:
                    return json.loads(row[0])
                return None
            except Exception as e:
                logger.error(f"Failed to get session: {e}")
                return None
            finally:
                conn.close()
        return await asyncio.to_thread(_read)

    async def delete_session(self, user_id: str, session_id: str):
        def _del():
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute(
                    "DELETE FROM sessions WHERE user_id = ? AND session_id = ?", (user_id, session_id))
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to delete session: {e}")
            finally:
                conn.close()
        await asyncio.to_thread(_del)


# Singleton
session_service = SessionService()
