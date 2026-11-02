"""
Plugin manager — discovers, loads, and manages skills dynamically.
This is what makes JARVIS extensible and professional.
"""
from __future__ import annotations

import importlib
import pkgutil
from pathlib import Path
from typing import Optional

from ai_jarvis.skills.base import BaseSkill, SkillCommand


class PluginManager:
    """Discovers and loads all skills from the skills package."""

    def __init__(self, orchestrator):
        self.orchestrator = orchestrator
        self.skills: dict[str, BaseSkill] = {}
        self.command_index: list[tuple[SkillCommand, BaseSkill]] = []

    def load_skills(self, skills_package: str = "ai_jarvis.skills") -> None:
        """Auto-discover and load all skills."""
        try:
            package = importlib.import_module(skills_package)
            package_path = Path(package.__file__).parent
        except Exception as e:
            print(f"[PluginManager] Could not load package: {e}")
            return

        for _, modname, ispkg in pkgutil.iter_modules([str(package_path)]):
            if ispkg or modname.startswith("_"):
                continue
            try:
                module = importlib.import_module(f"{skills_package}.{modname}")
                for attr in dir(module):
                    cls = getattr(module, attr)
                    if (
                        isinstance(cls, type)
                        and issubclass(cls, BaseSkill)
                        and cls is not BaseSkill
                    ):
                        skill = cls(self.orchestrator)
                        skill.setup()
                        self.skills[skill.name] = skill
                        for cmd in skill.commands:
                            self.command_index.append((cmd, skill))
                        print(f"[PluginManager] Loaded skill: {skill.name} v{skill.version}")
            except Exception as e:
                print(f"[PluginManager] Failed to load {modname}: {e}")

    def find_skill(self, text: str) -> Optional[tuple[SkillCommand, BaseSkill]]:
        """Find the best matching skill. Specific patterns take priority over
        generic fallbacks (like the AI skill's .+ pattern)."""
        matches = []
        for cmd, skill in self.command_index:
            matched_cmd = skill.match(text)
            if matched_cmd:
                matches.append((matched_cmd, skill))

        if not matches:
            return None

        # Sort by specificity: non-fallback patterns first, then longer patterns
        def specificity(item):
            cmd, _ = item
            is_fallback = cmd.pattern.strip() == r".+"
            return (is_fallback, -len(cmd.pattern))

        matches.sort(key=specificity)
        return matches[0]

    def list_commands(self) -> list[dict]:
        """List all registered commands (for help/menu)."""
        return [
            {
                "skill": skill.name,
                "description": cmd.description,
                "examples": cmd.examples,
            }
            for cmd, skill in self.command_index
        ]
