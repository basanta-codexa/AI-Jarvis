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
            "Open WhatsApp Desktop", ["open whatsapp"], priority=20,
        )
        self.register_command(
            r"\b(?:find|search)\s+(.+?)(?:'s)?\s+chat\b", self._handle_find,
            "Find someone's chat", ["find siba prasada padhi's chat"], priority=20,
        )
        self.register_command(
            r"\bsend\b(.+)", self._handle_send,
            "Send a WhatsApp message (finds the contact if named)",
            ["send a good morning message to maheswar", "send hello"],
            priority=20,
        )
        self.register_command(
            r"\bmessage\s+(\S+)\s+(.+)", self._handle_send,
            "Message someone on WhatsApp", ["message maheswar good morning"],
            priority=20,
        )
        self.register_command(
            r"\bclose\s+(?:the\s+)?whatsapp\b", self._handle_close,
            "Close WhatsApp", ["close whatsapp"], priority=20,
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

    @staticmethod
    def _parse_send(text: str) -> tuple[str | None, str]:
        """Extract (recipient, message) from natural phrasing.

        Handles "send hello", "send a message hello",
        "send a good morning message to maheswar", and
        "message maheswar good morning".
        """
        is_message_form = bool(re.match(r"^\s*message\b", text, re.IGNORECASE))
        body = re.sub(r"^\s*(?:send|message)\b", "", text, flags=re.IGNORECASE).strip()
        recipient = None
        if is_message_form and " to " not in body.lower():
            # "message maheswar good morning" — first word is the contact.
            parts = body.split(None, 1)
            if len(parts) == 2:
                recipient, body = parts[0], parts[1]
        # "… to <name>" — recipient is everything after the last " to ".
        parts = re.split(r"\s+to\s+", body, flags=re.IGNORECASE)
        if len(parts) > 1:
            body, recipient = parts[0], parts[-1].strip().strip(".")
        # Remove filler words that describe the message rather than its content.
        body = re.sub(
            r"\b(?:a|an|the|message|msg|saying|that\s+says)\b",
            " ", body, flags=re.IGNORECASE,
        )
        message = re.sub(r"\s+", " ", body).strip().strip(",").strip()
        message = message.replace(" ,", ",")
        return recipient or None, message

    def _handle_send(self, text: str) -> SkillResult:
        recipient, message = self._parse_send(text)
        if not message:
            return SkillResult(success=False, response="What should I send?")
        try:
            # If a name was given, find that chat first — no need for a
            # separate "find …'s chat" command.
            if recipient:
                self.controller.find_chat(recipient)
                self._last_contact = recipient
            if not self._last_contact:
                return SkillResult(success=False, response="Which chat? Mention a name first.")
            self.controller.send_message(message)
        except Exception as e:
            return SkillResult(success=False, response=f"Couldn't send the message: {e}")
        return SkillResult(
            success=True,
            response=(
                f"Message sent to {self._last_contact}: '{message}'. "
                "Your words are out there now. No take-backs."
            ),
        )

    def _handle_close(self, text: str) -> SkillResult:
        try:
            self.controller.close()
        except Exception as e:
            return SkillResult(success=False, response=f"Couldn't close WhatsApp: {e}")
        return SkillResult(success=True, response="WhatsApp closed. Digital doorway sealed.")
