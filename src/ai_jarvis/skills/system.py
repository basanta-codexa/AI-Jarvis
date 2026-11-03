"""
System skill — time, date, status, apps, websites, system info.
"""
from __future__ import annotations

import re
import subprocess
import webbrowser
import urllib.parse
from datetime import datetime

try:
    import psutil
    _PSUTIL_AVAILABLE = True
except ImportError:
    _PSUTIL_AVAILABLE = False

from ai_jarvis.skills.base import BaseSkill, SkillResult
from ai_jarvis.config.settings import (
    APPROVED_APPS, APPROVED_WEBSITES, USER_NAME, JARVIS_NAME,
)


class SystemSkill(BaseSkill):
    name = "system"
    description = "Time, date, system status, app launcher, web browser"
    version = "2.0.0"

    def setup(self):
        self.register_command(
            r"\b(hello|hi|hey|greetings)\b",
            self._handle_greeting,
            "Greeting response",
            ["hello", "hi JARVIS", "hey"],
        )
        self.register_command(
            r"\btime\b",
            self._handle_time,
            "Current time",
            ["what time is it", "time"],
        )
        self.register_command(
            r"\b(date|today)\b",
            self._handle_date,
            "Today's date",
            ["what is today's date", "date"],
        )
        self.register_command(
            r"\b(status|systems|system info)\b",
            self._handle_status,
            "System status (CPU, RAM, battery)",
            ["system status", "systems"],
        )
        self.register_command(
            r"\bopen\b(.+)",
            self._handle_open,
            "Open an approved app or website",
            ["open notepad", "open google", "open youtube"],
        )
        self.register_command(
            r"\b(go to|visit)\b(.+)",
            self._handle_website,
            "Open a website",
            ["go to github", "visit youtube"],
        )
        self.register_command(
            r"\b(who are you|your name|identity)\b",
            self._handle_identity,
            "Identity response",
            ["who are you", "what is your name"],
        )
        self.register_command(
            r"\bhelp\b",
            self._handle_help,
            "List available commands",
            ["help"],
        )
        self.register_command(
            r"\b(exit|quit|shutdown|goodbye|bye)\b",
            self._handle_exit,
            "Shutdown JARVIS",
            ["exit", "goodbye"],
        )
        self.register_command(
            r"\b(calculate|math|what is \d+[\s\+\-\*\/])\b",
            self._handle_math,
            "Simple calculations",
            ["calculate 25 times 4", "what is 2 plus 2"],
        )

    # ── Handlers ──────────────────────────────────────────────────

    def _handle_greeting(self, text: str) -> SkillResult:
        return SkillResult(
            success=True,
            response=f"Hello, {USER_NAME}. {JARVIS_NAME} is online. All systems operational. How can I assist you?",
        )

    def _handle_time(self, text: str) -> SkillResult:
        now = datetime.now().strftime("%I:%M %p")
        return SkillResult(success=True, response=f"The current time is {now}.")

    def _handle_date(self, text: str) -> SkillResult:
        today = datetime.now().strftime("%A, %B %d, %Y")
        return SkillResult(success=True, response=f"Today is {today}.")

    def _handle_status(self, text: str) -> SkillResult:
        parts = []
        if _PSUTIL_AVAILABLE:
            try:
                batt = psutil.sensors_battery()
                if batt:
                    status = "charging" if batt.power_plugged else "discharging"
                    parts.append(f"Battery at {int(batt.percent)}% and {status}.")
                cpu = psutil.cpu_percent(interval=0.5)
                parts.append(f"CPU usage at {int(cpu)}%.")
                mem = psutil.virtual_memory()
                parts.append(f"Memory usage at {int(mem.percent)}%.")
            except Exception as e:
                parts.append(f"System info error: {e}")
        else:
            parts.append("psutil not installed — install for system monitoring.")
        return SkillResult(success=True, response=" ".join(parts))

    def _handle_open(self, text: str) -> SkillResult:
        target = re.sub(r"\bopen\b", "", text, flags=re.IGNORECASE).strip()
        if not target:
            return SkillResult(success=False, response="What would you like me to open?")

        # Check websites first
        for key, url in APPROVED_WEBSITES.items():
            if key in target.lower():
                try:
                    webbrowser.open(url)
                    return SkillResult(success=True, response=f"Opening {key.title()} in your browser.")
                except Exception as e:
                    return SkillResult(success=False, response=f"Failed to open {key}: {e}")

        # Check apps
        for key, cmd in APPROVED_APPS.items():
            if key in target.lower():
                try:
                    if cmd.startswith("start "):
                        subprocess.Popen(cmd, shell=True)
                    else:
                        subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
                    return SkillResult(success=True, response=f"Opening {key.title()}.")
                except Exception as e:
                    return SkillResult(success=False, response=f"Failed to launch {key}: {e}")

        return SkillResult(
            success=False,
            response=f"I don't have '{target}' on my approved list, {USER_NAME}.",
        )

    def _handle_website(self, text: str) -> SkillResult:
        site = re.sub(r"\b(go to|visit)\b", "", text, flags=re.IGNORECASE).strip()
        if not site:
            return SkillResult(success=False, response="Which website should I open?")

        for key, url in APPROVED_WEBSITES.items():
            if key in site.lower():
                try:
                    webbrowser.open(url)
                    return SkillResult(success=True, response=f"Opening {key.title()}.")
                except Exception as e:
                    return SkillResult(success=False, response=f"Failed to open {key}: {e}")

        # Try direct URL
        if site.startswith("http") or "." in site:
            url = site if site.startswith("http") else f"https://{site}"
            try:
                webbrowser.open(url)
                return SkillResult(success=True, response=f"Opening {site}.")
            except Exception as e:
                return SkillResult(success=False, response=f"Failed to open {site}: {e}")

        return SkillResult(success=False, response=f"I don't have '{site}' on my approved websites list.")

    def _handle_identity(self, text: str) -> SkillResult:
        return SkillResult(
            success=True,
            response=f"I am {JARVIS_NAME}, your personal AI assistant. Created to serve you, {USER_NAME}.",
        )

    def _handle_help(self, text: str) -> SkillResult:
        cmds = self.orchestrator.plugins.list_commands()
        lines = [f"• {c['description']}" for c in cmds[:8]]
        return SkillResult(
            success=True,
            response="Here's what I can do:\n" + "\n".join(lines) + "\n\nJust ask me anything else for AI-powered answers.",
        )

    def _handle_exit(self, text: str) -> SkillResult:
        # Signal the host app (GUI closes the window, CLI quits) for real
        self.orchestrator.request_shutdown = True
        return SkillResult(
            success=True,
            response=f"Shutting down. Goodbye, {USER_NAME}.",
        )

    def _handle_math(self, text: str) -> SkillResult:
        """Handle simple math calculations."""
        import re as _re
        lower = text.lower()
        expr = lower
        expr = expr.replace("plus", "+")
        expr = expr.replace("minus", "-")
        expr = expr.replace("times", "*")
        expr = expr.replace("multiplied by", "*")
        expr = expr.replace("divided by", "/")
        expr = expr.replace("divide by", "/")
        expr = expr.replace("x", "*")
        expr = _re.sub(r"[^0-9\s\+\-\*\/\(\)\.]", "", expr)
        expr = expr.strip()
        if expr and any(op in expr for op in "+-*/"):
            try:
                result = eval(expr)  # nosec - offline local eval only
                return SkillResult(success=True, response=f"The result is {result}.")
            except Exception:
                pass
        return SkillResult(
            success=False,
            response="Please give me a math expression like '2 + 2' or 'calculate 10 times 5'.",
        )
