"""
AI skill — placeholder. AI fallback is handled directly by the orchestrator.
This skill exists for plugin registry completeness but registers no commands.
"""
from __future__ import annotations

from ai_jarvis.skills.base import BaseSkill


class AISkill(BaseSkill):
    name = "ai"
    description = "AI-powered conversation (handled by orchestrator fallback)"
    version = "2.0.0"

    def setup(self):
        # No commands registered — orchestrator handles AI fallback directly
        pass
