"""
Hybrid memory system:
- Conversation history (JSON, atomic writes, corrupt file backed up)
- Semantic vector memory (ChromaDB + embeddings) when installed:
  pip install -e ".[vector]"  — otherwise basic in-memory notes are used
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    _VECTOR_AVAILABLE = True
except ImportError:
    _VECTOR_AVAILABLE = False

from ai_jarvis.config.settings import VECTOR_MEMORY_ENABLED

COLLECTION_NAME = "jarvis_memory"


class MemorySystem:
    """Hybrid memory: vector store for facts + JSON for conversation history."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "conversation.json"
        self.chroma_dir = self.data_dir / "chroma_db"
        self._history: list[dict] = self._load_history()

        self._client = None
        self._collection = None
        self._embedder = None
        self._fallback_notes: list[str] = []
        if VECTOR_MEMORY_ENABLED and _VECTOR_AVAILABLE:
            self._init_vector()

    def _init_vector(self):
        try:
            self.chroma_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
            self._collection = self._client.get_or_create_collection(COLLECTION_NAME)
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            print("[Memory] Vector store initialized (ChromaDB + embeddings)")
        except Exception as e:
            print(f"[Memory] Vector init failed: {e}")
            self._collection = None
            self._client = None

    # ── Conversation history ────────────────────────────────────────

    def _load_history(self) -> list[dict]:
        if not self.history_file.exists():
            return []
        try:
            data = json.loads(self.history_file.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            # Never silently drop history — move the corrupt file aside
            backup = self.history_file.with_suffix(".corrupt.bak")
            try:
                os.replace(self.history_file, backup)
                print(f"[Memory] History file was corrupt; saved as {backup.name}")
            except OSError:
                print("[Memory] History file was corrupt and could not be backed up")
            return []

    def save_history(self):
        tmp = self.history_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(self._history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        os.replace(tmp, self.history_file)     # atomic on same filesystem

    def add_message(self, role: str, content: str):
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        self._history.append(entry)
        self._history = self._history[-500:]   # Cap at 500 messages
        self.save_history()

    def get_recent(self, n: int = 10) -> list[dict]:
        return self._history[-n:]

    def get_all_history(self) -> list[dict]:
        return self._history

    # ── Semantic memory (RAG) ──────────────────────────────────────

    def remember(self, text: str, metadata: dict | None = None) -> str:
        """Store a fact in vector memory (or fallback list)."""
        if self._collection:
            mem_id = str(uuid.uuid4())
            self._collection.add(
                documents=[text],
                metadatas=[metadata or {"timestamp": datetime.now().isoformat()}],
                ids=[mem_id],
            )
            return f"Locked into memory: {text[:60]}"
        self._fallback_notes.append(text)
        return f"Noted: {text[:60]}"

    def recall(self, query: str, n: int = 5) -> list[str]:
        """Semantically search memory for relevant facts."""
        if self._collection:
            results = self._collection.query(
                query_texts=[query],
                n_results=n,
                include=["documents", "metadatas"],
            )
            docs = results.get("documents", [[]])[0]
            return docs if docs else ["No relevant memories found."]
        query_lower = query.lower()
        matches = [note for note in self._fallback_notes if query_lower in note.lower()]
        return matches if matches else ["No relevant memories found."]

    def forget_all(self) -> str | None:
        """Erase everything.

        Returns None on full success, or an error string if the vector
        store could not be wiped (history is cleared either way).
        """
        vector_error = None
        if self._client is not None:
            try:
                # ChromaDB rejects delete(where={}) — delete and recreate instead
                self._client.delete_collection(COLLECTION_NAME)
                self._collection = self._client.get_or_create_collection(COLLECTION_NAME)
            except Exception as e:
                vector_error = f"vector store could not be reset ({e})"
        self._fallback_notes = []
        self._history = []
        self.save_history()
        return vector_error

    def get_stats(self) -> dict:
        return {
            "total_messages": len(self._history),
            "vector_memory": "online" if self._collection else "offline",
        }
