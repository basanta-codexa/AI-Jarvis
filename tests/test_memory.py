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
    # Rotated-out messages are preserved, not silently erased.
    archived = json.loads(memory.archive_file.read_text(encoding="utf-8"))
    assert len(archived) == 5
    assert archived[0]["content"] == "message 0"
    assert archived[-1]["content"] == "message 4"


def test_fallback_memory_can_recall_and_forget(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    memory.remember("My favorite tea is jasmine.")
    memory.remember("I prefer quiet mornings.")

    assert memory.recall("jasmine") == ["My favorite tea is jasmine."]
    assert memory.recall("coffee") == ["No relevant memories found."]

    memory.forget_all()

    assert memory.recall("jasmine") == ["No relevant memories found."]
    assert memory.get_all_history() == []


def test_forget_all_also_removes_archive(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    for index in range(502):
        memory.add_message("user", f"message {index}")
    assert memory.archive_file.exists()

    memory.forget_all()

    assert not memory.archive_file.exists()
    assert memory.get_all_history() == []


def test_fallback_recall_matches_rephrased_question(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    memory.remember("My favourite tea is jasmine.")

    assert memory.recall("what tea do I like?") == ["My favourite tea is jasmine."]


def test_fallback_recall_ranks_by_token_overlap(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    memory.remember("I drive a blue car.")
    memory.remember("My blue car needs new tires.")

    results = memory.recall("blue car tires")

    assert results[0] == "My blue car needs new tires."


def test_fallback_recall_ignores_stopword_only_query(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    memory.remember("I like tea.")

    assert memory.recall("what is it?") == ["No relevant memories found."]


def test_fallback_recall_respects_result_limit(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    for note in ("tea one", "tea two", "tea three"):
        memory.remember(note)

    assert len(memory.recall("tea", n=2)) == 2
