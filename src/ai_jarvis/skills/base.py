"""
Base class for JARVIS skills. Each skill is a pluggable module with
metadata, commands, and an execute method.
"""
from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass
class SkillResult:
    """Standardized result from a skill execution."""
    success: bool
    response: str
    data: dict = field(default_factory=dict)
    speak: bool = True


@dataclass
class SkillCommand:
    """A command pattern that a skill can handle."""
    pattern: str
    handler: Callable
    description: str
    examples: list[str] = field(default_factory=list)


class BaseSkill(ABC):
    """Base class for all JARVIS skills."""

    name: str = "base"
    description: str = "Base skill"
    version: str = "1.0.0"
    author: str = "JARVIS"

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.commands: list[SkillCommand] = []

    def register_command(
        self,
        pattern: str,
        handler: Callable,
        description: str,
        examples: list[str] | None = None,
    ):
        self.commands.append(
            SkillCommand(
                pattern=pattern,
                handler=handler,
                description=description,
                examples=examples or [],
            )
        )

    @abstractmethod
    def setup(self) -> None:
        """Called when skill is loaded. Register commands here."""
        ...

    def match(self, text: str) -> Optional[SkillCommand]:
        """Check if this skill can handle the given text."""
        lower = text.lower().strip()
        for cmd in self.commands:
            if re.search(cmd.pattern, lower, re.IGNORECASE):
                return cmd
        return None

    async def execute(self, command: SkillCommand, text: str) -> SkillResult:
        """Execute a matched command."""
        try:
            result = command.handler(text)
            if isinstance(result, SkillResult):
                return result
            return SkillResult(success=True, response=str(result))
        except Exception as e:
            return SkillResult(
                success=False,
                response=f"Error in {self.name}: {e}",
                speak=False,
            )
