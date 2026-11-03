"""Tests for conversation durability and honest 'forget everything' behaviour."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import Mock

from ai_jarvis.core import memory as memory_module
from ai_jarvis.core.memory import MemorySystem
from ai_jarvis.skills.memory import MemorySkill


def make_memory(monkeypatch, tmp_path, vector=False, client_cls=None):
    monkeypatch.setattr(memory_module, "_VECTOR_AVAILABLE", vector)
    monkeypatch.setattr(memory_module, "VECTOR_MEMORY_ENABLED", vector)
    if vector:
        monkeypatch.setattr(
            memory_module, "chromadb",
            SimpleNamespace(PersistentClient=lambda path: client_cls()),
            raising=False,
        )
        monkeypatch.setattr(
            memory_module, "SentenceTransformer", lambda name: object(), raising=False,
        )
    return MemorySystem(tmp_path)


def test_corrupt_history_is_backed_up_not_erased(monkeypatch, tmp_path):
    history = tmp_path / "conversation.json"
    history.write_text("{ not valid json", encoding="utf-8")

    memory = make_memory(monkeypatch, tmp_path)

    assert memory.get_all_history() == []
    backup = tmp_path / "conversation.corrupt.bak"
    assert backup.exists()
    assert backup.read_text(encoding="utf-8") == "{ not valid json"


def test_save_history_leaves_no_tmp_file(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    memory.add_message("user", "hello")

    assert not (tmp_path / "conversation.tmp").exists()
    assert json.loads((tmp_path / "conversation.json").read_text(encoding="utf-8")) == \
        memory.get_all_history()


def test_forget_all_recreates_vector_collection(monkeypatch, tmp_path):
    calls = []

    class FakeClient:
        def delete_collection(self, name):
            calls.append(("delete", name))

        def get_or_create_collection(self, name):
            calls.append(("create", name))
            return "COLLECTION"

    memory = make_memory(monkeypatch, tmp_path, vector=True, client_cls=FakeClient)
    memory.add_message("user", "remember the milk")

    error = memory.forget_all()

    assert error is None
    assert ("delete", "jarvis_memory") in calls
    assert ("create", "jarvis_memory") in calls
    assert memory._collection == "COLLECTION"
    assert memory.get_all_history() == []


def test_forget_all_reports_vector_failure(monkeypatch, tmp_path):
    class BadClient:
        def delete_collection(self, name):
            raise RuntimeError("collection is locked")

        def get_or_create_collection(self, name):
            return "COLLECTION"

    memory = make_memory(monkeypatch, tmp_path, vector=True, client_cls=BadClient)
    memory.add_message("user", "secret fact")

    error = memory.forget_all()

    assert error is not None
    assert "collection is locked" in error
    assert memory.get_all_history() == []          # history still cleared


def test_memory_skill_tells_the_truth_when_vector_reset_fails():
    memory = SimpleNamespace(
        forget_all=Mock(return_value="vector store could not be reset (locked)")
    )
    skill = MemorySkill(orchestrator=SimpleNamespace(memory=memory))
    skill.setup()
    command = skill.match("forget everything")

    result = asyncio.run(skill.execute(command, "forget everything"))

    assert result.success is False
    assert "vector store could not be reset" in result.response
    assert "chroma_db" in result.response          # user is told what to do


def test_memory_skill_reports_clean_wipe():
    memory = SimpleNamespace(forget_all=Mock(return_value=None))
    skill = MemorySkill(orchestrator=SimpleNamespace(memory=memory))
    skill.setup()
    command = skill.match("forget everything")

    result = asyncio.run(skill.execute(command, "forget everything"))

    assert result.success is True
    assert result.response == "All memory cleared. Starting fresh."
