"""
Hybrid memory system:
- Conversation history (JSON)
- Semantic vector memory (ChromaDB + embeddings) for RAG-style recall
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

try:
    import chromadb
    from sentence_transformers import SentenceTransformer
    _VECTOR_AVAILABLE = True
except ImportError:
    _VECTOR_AVAILABLE = False

from ai_jarvis.config.settings import MEMORY_FILE, CHROMA_DIR, VECTOR_MEMORY_ENABLED


class MemorySystem:
    """Hybrid memory: vector store for facts + JSON for conversation history."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "conversation.json"
        self._history: list[dict] = self._load_history()

        self._collection = None
        self._embedder = None
        self._fallback_notes: list[str] = []
        if VECTOR_MEMORY_ENABLED and _VECTOR_AVAILABLE:
            self._init_vector()

    def _init_vector(self):
        try:
            CHROMA_DIR.mkdir(parents=True, exist_ok=True)
            client = chromadb.PersistentClient(path=str(CHROMA_DIR))
            self._collection = client.get_or_create_collection(
                name="jarvis_memory"
            )
            self._embedder = SentenceTransformer("all-MiniLM-L6-v2")
            print("[Memory] Vector store initialized (ChromaDB + embeddings)")
        except Exception as e:
            print(f"[Memory] Vector init failed: {e}")
            self._collection = None

    # ── Conversation history ────────────────────────────────────────

    def _load_history(self) -> list[dict]:
        if self.history_file.exists():
            try:
                return json.loads(self.history_file.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def save_history(self):
        self.history_file.write_text(
            json.dumps(self._history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def add_message(self, role: str, content: str):
        entry = {
            "role": role,
            "content": content,
            "timestamp": datetime.now().isoformat(),
        }
        self._history.append(entry)
        self._history = self._history[-500:]  # Cap at 500 messages
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
            return f"Locked into memory: {text[:60]}..."
        # Fallback: store in simple list
        self._fallback_notes.append(text)
        return f"Noted: {text[:60]}..."

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
        # Fallback: simple text match
        query_lower = query.lower()
        matches = [n for n in self._fallback_notes if query_lower in n.lower()]
        return matches if matches else ["No relevant memories found."]

    def forget_all(self):
        """Clear all memory."""
        if self._collection:
            try:
                self._collection.delete(where={})
            except Exception:
                pass
        self._fallback_notes = []
        self._history = []
        self.save_history()

    def get_stats(self) -> dict:
        return {
            "total_messages": len(self._history),
            "vector_memory": "online" if self._collection else "offline",
        }
