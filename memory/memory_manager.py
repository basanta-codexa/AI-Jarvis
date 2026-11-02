# ──────────────────────────────────────────────
#  memory/memory_manager.py  –  Persistent memory
# ──────────────────────────────────────────────
"""
Stores conversation history and user notes as JSON.
Auto-creates the data/ directory if it doesn't exist.
"""
import json
from datetime import datetime
from pathlib import Path
from config import settings


class MemoryManager:
    """Persist conversation history and user notes to disk."""

    def __init__(self):
        self._path = Path(settings.MEMORY_FILE)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data = self._load()

    # ── Conversation history ──────────────────────────────────────────

    def add_message(self, role: str, content: str) -> None:
        """Append a message to the conversation history."""
        self._data["history"].append({
            "role":      role,
            "content":   content,
            "timestamp": datetime.now().isoformat(),
        })
        # Keep last 200 messages to avoid unbounded growth
        self._data["history"] = self._data["history"][-200:]
        self._save()

    def get_recent(self, n: int = 10) -> list[dict]:
        """Return the last n messages from history."""
        return self._data["history"][-n:]

    def get_all_history(self) -> list[dict]:
        """Return full conversation history."""
        return self._data["history"]

    # ── User notes ────────────────────────────────────────────────────

    def save_note(self, note: str) -> None:
        """Save a user note."""
        self._data["notes"].append({
            "text":      note,
            "timestamp": datetime.now().isoformat(),
        })
        self._save()

    def get_notes(self) -> list[str]:
        """Return all saved note texts."""
        return [n["text"] for n in self._data["notes"]]

    def clear_notes(self) -> None:
        """Delete all saved notes."""
        self._data["notes"] = []
        self._save()

    # ── Preferences ───────────────────────────────────────────────────

    def set_preference(self, key: str, value) -> None:
        self._data["preferences"][key] = value
        self._save()

    def get_preference(self, key: str, default=None):
        return self._data["preferences"].get(key, default)

    # ── Stats ─────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "total_messages": len(self._data["history"]),
            "total_notes":    len(self._data["notes"]),
        }

    # ── Internal ──────────────────────────────────────────────────────

    def _load(self) -> dict:
        if self._path.exists():
            try:
                with open(self._path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        return {"history": [], "notes": [], "preferences": {}}

    def _save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
