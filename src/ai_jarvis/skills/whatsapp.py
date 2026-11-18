"""WhatsApp Desktop control: open, find a chat, send a message, close.

GUI automation is inherently machine-dependent, so all real actions live in
an injectable controller. The skill logic itself is fully testable with a
fake controller and never needs a running GUI.
"""
from __future__ import annotations

import re
import subprocess

from ai_jarvis.skills.base import BaseSkill, SkillResult

_FIND_RE = re.compile(r"\b(?:find|search)\s+(.+?)(?:'s)?\s+chat\b", re.IGNORECASE)


class WhatsAppController:
    """Real Windows GUI control via pyautogui + PowerShell."""

    def open(self) -> None:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        subprocess.Popen("start whatsapp:", shell=True, creationflags=flags)

    def close(self) -> None:
        script = (
            "Get-Process -Name WhatsApp -ErrorAction SilentlyContinue | "
            "ForEach-Object { $_.CloseMainWindow() }"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, timeout=10,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

    def find_chat(self, name: str) -> None:
        import time
        import pyautogui
        pyautogui.hotkey("ctrl", "f")
        time.sleep(0.4)
        pyautogui.write(name, interval=0.02)
        time.sleep(0.6)
        pyautogui.press("enter")
        time.sleep(0.4)

    def send_message(self, message: str) -> None:
        import time
        import pyautogui
        time.sleep(0.3)
        pyautogui.write(message, interval=0.02)
        pyautogui.press("enter")


class WhatsAppSkill(BaseSkill):
    name = "whatsapp"
    description = "Open WhatsApp, find a chat, send a message, close it"
    version = "2.0.0"

    def __init__(self, orchestrator):
        super().__init__(orchestrator)
        self.controller = getattr(orchestrator, "whatsapp_controller", None) or WhatsAppController()
        self._last_contact: str | None = None

    def setup(self):
        self.register_command(
            r"\bopen\s+whatsapp\b", self._handle_open,
            "Open WhatsApp Desktop", ["open whatsapp"],
        )
        self.register_command(
            r"\b(?:find|search)\s+(.+?)(?:'s)?\s+chat\b", self._handle_find,
            "Find someone's chat", ["find siba prasada padhi's chat"],
        )
        self.register_command(
            r"\bsend\s+(?:a\s+)?(?:message|msg)\b(.+)", self._handle_send,
            "Send a message in the current chat", ["send a message hello"],
        )
        self.register_command(
            r"\bclose\s+(?:the\s+)?whatsapp\b", self._handle_close,
            "Close WhatsApp", ["close whatsapp"],
        )

    def _handle_open(self, text: str) -> SkillResult:
        try:
            self.controller.open()
        except Exception as e:
            return SkillResult(success=False, response=f"Couldn't open WhatsApp: {e}")
        return SkillResult(success=True, response="Opening WhatsApp. Give me a moment to wake it up.")

    def _handle_find(self, text: str) -> SkillResult:
        match = _FIND_RE.search(text)
        name = match.group(1).strip() if match else ""
        if not name:
            return SkillResult(success=False, response="Who should I find? Give me a name.")
        try:
            self.controller.find_chat(name)
        except Exception as e:
            return SkillResult(success=False, response=f"Couldn't find that chat: {e}")
        self._last_contact = name
        return SkillResult(
            success=True,
            response=(
                f"Found {name}'s chat. There they are. Shall I say hello, "
                "or should I warn them first?" ),
        )

    def _handle_send(self, text: str) -> SkillResult:
        message = re.sub(
            r"\bsend\s+(?:a\s+)?(?:message|msg)\b", "", text, flags=re.IGNORECASE
        ).strip().strip(",").strip()
        message = message.replace(" ,", ",")
        if not message:
            return SkillResult(success=False, response="What should I send?")
        if not self._last_contact:
            return SkillResult(success=False, response="Which chat? Find someone first.")
        try:
            self.controller.send_message(message)
        except Exception as e:
            return SkillResult(success=False, response=f"Couldn't send the message: {e}")
        return SkillResult(
            success=True,
            response=f"Message sent to {self._last_contact}. Their inbox is now yours. No take-backs.",
        )

    def _handle_close(self, text: str) -> SkillResult:
        try:
            self.controller.close()
        except Exception as e:
            return SkillResult(success=False, response=f"Couldn't close WhatsApp: {e}")
        return SkillResult(success=True, response="WhatsApp closed. Digital doorway sealed.")
