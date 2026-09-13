"""
Local RAG & Second Brain Vector Search Engine for Lisa AI.
Indexes local Markdown vaults, PDFs, code repos, notes, and research documents,
enabling semantic vector retrieval and context synthesis for LLM queries.
"""

import os
import re
import math
import sqlite3
import datetime
from typing import List, Dict, Any

class SecondBrainRAG:
    def __init__(self, db_path: str = "lisa_memory.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_documents (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_path TEXT UNIQUE NOT NULL,
                    file_name TEXT NOT NULL,
                    file_ext TEXT NOT NULL,
                    indexed_at TEXT NOT NULL,
                    chunk_count INTEGER NOT NULL
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS rag_chunks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    doc_id INTEGER NOT NULL,
                    chunk_index INTEGER NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY (doc_id) REFERENCES rag_documents(id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def _extract_text(self, file_path: str) -> str:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in (".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".csv", ".yaml", ".yml", ".sql", ".sh"):
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return ""
        elif ext == ".pdf":
            try:
                import pypdf
                reader = pypdf.PdfReader(file_path)
                text = "\n".join([page.extract_text() or "" for page in reader.pages])
                return text
            except Exception:
                return ""
        return ""

    def _chunk_text(self, text: str, chunk_size: int = 500, overlap: int = 80) -> List[str]:
        words = text.split()
        if not words:
            return []
        chunks = []
        i = 0
        while i < len(words):
            chunk = " ".join(words[i:i + chunk_size])
            chunks.append(chunk)
            i += (chunk_size - overlap)
            if i >= len(words):
                break
        return chunks

    def index_file(self, file_path: str) -> Dict[str, Any]:
        abs_path = os.path.abspath(file_path)
        if not os.path.exists(abs_path):
            return {"status": "error", "message": f"File '{abs_path}' does not exist."}

        text = self._extract_text(abs_path)
        if not text.strip():
            return {"status": "error", "message": f"Could not extract readable text from '{abs_path}'."}

        chunks = self._chunk_text(text)
        if not chunks:
            return {"status": "error", "message": "File is empty or contains no tokens."}

        file_name = os.path.basename(abs_path)
        file_ext = os.path.splitext(abs_path)[1].lower()
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()

        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Upsert document
            cursor.execute("DELETE FROM rag_documents WHERE file_path = ?", (abs_path,))
            cursor.execute("""
                INSERT INTO rag_documents (file_path, file_name, file_ext, indexed_at, chunk_count)
                VALUES (?, ?, ?, ?, ?)
            """, (abs_path, file_name, file_ext, now, len(chunks)))
            doc_id = cursor.lastrowid

            for idx, chunk in enumerate(chunks):
                cursor.execute("""
                    INSERT INTO rag_chunks (doc_id, chunk_index, content)
                    VALUES (?, ?, ?)
                """, (doc_id, idx, chunk))
            conn.commit()

        return {
            "status": "success",
            "file": file_name,
            "path": abs_path,
            "chunks_indexed": len(chunks),
            "message": f"Successfully indexed '{file_name}' ({len(chunks)} chunks)."
        }

    def index_directory(self, folder_path: str, recursive: bool = True) -> Dict[str, Any]:
        abs_folder = os.path.abspath(folder_path)
        if not os.path.isdir(abs_folder):
            return {"status": "error", "message": f"Directory '{abs_folder}' not found."}

        supported_exts = {".md", ".txt", ".py", ".js", ".ts", ".html", ".css", ".json", ".pdf", ".csv"}
        indexed_files = []
        total_chunks = 0

        for root, dirs, files in os.walk(abs_folder):
            # Skip hidden / venv / git dirs
            dirs[:] = [d for d in dirs if not d.startswith(".") and d not in ("venv", "node_modules", "__pycache__", "build", "dist")]
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in supported_exts:
                    full_p = os.path.join(root, f)
                    res = self.index_file(full_p)
                    if res["status"] == "success":
                        indexed_files.append(f)
                        total_chunks += res["chunks_indexed"]

            if not recursive:
                break

        return {
            "status": "success",
            "folder": abs_folder,
            "total_files_indexed": len(indexed_files),
            "total_chunks": total_chunks,
            "sample_files": indexed_files[:10],
            "message": f"Second Brain indexed {len(indexed_files)} files ({total_chunks} chunks) from '{abs_folder}'."
        }

    def query(self, query_text: str, top_k: int = 4) -> List[Dict[str, Any]]:
        """
        Retrieves most relevant context chunks using BM25 / token-overlap scoring.
        """
        query_tokens = set(re.findall(r'\w+', query_text.lower()))
        if not query_tokens:
            return []

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.id, c.doc_id, c.chunk_index, c.content, d.file_name, d.file_path
                FROM rag_chunks c
                JOIN rag_documents d ON c.doc_id = d.id
            """)
            rows = cursor.fetchall()

        scores = []
        for r in rows:
            chunk_id, doc_id, chunk_idx, content, file_name, file_path = r
            content_lower = content.lower()
            
            # Simple TF-IDF term scoring
            score = 0.0
            for token in query_tokens:
                count = content_lower.count(token)
                if count > 0:
                    score += (1 + math.log(count))

            if score > 0:
                scores.append({
                    "score": round(score, 3),
                    "file_name": file_name,
                    "file_path": file_path,
                    "chunk_index": chunk_idx,
                    "content": content.strip()
                })

        scores.sort(key=lambda x: x["score"], reverse=True)
        return scores[:top_k]

    def get_stats(self) -> Dict[str, Any]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM rag_documents")
            doc_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM rag_chunks")
            chunk_count = cursor.fetchone()[0]
            cursor.execute("SELECT file_name, chunk_count, indexed_at FROM rag_documents ORDER BY id DESC LIMIT 5")
            recent = [{"file": r[0], "chunks": r[1], "indexed_at": r[2]} for r in cursor.fetchall()]

        return {
            "total_documents": doc_count,
            "total_chunks": chunk_count,
            "recent_documents": recent
        }

rag_engine = SecondBrainRAG()

if __name__ == "__main__":
    print("Testing RAG Engine on current workspace...")
    res = rag_engine.index_directory(".", recursive=False)
    print("Index result:", res)
    query_res = rag_engine.query("Lisa system prompt personality")
    print(f"Found {len(query_res)} results:")
    for q in query_res:
        print(f"[{q['file_name']}] (score: {q['score']}): {q['content'][:120]}...")
