"""Explicit tool registry: the capabilities the AI is allowed to invoke.

This step only defines the schemas and a safe dispatcher. Wiring them into the
chat-completions request happens in the next step.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    parameters: dict
    handler: Callable[..., str]


class ToolRegistry:
    """Small registry with OpenAI-compatible schemas and a fail-soft dispatcher."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def names(self) -> list[str]:
        return list(self._tools)

    def schemas(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": spec.name,
                    "description": spec.description,
                    "parameters": spec.parameters,
                },
            }
            for spec in self._tools.values()
        ]

    def dispatch(self, name: str, arguments: dict | None = None) -> str:
        spec = self._tools.get(name)
        if spec is None:
            return f"Unknown tool: {name}"
        try:
            return str(spec.handler(**(arguments or {})))
        except Exception as exc:
            return f"Tool {name} failed: {type(exc).__name__}: {exc}"


def _string_arg(name: str, description: str) -> dict:
    return {
        "type": "object",
        "properties": {name: {"type": "string", "description": description}},
        "required": [name],
    }


def build_default_registry(orchestrator) -> ToolRegistry:
    """Register the capabilities already available in JARVIS."""
    registry = ToolRegistry()
    memory = orchestrator.memory

    def get_time() -> str:
        return f"The current local time is {datetime.now().strftime('%I:%M %p')}."

    def get_date() -> str:
        return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

    def remember_fact(fact: str) -> str:
        if not fact or not fact.strip():
            return "No fact was provided."
        return memory.remember(fact.strip())

    def recall_facts(query: str) -> str:
        if not query or not query.strip():
            query = "everything"
        results = memory.recall(query.strip()) or []
        useful = [
            item for item in results
            if isinstance(item, str) and item and item != "No relevant memories found."
        ]
        if not useful:
            return "I don't have any memories about that yet."
        return "What I remember:\n" + "\n".join(f"- {item}" for item in useful)

    def get_system_status() -> str:
        skill = orchestrator.plugins.skills.get("system")
        if skill is None:
            return "System monitoring is unavailable."
        return skill._handle_status("").response

    def open_target(target: str) -> str:
        if not target or not target.strip():
            return "No app or website was specified."
        skill = orchestrator.plugins.skills.get("system")
        if skill is None:
            return "The launcher is unavailable."
        return skill._handle_open(f"open {target.strip()}").response

    def search_web(query: str) -> str:
        if not query or not query.strip():
            return "No search query was provided."
        skill = orchestrator.plugins.skills.get("web")
        if skill is None:
            return "Web search is unavailable."
        return skill._handle_search(f"search for {query.strip()}").response

    def whatsapp_open() -> str:
        skill = orchestrator.plugins.skills.get("whatsapp")
        if skill is None:
            return "WhatsApp control is unavailable."
        return skill._handle_open("open whatsapp").response

    def whatsapp_find(name: str) -> str:
        if not name or not name.strip():
            return "Who should I find?"
        skill = orchestrator.plugins.skills.get("whatsapp")
        if skill is None:
            return "WhatsApp control is unavailable."
        return skill._handle_find(f"find {name.strip()}'s chat").response

    def whatsapp_send(message: str) -> str:
        if not message or not message.strip():
            return "What should I send?"
        skill = orchestrator.plugins.skills.get("whatsapp")
        if skill is None:
            return "WhatsApp control is unavailable."
        return skill._handle_send(f"send a message {message.strip()}").response

    def whatsapp_close() -> str:
        skill = orchestrator.plugins.skills.get("whatsapp")
        if skill is None:
            return "WhatsApp control is unavailable."
        return skill._handle_close("close whatsapp").response

    def request_shutdown() -> str:
        orchestrator.request_shutdown = True
        return "Shutdown requested."

    registry.register(ToolSpec(
        "get_time", "Get the current local time.", {"type": "object", "properties": {}},
        get_time,
    ))
    registry.register(ToolSpec(
        "get_date", "Get today's local date.", {"type": "object", "properties": {}},
        get_date,
    ))
    registry.register(ToolSpec(
        "remember_fact", "Save a fact about the user for later recall.",
        _string_arg("fact", "The fact to remember, e.g. 'My favourite tea is jasmine'."),
        remember_fact,
    ))
    registry.register(ToolSpec(
        "recall_facts", "Search stored memories for facts relevant to a query.",
        _string_arg("query", "What to recall, e.g. 'tea' or 'my meeting'."),
        recall_facts,
    ))
    registry.register(ToolSpec(
        "get_system_status", "Report CPU, memory and battery usage.",
        {"type": "object", "properties": {}},
        get_system_status,
    ))
    registry.register(ToolSpec(
        "open_target", "Open an approved app or website on the user's machine.",
        _string_arg("target", "The app or website, e.g. 'notepad', 'vs code', 'github'."),
        open_target,
    ))
    registry.register(ToolSpec(
        "search_web", "Open a web search for a query in the user's browser.",
        _string_arg("query", "What to search for."),
        search_web,
    ))
    registry.register(ToolSpec(
        "whatsapp_open", "Open WhatsApp Desktop on the user's machine.",
        {"type": "object", "properties": {}}, whatsapp_open,
    ))
    registry.register(ToolSpec(
        "whatsapp_find", "Find a person's chat in WhatsApp so a message can be sent.",
        _string_arg("name", "The contact name, e.g. 'Siba Prasada Padhi'."),
        whatsapp_find,
    ))
    registry.register(ToolSpec(
        "whatsapp_send", "Send a message in the currently open WhatsApp chat.",
        _string_arg("message", "The message text to send."), whatsapp_send,
    ))
    registry.register(ToolSpec(
        "whatsapp_close", "Close WhatsApp Desktop.",
        {"type": "object", "properties": {}}, whatsapp_close,
    ))
    registry.register(ToolSpec(
        "request_shutdown", "Shut down the assistant when the user asks to exit.",
        {"type": "object", "properties": {}},
        request_shutdown,
    ))
    return registry
