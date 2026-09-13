import sqlite3
import datetime
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class BaseMemory(ABC):
    """
    Abstract Interface for Lisa's Memory Storage.
    Designed so it can seamlessly swap between SQLite, JSON, or Vector DBs (Chroma/Pinecone).
    """

    @abstractmethod
    def add_interaction(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Store a single turn in conversation memory."""
        pass

    @abstractmethod
    def get_recent_context(self, limit: int = 10) -> List[Dict[str, str]]:
        """Retrieve recent conversation turns for LLM prompt context."""
        pass

    @abstractmethod
    def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Search memory for relevant facts (semantic recall hook for Chroma)."""
        pass

    @abstractmethod
    def clear_memory(self) -> None:
        """Clear stored conversation history."""
        pass


class SQLiteMemory(BaseMemory):
    """
    Persistent SQLite storage for Lisa's conversations.
    Retains context across restarts and sessions.
    """
    def __init__(self, db_path: str = "lisa_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL
                )
            """)
            conn.commit()

    def add_interaction(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO interactions (timestamp, role, content)
                VALUES (?, ?, ?)
            """, (now, role, content))
            conn.commit()

    def get_recent_context(self, limit: int = 10) -> List[Dict[str, str]]:
        """
        Fetches the last `limit` messages in chronological order.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT role, content FROM (
                    SELECT id, role, content FROM interactions
                    ORDER BY id DESC
                    LIMIT ?
                ) ORDER BY id ASC
            """, (limit,))
            rows = cursor.fetchall()
            return [{"role": row[0], "content": row[1]} for row in rows]

    def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Keyword search for SQLite; in Chroma implementation, this will perform semantic cosine search.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, role, content FROM interactions
                WHERE content LIKE ?
                ORDER BY id DESC
                LIMIT ?
            """, (f"%{query}%", limit))
            rows = cursor.fetchall()
            return [{"timestamp": r[0], "role": r[1], "content": r[2]} for r in rows]

    def clear_memory(self) -> None:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM interactions")
            conn.commit()


class ChromaVectorMemory(BaseMemory):
    """
    Vector Database implementation placeholder for Chroma.
    Allows semantic recall without changing any calling code.
    """
    def __init__(self, collection_name: str = "lisa_memory"):
        self.collection_name = collection_name
        # Fallback to SQLite until Chroma is installed/enabled
        self.fallback = SQLiteMemory()

    def add_interaction(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        self.fallback.add_interaction(role, content, metadata)

    def get_recent_context(self, limit: int = 10) -> List[Dict[str, str]]:
        return self.fallback.get_recent_context(limit)

    def search_memory(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        return self.fallback.search_memory(query, limit)

    def clear_memory(self) -> None:
        self.fallback.clear_memory()


def get_memory_manager(backend: str = "sqlite") -> BaseMemory:
    """Factory to retrieve memory storage manager."""
    if backend.lower() == "sqlite":
        return SQLiteMemory()
    elif backend.lower() == "chroma":
        return ChromaVectorMemory()
    return SQLiteMemory()
