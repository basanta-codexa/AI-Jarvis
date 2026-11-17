import asyncio
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import ai_jarvis.core.orchestrator as orchestrator_module
from ai_jarvis.config import settings
from ai_jarvis.core.orchestrator import JarvisOrchestrator
from ai_jarvis.skills.base import SkillResult
from ai_jarvis.core.tools import ToolRegistry, ToolSpec


@pytest.fixture(autouse=True)
def no_wikipedia_network(monkeypatch):
    """No test may make a real network request; override per test if needed."""
    monkeypatch.setattr(orchestrator_module, "wikipedia_summary", lambda query: None)


def make_orchestrator(skill=None):
    orchestrator = JarvisOrchestrator.__new__(JarvisOrchestrator)
    orchestrator.on_message = Mock()
    orchestrator.memory = SimpleNamespace(
        add_message=Mock(),
        get_recent=Mock(return_value=[]),
        recall=Mock(return_value=[]),
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


def _patch_async_client(monkeypatch, content="An answer."):
    """Install a fake AsyncOpenAI that records the request kwargs."""
    request = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )
    create = Mock()

    async def create_response(**kwargs):
        create(**kwargs)
        return request

    async def close_client():
        pass

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create_response)),
        close=close_client,
    )
    monkeypatch.setattr(orchestrator_module, "AsyncOpenAI", Mock(return_value=client))
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")
    return create


def test_ai_fallback_grounds_answer_in_relevant_memories(monkeypatch):
    create = _patch_async_client(monkeypatch)
    orchestrator = make_orchestrator()
    orchestrator.memory.recall.return_value = ["My favourite tea is jasmine."]

    asyncio.run(orchestrator._ai_fallback("What tea do I like?"))

    system_prompt = create.call_args.kwargs["messages"][0]["content"]
    assert "What you know about the user" in system_prompt
    assert "- My favourite tea is jasmine." in system_prompt
    orchestrator.memory.recall.assert_called_once_with("What tea do I like?", n=3)


def test_ai_fallback_sends_tool_schemas_when_registry_present(monkeypatch):
    create = _patch_async_client(monkeypatch)
    registry = ToolRegistry()
    registry.register(ToolSpec("get_time", "Get the time.", {}, lambda: "now"))
    orchestrator = make_orchestrator()
    orchestrator.tools = registry

    asyncio.run(orchestrator._ai_fallback("Hello"))

    assert create.call_args.kwargs["tools"] == registry.schemas()


def test_ai_fallback_does_not_send_tools_when_no_registry(monkeypatch):
    create = _patch_async_client(monkeypatch)
    orchestrator = make_orchestrator()  # __new__ — no tools attribute

    asyncio.run(orchestrator._ai_fallback("Hello"))

    assert "tools" not in create.call_args.kwargs


def test_ai_fallback_executes_tool_call_then_returns_final_answer(monkeypatch):
    first = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content=None,
        tool_calls=[SimpleNamespace(
            id="call_1",
            function=SimpleNamespace(name="remember_fact", arguments='{"fact": "I like tea"}'),
        )],
    ))])
    final = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(
        content="Noted, I'll remember that.", tool_calls=None,
    ))])
    calls = []

    async def create_response(**kwargs):
        calls.append(kwargs)
        return first if len(calls) == 1 else final

    async def close_client():
        pass

    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create_response)),
        close=close_client,
    )
    monkeypatch.setattr(orchestrator_module, "AsyncOpenAI", Mock(return_value=client))
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "test-key")

    registry = ToolRegistry()
    handler = Mock(return_value="Locked into memory: I like tea")
    registry.register(ToolSpec("remember_fact", "Save a fact.", {}, handler))
    orchestrator = make_orchestrator()
    orchestrator.tools = registry

    answer = asyncio.run(orchestrator._ai_fallback("Remember that I like tea"))

    assert answer == "Noted, I'll remember that."
    assert len(calls) == 2
    handler.assert_called_once_with(fact="I like tea")
    second_messages = calls[1]["messages"]
    assert any(
        m.get("role") == "tool" and m.get("content") == "Locked into memory: I like tea"
        for m in second_messages
    )
    assert any(m.get("role") == "assistant" and m.get("tool_calls") for m in second_messages)


def test_ai_fallback_adds_wikipedia_reference_for_lookup_questions(monkeypatch):
    create = _patch_async_client(monkeypatch)
    looked_up = []
    monkeypatch.setattr(
        orchestrator_module,
        "wikipedia_summary",
        lambda query: looked_up.append(query) or "Python is a programming language.",
    )
    orchestrator = make_orchestrator()

    asyncio.run(orchestrator._ai_fallback("What is Python?"))

    assert looked_up == ["Python"]
    system_prompt = create.call_args.kwargs["messages"][0]["content"]
    assert "Verified reference" in system_prompt
    assert "Python is a programming language." in system_prompt


def test_ai_fallback_skips_lookup_for_non_lookup_questions(monkeypatch):
    create = _patch_async_client(monkeypatch)
    looked_up = []
    monkeypatch.setattr(
        orchestrator_module,
        "wikipedia_summary",
        lambda query: looked_up.append(query) or "should not be used",
    )
    orchestrator = make_orchestrator()

    asyncio.run(orchestrator._ai_fallback("How can I stay productive?"))

    assert looked_up == []
    assert "Verified reference" not in create.call_args.kwargs["messages"][0]["content"]


def test_ai_fallback_includes_current_local_datetime(monkeypatch):
    from datetime import datetime

    create = _patch_async_client(monkeypatch)
    orchestrator = make_orchestrator()

    asyncio.run(orchestrator._ai_fallback("Is it a weekday?"))

    system_prompt = create.call_args.kwargs["messages"][0]["content"]
    assert "The current local date and time is" in system_prompt
    assert str(datetime.now().year) in system_prompt


def test_ai_fallback_ignores_empty_memory_results(monkeypatch):
    create = _patch_async_client(monkeypatch)
    orchestrator = make_orchestrator()
    orchestrator.memory.recall.return_value = ["No relevant memories found."]

    asyncio.run(orchestrator._ai_fallback("Hello"))

    system_prompt = create.call_args.kwargs["messages"][0]["content"]
    assert "What you know about the user" not in system_prompt


def test_ai_fallback_survives_memory_failure(monkeypatch):
    create = _patch_async_client(monkeypatch)
    orchestrator = make_orchestrator()
    orchestrator.memory.recall.side_effect = RuntimeError("vector store locked")

    assert asyncio.run(orchestrator._ai_fallback("Hello")) == "An answer."
    assert create.called


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


def test_get_status_reports_actual_subsystem_availability():
    orchestrator = make_orchestrator()
    orchestrator._ai_provider_status = "fallback"
    orchestrator._wake_word_enabled = True
    orchestrator.plugins.skills = {"system": object()}
    orchestrator.memory.get_stats = Mock(
        return_value={"total_messages": 5, "vector_memory": "offline"}
    )
    orchestrator.tts.is_available = False
    orchestrator.stt = SimpleNamespace(is_available=True)

    status = orchestrator.get_status()

    assert status == {
        "skills": ["system"],
        "memory": {"total_messages": 5, "vector_memory": "offline"},
        "ai": "fallback",
        "tts": "offline",
        "stt": "online",
        "wake_word": True,
    }
