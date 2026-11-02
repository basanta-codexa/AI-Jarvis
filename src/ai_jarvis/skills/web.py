"""
Web skill — search the internet and open websites.
"""
from __future__ import annotations

import re
import urllib.parse
import webbrowser
from ai_jarvis.skills.base import BaseSkill, SkillResult


class WebSkill(BaseSkill):
    name = "web"
    description = "Search the web and browse websites"
    version = "2.0.0"

    def setup(self):
        self.register_command(
            r"\b(search for|search|look up|find)\b(.+)",
            self._handle_search,
            "Search the web",
            ["search for python tutorials", "look up weather in London"],
        )

    def _handle_search(self, text: str) -> SkillResult:
        query = re.sub(
            r"\b(search for|search|look up|find)\b",
            "",
            text,
            flags=re.IGNORECASE,
        ).strip()
        if not query:
            return SkillResult(success=False, response="What would you like me to search for?")

        encoded = urllib.parse.quote_plus(query)
        url = f"https://www.google.com/search?q={encoded}"
        try:
            webbrowser.open(url)
            return SkillResult(success=True, response=f"Searching the web for: {query}")
        except Exception as e:
            return SkillResult(success=False, response=f"Search failed: {e}")
