"""Memory Service - simple persistent memory storage and semantic-like search (fallback)

This service provides:
- store_memory(user_id, content, metadata)
- search_memory(query, user_id=None, top_k=5)

Current implementation uses SQLite for persistence and simple text-similarity (difflib).
If a vector DB and embedding provider are configured later, this file can be extended to
use vector similarity search instead.
"""

import sqlite3
import json
import time
import asyncio
from typing import List, Dict, Any, Optional
from difflib import SequenceMatcher
from pathlib import Path
from loguru import logger

DB_PATH = Path(__file__).resolve().parents[2] / "data" / "memories.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

CREATE_SQL = """
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT,
    content TEXT NOT NULL,
    metadata TEXT,
    created_at INTEGER
)
"""


class MemoryService:
    def __init__(self):
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(DB_PATH)
        try:
            conn.execute(CREATE_SQL)
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize memory DB: {e}")
        finally:
            conn.close()

    async def store_memory(self, user_id: Optional[str], content: str, metadata: Optional[Dict[str, Any]] = None):
        """Persist a memory (non-blocking)"""
        timestamp = int(time.time())
        meta_json = json.dumps(metadata or {})

        def _write():
            conn = sqlite3.connect(DB_PATH)
            try:
                conn.execute(
                    "INSERT INTO memories (user_id, content, metadata, created_at) VALUES (?, ?, ?, ?)",
                    (user_id, content, meta_json, timestamp)
                )
                conn.commit()
            except Exception as e:
                logger.error(f"Failed to store memory: {e}")
            finally:
                conn.close()
        await asyncio.to_thread(_write)

    async def _fetch_all(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        def _read():
            conn = sqlite3.connect(DB_PATH)
            try:
                if user_id:
                    cur = conn.execute(
                        "SELECT id, user_id, content, metadata, created_at FROM memories WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
                else:
                    cur = conn.execute(
                        "SELECT id, user_id, content, metadata, created_at FROM memories ORDER BY created_at DESC")
                rows = cur.fetchall()
                return [
                    {"id": r[0], "user_id": r[1], "content": r[2], "metadata": json.loads(r[3] or "{}"), "created_at": r[4]} for r in rows
                ]
            except Exception as e:
                logger.error(f"Failed to fetch memories: {e}")
                return []
            finally:
                conn.close()
        return await asyncio.to_thread(_read)

    async def search_memory(self, query: str, user_id: Optional[str] = None, top_k: int = 5) -> List[Dict[str, Any]]:
        """Search memories using simple similarity fallback (difflib). Returns list of {id, user_id, content, metadata, score}"""
        all_mem = await self._fetch_all(user_id)
        scores = []
        for m in all_mem:
            score = SequenceMatcher(None, query, m["content"]).ratio()
            scores.append((m, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        results = []
        for m, s in scores[:top_k]:
            results.append({"id": m["id"], "user_id": m["user_id"],
                           "content": m["content"], "metadata": m["metadata"], "score": s})
        return results


# Singleton
memory_service = MemoryService()
