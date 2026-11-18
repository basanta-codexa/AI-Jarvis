from types import SimpleNamespace
from unittest.mock import Mock

from ai_jarvis.core.tools import ToolRegistry, ToolSpec, build_default_registry


def test_registry_exposes_openai_compatible_schemas():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        "ping", "Check connectivity.",
        {"type": "object", "properties": {}},
        lambda: "pong",
    ))

    assert registry.names() == ["ping"]
    assert registry.schemas() == [{
        "type": "function",
        "function": {
            "name": "ping",
            "description": "Check connectivity.",
            "parameters": {"type": "object", "properties": {}},
        },
    }]


def test_dispatch_calls_handler_with_arguments():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        "add", "Add numbers.",
        {"type": "object", "properties": {}},
        lambda a, b: str(a + b),
    ))

    assert registry.dispatch("add", {"a": 2, "b": 3}) == "5"


def test_dispatch_never_raises_for_unknown_tool_or_bad_arguments():
    registry = ToolRegistry()
    registry.register(ToolSpec(
        "ping", "Check connectivity.", {}, lambda: "pong",
    ))

    assert registry.dispatch("missing") == "Unknown tool: missing"
    assert "failed" in registry.dispatch("ping", {"unexpected": 1}).lower()


def make_orchestrator():
    return SimpleNamespace(
        memory=SimpleNamespace(
            remember=Mock(return_value="Locked into memory: tea"),
            recall=Mock(return_value=["My favourite tea is jasmine.", "No relevant memories found."]),
        ),
        plugins=SimpleNamespace(skills={
            "system": SimpleNamespace(
                _handle_status=lambda text: SimpleNamespace(response="CPU usage at 5%."),
                _handle_open=lambda text: SimpleNamespace(response=f"Opening: {text}"),
            ),
            "web": SimpleNamespace(
                _handle_search=lambda text: SimpleNamespace(response=f"Searching: {text}"),
            ),
        }),
        request_shutdown=False,
    )


def test_default_registry_exposes_expected_capabilities():
    registry = build_default_registry(make_orchestrator())

    assert registry.names() == [
        "get_time", "get_date", "remember_fact", "recall_facts",
        "get_system_status", "open_target", "search_web",
        "whatsapp_open", "whatsapp_find", "whatsapp_send", "whatsapp_close",
        "request_shutdown",
    ]
    assert all(schema["function"]["parameters"]["type"] == "object" for schema in registry.schemas())


def test_default_registry_handlers_use_existing_subsystems():
    orch = make_orchestrator()
    registry = build_default_registry(orch)

    assert "time is" in registry.dispatch("get_time")
    assert "Today is" in registry.dispatch("get_date")
    assert registry.dispatch("remember_fact", {"fact": " tea "}) == "Locked into memory: tea"
    orch.memory.remember.assert_called_once_with("tea")
    assert "My favourite tea is jasmine." in registry.dispatch("recall_facts", {"query": "tea"})
    assert "No relevant memories found." not in registry.dispatch("recall_facts", {"query": "tea"})
    assert registry.dispatch("get_system_status") == "CPU usage at 5%."


def test_open_and_search_tools_delegate_to_existing_skills():
    registry = build_default_registry(make_orchestrator())

    assert registry.dispatch("open_target", {"target": "notepad"}) == "Opening: open notepad"
    assert registry.dispatch("search_web", {"query": "python"}) == "Searching: search for python"
    assert registry.dispatch("open_target", {"target": "   "}) == "No app or website was specified."
    assert registry.dispatch("search_web", {"query": ""}) == "No search query was provided."


def test_whatsapp_tools_delegate_to_the_skill():
    wa = SimpleNamespace(
        _handle_open=lambda t: SimpleNamespace(response="Opening WhatsApp."),
        _handle_find=lambda t: SimpleNamespace(response=f"Found via {t}"),
        _handle_send=lambda t: SimpleNamespace(response=f"Sent via {t}"),
        _handle_close=lambda t: SimpleNamespace(response="Closed WhatsApp."),
    )
    orch = make_orchestrator()
    orch.plugins.skills["whatsapp"] = wa
    registry = build_default_registry(orch)

    assert registry.dispatch("whatsapp_open") == "Opening WhatsApp."
    assert registry.dispatch("whatsapp_find", {"name": "Siba"}) == "Found via find Siba's chat"
    assert registry.dispatch("whatsapp_send", {"message": "hi"}) == "Sent via send a message hi"
    assert registry.dispatch("whatsapp_close") == "Closed WhatsApp."


def test_request_shutdown_tool_sets_flag():
    orch = make_orchestrator()
    registry = build_default_registry(orch)

    assert registry.dispatch("request_shutdown") == "Shutdown requested."
    assert orch.request_shutdown is True
