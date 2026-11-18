"""
Hybrid memory system:
- Conversation history (JSON, atomic writes, corrupt file backed up)
- Semantic vector memory (ChromaDB + embeddings) when installed:
  pip install -e ".[vector]"  — otherwise basic in-memory notes are used
"""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

try:
    import chromadb
    _VECTOR_AVAILABLE = True
except ImportError:
    _VECTOR_AVAILABLE = False

from ai_jarvis.config.settings import VECTOR_MEMORY_ENABLED

COLLECTION_NAME = "jarvis_memory"
MAX_HISTORY = 500

# Words that carry no recall signal in a natural-language question.
_STOPWORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been",
    "do", "does", "did", "i", "me", "my", "you", "your", "it", "its",
    "to", "of", "for", "in", "on", "at", "with", "about", "from",
    "what", "who", "when", "where", "why", "how", "which", "tell",
    "please", "that", "this", "have", "has", "had",
})


def _tokens(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z0-9]+", text.lower())
        if word not in _STOPWORDS
    }


class MemorySystem:
    """Hybrid memory: vector store for facts + JSON for conversation history."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.data_dir / "conversation.json"
        self.archive_file = self.data_dir / "conversation.archive.json"
        self.chroma_dir = self.data_dir / "chroma_db"
        self._history: list[dict] = self._load_history()

        self._client = None
        self._collection = None
        self._fallback_notes: list[str] = []
        if VECTOR_MEMORY_ENABLED and _VECTOR_AVAILABLE:
            self._init_vector()

    def _init_vector(self):
        try:
            self.chroma_dir.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(path=str(self.chroma_dir))
            self._collection = self._client.get_or_create_collection(COLLECTION_NAME)
            # ChromaDB supplies its own default embeddings; no extra model
            # download or embedding library is needed.
            print("[Memory] Vector store initialized (ChromaDB)")
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
            # Never silently drop history — move the corrupt file aside with a
            # unique name so a later corruption cannot overwrite an older copy.
            # Windows clock resolution is ~15ms, so a timestamp alone can
            # collide for two rapid failures — add a UUID to stay unique.
            stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
            unique = f"{stamp}-{uuid.uuid4().hex[:8]}"
            backup = self.history_file.with_name(
                f"{self.history_file.stem}.corrupt.{unique}.bak"
            )
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
        if len(self._history) > MAX_HISTORY:
            self._archive_history(self._history[:-MAX_HISTORY])
            self._history = self._history[-MAX_HISTORY:]
        self.save_history()

    def _archive_history(self, entries: list[dict]) -> None:
        """Persist messages rotated out of the active history."""
        archived = []
        if self.archive_file.exists():
            try:
                data = json.loads(self.archive_file.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    archived = data
            except Exception:
                stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
                unique = f"{stamp}-{uuid.uuid4().hex[:8]}"
                corrupt = self.archive_file.with_name(
                    f"{self.archive_file.stem}.corrupt.{unique}.bak"
                )
                os.replace(self.archive_file, corrupt)
        archived.extend(entries)
        tmp = self.archive_file.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(archived, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        os.replace(tmp, self.archive_file)

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
        query_tokens = _tokens(query)
        if not query_tokens:
            return ["No relevant memories found."]

        scored: list[tuple[int, int, str]] = []
        for index, note in enumerate(self._fallback_notes):
            if query_lower in note.lower():
                score = 100 + len(query_tokens)   # exact phrase wins
            else:
                score = len(query_tokens & _tokens(note))
            if score:
                scored.append((score, index, note))
        scored.sort(key=lambda item: (-item[0], item[1]))
        return [note for _, _, note in scored[:n]] or ["No relevant memories found."]

    def forget_all(self) -> str | None:
        """Erase everything, including the on-disk vector database.

        Returns None on full success, or an error string if the vector store
        could not be wiped. Conversation history is cleared either way.
        """
        self._fallback_notes = []
        self._history = []
        self.save_history()
        if self.archive_file.exists():
            self.archive_file.unlink()

        vector_error = None
        if self._client is not None or self.chroma_dir.exists():
            close = getattr(self._client, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
            self._client = None
            self._collection = None
            try:
                shutil.rmtree(self.chroma_dir)
            except OSError as e:
                vector_error = f"vector store could not be erased ({e})"

        if VECTOR_MEMORY_ENABLED and _VECTOR_AVAILABLE:
            self._init_vector()   # recreate an empty store for continued use
        return vector_error

    def get_stats(self) -> dict:
        return {
            "total_messages": len(self._history),
            "vector_memory": "online" if self._collection else "offline",
        }
