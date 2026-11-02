import json

from ai_jarvis.core import memory as memory_module
from ai_jarvis.core.memory import MemorySystem


def make_memory(monkeypatch, tmp_path):
    monkeypatch.setattr(memory_module, "_VECTOR_AVAILABLE", False)
    monkeypatch.setattr(memory_module, "VECTOR_MEMORY_ENABLED", False)
    return MemorySystem(tmp_path)


def test_conversation_history_persists_and_is_capped(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)

    for index in range(505):
        memory.add_message("user", f"message {index}")

    assert len(memory.get_all_history()) == 500
    assert memory.get_recent(1)[0]["content"] == "message 504"
    assert json.loads(memory.history_file.read_text(encoding="utf-8")) == (
        memory.get_all_history()
    )


def test_fallback_memory_can_recall_and_forget(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    memory.remember("My favorite tea is jasmine.")
    memory.remember("I prefer quiet mornings.")

    assert memory.recall("jasmine") == ["My favorite tea is jasmine."]
    assert memory.recall("coffee") == ["No relevant memories found."]

    memory.forget_all()

    assert memory.recall("jasmine") == ["No relevant memories found."]
    assert memory.get_all_history() == []
