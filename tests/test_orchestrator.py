import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

from ai_jarvis.core.orchestrator import JarvisOrchestrator
from ai_jarvis.skills.base import SkillResult


def make_orchestrator(skill=None):
    orchestrator = JarvisOrchestrator.__new__(JarvisOrchestrator)
    orchestrator.on_message = Mock()
    orchestrator.memory = SimpleNamespace(
        add_message=Mock(),
        get_recent=Mock(return_value=[]),
    )
    orchestrator.tts = SimpleNamespace(speak=Mock())
    orchestrator.plugins = SimpleNamespace(
        find_skill=Mock(return_value=(object(), skill) if skill else None)
    )
    return orchestrator


def test_process_routes_skill_and_speaks_response():
    async def execute(_command, _text):
        return SkillResult(success=True, response="Done.")

    skill = SimpleNamespace(name="example", execute=execute)
    orchestrator = make_orchestrator(skill)

    response = asyncio.run(orchestrator.process("  run task  "))

    assert response == "Done."
    assert orchestrator.memory.add_message.call_args_list[0].args == (
        "user",
        "run task",
    )
    assert orchestrator.memory.add_message.call_args_list[1].args == (
        "jarvis",
        "Done.",
    )
    orchestrator.tts.speak.assert_called_once_with("Done.")
    assert orchestrator.on_message.call_args_list[0].args == ("user", "run task")
    assert orchestrator.on_message.call_args_list[1].args == ("jarvis", "Done.")


def test_process_does_not_speak_when_skill_disables_speech():
    async def execute(_command, _text):
        return SkillResult(success=False, response="The command failed.", speak=False)

    orchestrator = make_orchestrator(
        SimpleNamespace(name="example", execute=execute)
    )

    response = asyncio.run(orchestrator.process("run task"))

    assert response == "The command failed."
    orchestrator.tts.speak.assert_not_called()


def test_process_uses_ai_fallback_when_no_skill_matches():
    orchestrator = make_orchestrator()

    async def fallback(text):
        return f"Offline answer for: {text}"

    orchestrator._ai_fallback = fallback
    response = asyncio.run(orchestrator.process("  explain Python  "))

    assert response == "Offline answer for: explain Python"
    orchestrator.tts.speak.assert_called_once_with(response)


def test_process_ignores_empty_input():
    orchestrator = make_orchestrator()

    assert asyncio.run(orchestrator.process("  \n")) == ""
    orchestrator.memory.add_message.assert_not_called()
    orchestrator.tts.speak.assert_not_called()
    orchestrator.on_message.assert_not_called()
