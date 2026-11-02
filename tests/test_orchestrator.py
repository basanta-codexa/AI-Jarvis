import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import ai_jarvis.core.orchestrator as orchestrator_module
from ai_jarvis.config import settings
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


def test_ai_fallback_uses_async_client_and_deduplicates_current_message(monkeypatch):
    orchestrator = make_orchestrator()
    orchestrator.memory.get_recent.return_value = [
        {"role": "user", "content": "What is Python?"},
    ]
    request = SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=SimpleNamespace(content="Python is a programming language.")
            )
        ]
    )
    create = Mock()

    async def create_response(**kwargs):
        create(**kwargs)
        return request

    close = Mock()

    async def close_client():
        close()

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=create_response)
        ),
        close=close_client,
    )
    client_init = Mock(return_value=client)
    monkeypatch.setattr(orchestrator_module, "AsyncOpenAI", client_init)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(settings, "AI_REQUEST_TIMEOUT", 12)
    monkeypatch.setattr(settings, "AI_MAX_RETRIES", 2)

    response = asyncio.run(orchestrator._ai_fallback("What is Python?"))

    assert response == "Python is a programming language."
    client_init.assert_called_once_with(
        api_key="test-key",
        base_url=settings.OPENAI_BASE_URL,
        timeout=12,
        max_retries=2,
    )
    assert [message["content"] for message in create.call_args.kwargs["messages"]].count(
        "What is Python?"
    ) == 1
    close.assert_called_once()


def test_ai_fallback_reports_provider_error_and_uses_offline_response(monkeypatch):
    orchestrator = make_orchestrator()
    events = []
    orchestrator.on_message = Mock(side_effect=lambda *event: events.append(event))
    closed = Mock()

    class ProviderError(Exception):
        pass

    async def fail_request(**_kwargs):
        raise ProviderError("provider unavailable")

    async def close_client():
        closed()

    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=fail_request)
        ),
        close=close_client,
    )
    monkeypatch.setattr(orchestrator_module, "AsyncOpenAI", Mock(return_value=client))
    monkeypatch.setattr(orchestrator_module, "APIError", ProviderError)
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    orchestrator._offline_response = Mock(return_value="Offline answer.")

    response = asyncio.run(orchestrator._ai_fallback("Explain Python"))

    assert response == "Offline answer."
    assert events == [
        ("error", "AI provider request failed (ProviderError); using offline responses.")
    ]
    orchestrator._offline_response.assert_called_once_with("Explain Python")
    closed.assert_called_once()


def test_ai_fallback_reports_unconfigured_provider(monkeypatch):
    orchestrator = make_orchestrator()
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    orchestrator._offline_response = Mock(return_value="Offline answer.")

    response = asyncio.run(orchestrator._ai_fallback("Explain Python"))

    assert response == "Offline answer."
    orchestrator.on_message.assert_called_once_with(
        "system",
        "AI provider is not configured; using offline responses.",
    )
    orchestrator._offline_response.assert_called_once_with("Explain Python")
