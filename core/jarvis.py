# ──────────────────────────────────────────────
#  core/jarvis.py  –  Central JARVIS orchestrator
# ──────────────────────────────────────────────
"""
Jarvis is the heart of the system.  Every other module (voice, brain,
automation, memory) is wired through here so the GUI and CLI can both
drive it through a single, clean interface.
"""
import re
import threading
from config import settings
from voice.tts import TTS
from voice.stt import STT
from brain.ai_brain import AIBrain
from automation.desktop import Desktop
from memory.memory_manager import MemoryManager


class Jarvis:
    """Central controller – routes commands to the right subsystem."""

    def __init__(self, on_message=None):
        """
        Args:
            on_message: Optional callback(role, text) for GUI updates.
                        role is "user" | "jarvis" | "system" | "error".
        """
        self.on_message = on_message or (lambda role, text: print(f"[{role.upper()}] {text}"))

        # Initialise subsystems
        self.tts = TTS()
        self.stt = STT()
        self.brain = AIBrain()
        self.desktop = Desktop()
        self.memory = MemoryManager()

        self.listening = False
        self._listen_thread: threading.Thread | None = None

    # ── Public helpers ────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """Speak text aloud and emit a jarvis message event."""
        self.on_message("jarvis", text)
        try:
            self.tts.speak(text)
        except Exception as e:
            self.on_message("error", f"TTS error: {e}")

    def process_text(self, text: str) -> None:
        """Handle a text command (from GUI input or voice transcript)."""
        text = text.strip()
        if not text:
            return

        self.on_message("user", text)
        self.memory.add_message("user", text)

        try:
            response = self._route(text)
        except Exception as e:
            response = f"I encountered an error: {e}"
            self.on_message("error", str(e))

        self.speak(response)
        self.memory.add_message("jarvis", response)

    # ── Command router ────────────────────────────────────────────────

    def _route(self, text: str) -> str:
        """
        Try built-in commands first.  If nothing matches, forward to AI.
        Returns the response string.
        """
        lower = text.lower().strip()

        # ── Greetings ─────────────────────────────────────────────────
        if re.search(r"\b(hello|hi|hey|greetings)\b", lower):
            return f"Hello, {settings.USER_NAME}. All systems are online. How can I assist you?"

        if re.search(r"\bhow are you\b", lower):
            return "All systems are running at optimal capacity. Ready to assist."

        # ── Identity ──────────────────────────────────────────────────
        if re.search(r"\b(your name|who are you)\b", lower):
            return f"I am {settings.JARVIS_NAME}, your personal AI assistant."

        if re.search(r"\b(who created you|who made you)\b", lower):
            return "I was created by my developer, inspired by Iron Man's JARVIS."

        # ── Time / Date ───────────────────────────────────────────────
        if re.search(r"\btime\b", lower):
            from datetime import datetime
            now = datetime.now().strftime("%I:%M %p")
            return f"The current time is {now}."

        if re.search(r"\b(date|today)\b", lower):
            from datetime import datetime
            today = datetime.now().strftime("%A, %B %d, %Y")
            return f"Today is {today}."

        # ── System status ─────────────────────────────────────────────
        if re.search(r"\b(status|systems|system info)\b", lower):
            return self.desktop.get_status()

        # ── Desktop Automation ────────────────────────────────────────
        if lower.startswith("open "):
            target = lower.removeprefix("open ").strip()
            return self.desktop.open_target(target)

        if lower.startswith("search for ") or lower.startswith("search "):
            query = lower.replace("search for ", "").replace("search ", "").strip()
            return self.desktop.search_web(query)

        if lower.startswith("go to ") or lower.startswith("open website "):
            site = lower.replace("go to ", "").replace("open website ", "").strip()
            return self.desktop.open_website(site)

        # ── Memory / Preferences ─────────────────────────────────────
        if lower.startswith("remember "):
            note = lower.removeprefix("remember ").strip()
            if not note:
                note = text[len("remember "):].strip()
            self.memory.save_note(note)
            return f"Noted, {settings.USER_NAME}. I'll remember that."

        if re.search(r"\b(what do you remember|show notes|my notes)\b", lower):
            notes = self.memory.get_notes()
            if notes:
                return "Here's what I remember:\n" + "\n".join(f"• {n}" for n in notes)
            return "I don't have any saved notes yet."

        if re.search(r"\b(forget everything|clear memory)\b", lower):
            self.memory.clear_notes()
            return "Memory cleared. Starting fresh."

        # ── Help ──────────────────────────────────────────────────────
        if re.search(r"\bhelp\b", lower):
            return self._help_text()

        # ── Exit ──────────────────────────────────────────────────────
        if re.search(r"\b(exit|quit|shutdown|goodbye|bye)\b", lower):
            return f"Shutting down. Goodbye, {settings.USER_NAME}."

        # ── AI fallback ───────────────────────────────────────────────
        history = self.memory.get_recent(10)
        return self.brain.ask(text, history)

    # ── Continuous listening ──────────────────────────────────────────

    def start_listening(self) -> None:
        """Start continuous STT loop in a background thread."""
        if self.listening:
            return
        self.listening = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        self.on_message("system", "Microphone active — speak now.")

    def stop_listening(self) -> None:
        """Stop the STT loop."""
        self.listening = False
        self.on_message("system", "Microphone stopped.")

    def _listen_loop(self) -> None:
        while self.listening:
            try:
                text = self.stt.listen()
                if text:
                    self.process_text(text)
            except Exception as e:
                self.on_message("error", f"Voice error: {e}")

    # ── Helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _help_text() -> str:
        return (
            "Here are some things I can do:\n"
            "• hello / hi JARVIS\n"
            "• what time is it / what's the date\n"
            "• system status\n"
            "• open <app>  (notepad, calculator, browser, vs code…)\n"
            "• search for <query>\n"
            "• go to <site>  (google, youtube, github, wikipedia…)\n"
            "• remember <note>\n"
            "• what do you remember\n"
            "• forget everything\n"
            "• tell me a joke\n"
            "• ask me anything  →  powered by AI\n"
            "• exit / goodbye"
        )
