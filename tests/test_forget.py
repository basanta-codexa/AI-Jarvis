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
    return MemorySystem(tmp_path)


def test_corrupt_history_is_backed_up_not_erased(monkeypatch, tmp_path):
    history = tmp_path / "conversation.json"
    history.write_text("{ not valid json", encoding="utf-8")

    memory = make_memory(monkeypatch, tmp_path)

    assert memory.get_all_history() == []
    backups = list(tmp_path.glob("conversation.corrupt.*.bak"))
    assert len(backups) == 1
    assert backups[0].read_text(encoding="utf-8") == "{ not valid json"


def test_repeated_corruption_keeps_both_backups(monkeypatch, tmp_path):
    history = tmp_path / "conversation.json"

    history.write_text("first corrupt copy", encoding="utf-8")
    make_memory(monkeypatch, tmp_path)
    history.write_text("second corrupt copy", encoding="utf-8")
    make_memory(monkeypatch, tmp_path)

    backups = list(tmp_path.glob("conversation.corrupt.*.bak"))
    assert len(backups) == 2
    assert {b.read_text(encoding="utf-8") for b in backups} == {
        "first corrupt copy", "second corrupt copy",
    }


def test_save_history_leaves_no_tmp_file(monkeypatch, tmp_path):
    memory = make_memory(monkeypatch, tmp_path)
    memory.add_message("user", "hello")

    assert not (tmp_path / "conversation.tmp").exists()
    assert json.loads((tmp_path / "conversation.json").read_text(encoding="utf-8")) == \
        memory.get_all_history()


def test_forget_all_erases_vector_directory_and_recreates_empty_store(monkeypatch, tmp_path):
    class FakeClient:
        def get_or_create_collection(self, name):
            return "COLLECTION"

    memory = make_memory(monkeypatch, tmp_path, vector=True, client_cls=FakeClient)
    memory.add_message("user", "remember the milk")
    marker = memory.chroma_dir / "leftover.dat"
    marker.write_text("old vector data", encoding="utf-8")
    assert marker.exists()

    error = memory.forget_all()

    assert error is None
    assert not marker.exists()                       # on-disk store really removed
    assert memory.chroma_dir.exists()                # empty store recreated
    assert memory._collection == "COLLECTION"
    assert memory.get_all_history() == []


def test_forget_all_reports_vector_failure(monkeypatch, tmp_path):
    class FakeClient:
        def get_or_create_collection(self, name):
            return "COLLECTION"

    memory = make_memory(monkeypatch, tmp_path, vector=True, client_cls=FakeClient)
    memory.add_message("user", "secret fact")

    def fail_rmtree(path):
        raise OSError("directory is locked")

    monkeypatch.setattr(memory_module.shutil, "rmtree", fail_rmtree)
    error = memory.forget_all()

    assert error is not None
    assert "could not be erased" in error
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
