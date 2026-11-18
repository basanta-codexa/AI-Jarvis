"""Handle multi-action requests such as 'open google and search for X'."""
from __future__ import annotations

import re

from ai_jarvis.skills.base import BaseSkill, SkillResult

# Anchored so it only claims requests that are explicitly two actions.
_COMPOUND_RE = re.compile(
    r"^\s*open\s+(.+?)\s+and\s+(?:search for|search|look up|find)\s+(.+?)\s*$",
    re.IGNORECASE,
)


class CompoundSkill(BaseSkill):
    name = "compound"
    description = "Open a target and run a web search in one request"
    version = "2.0.0"

    def setup(self):
        self.register_command(
            _COMPOUND_RE.pattern,
            self._handle_compound,
            "Open an app/site and search the web together",
            ["open google and search for dhoni ipl retirement"],
        )

    def _handle_compound(self, text: str) -> SkillResult:
        match = _COMPOUND_RE.match(text)
        if not match:
            return SkillResult(
                success=False, response="I couldn't parse that request.", speak=False,
            )
        target, query = match.group(1).strip(), match.group(2).strip()
        skills = self.orchestrator.plugins.skills
        responses = []

        launcher = skills.get("system")
        if launcher is not None:
            responses.append(launcher._handle_open(f"open {target}").response)
        searcher = skills.get("web")
        if searcher is not None:
            responses.append(searcher._handle_search(f"search for {query}").response)

        if not responses:
            return SkillResult(success=False, response="Those actions aren't available.")
        return SkillResult(success=True, response=" ".join(responses))
