"""
Memory skill — save notes, recall facts semantically via vector memory.
"""
from __future__ import annotations

import re
from ai_jarvis.skills.base import BaseSkill, SkillResult


class MemorySkill(BaseSkill):
    name = "memory"
    description = "Save notes, recall facts, search memory semantically"
    version = "2.0.0"

    def setup(self):
        self.register_command(
            r"\bremember\b(.+)",
            self._handle_remember,
            "Save a fact or note to memory",
            ["remember I love coffee", "remember my meeting is at 3pm"],
        )
        self.register_command(
            r"\b(what do you remember|recall|search memory)\b(.*)",
            self._handle_recall,
            "Search memory semantically",
            ["what do you remember about coffee?", "recall my notes"],
        )
        self.register_command(
            r"\bforget everything\b",
            self._handle_forget,
            "Clear all memory",
            ["forget everything"],
        )

    def _handle_remember(self, text: str) -> SkillResult:
        note = re.sub(r"\bremember\b", "", text, flags=re.IGNORECASE).strip()
        if not note:
            return SkillResult(success=False, response="What should I remember?")
        result = self.orchestrator.memory.remember(note)
        return SkillResult(success=True, response=result)

    def _handle_recall(self, text: str) -> SkillResult:
        query = re.sub(
            r"\b(what do you remember|recall|search memory)\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if not query:
            query = "everything"
        memories = self.orchestrator.memory.recall(query)
        if not memories or memories == ["No relevant memories found."]:
            return SkillResult(success=True, response="I don't have any memories about that yet.")
        response = "Here's what I remember:\n" + "\n".join(f"• {m}" for m in memories)
        return SkillResult(success=True, response=response)

    def _handle_forget(self, text: str) -> SkillResult:
        error = self.orchestrator.memory.forget_all()
        if error:
            return SkillResult(
                success=False,
                speak=False,
                response=(
                    f"Conversation history cleared, but {error}. "
                    "The semantic memories may still be stored — "
                    "delete the data/chroma_db folder manually."
                ),
            )
        return SkillResult(success=True, response="All memory cleared. Starting fresh.")
