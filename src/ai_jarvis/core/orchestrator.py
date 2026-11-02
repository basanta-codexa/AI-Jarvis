"""
Central orchestrator — routes input through skills → AI → response.
This is the brain of JARVIS.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from openai import APIError, AsyncOpenAI

from ai_jarvis.core.plugin_manager import PluginManager
from ai_jarvis.core.memory import MemorySystem
from ai_jarvis.voice.tts import TTS
from ai_jarvis.voice.stt import STT
from ai_jarvis.config import settings


class JarvisOrchestrator:
    """Main agent controller — the brain of JARVIS."""

    def __init__(self, on_message=None, data_dir: str | Path = None):
        if data_dir is None:
            data_dir = settings.MEMORY_DIR
        self.data_dir = Path(data_dir)

        # Callback for UI updates
        self.on_message = on_message or (lambda role, text: print(f"[{role.upper()}] {text}"))

        # Subsystems
        self.memory = MemorySystem(self.data_dir)
        self.tts = TTS()
        self.stt = STT()
        self.plugins = PluginManager(self)

        # Load all skills
        self.plugins.load_skills()

        # Wake word state
        self._listening = False
        self._wake_word_enabled = True
        self._ai_provider_status = (
            "configured" if settings.OPENAI_API_KEY else "offline"
        )

        print(f"[Jarvis] Orchestrator initialized with {len(self.plugins.skills)} skills")

    async def process(self, text: str) -> str:
        """Process user input through skills, then AI fallback."""
        if not text or not text.strip():
            return ""

        text = text.strip()
        self.on_message("user", text)
        self.memory.add_message("user", text)

        # 1. Try specific skills first (non-AI skills take priority)
        match = self.plugins.find_skill(text)
        if match:
            cmd, skill = match
            # Don't let AI fallback catch specific commands
            if skill.name != "ai" or cmd.pattern.strip() != r".+":
                result = await skill.execute(cmd, text)
                response = result.response
                speak = result.speak
            else:
                # AI fallback only if no specific skill matched
                response = await self._ai_fallback(text)
                speak = True
        else:
            # 2. AI fallback
            response = await self._ai_fallback(text)
            speak = True

        self.on_message("jarvis", response)
        self.memory.add_message("jarvis", response)

        if speak:
            self.tts.speak(response)

        return response

    async def _ai_fallback(self, text: str) -> str:
        """AI-powered response for open-ended questions."""
        if not settings.OPENAI_API_KEY:
            self._ai_provider_status = "offline"
            self.on_message(
                "system",
                "AI provider is not configured; using offline responses.",
            )
            return self._offline_response(text)

        try:
            client = AsyncOpenAI(
                api_key=settings.OPENAI_API_KEY,
                base_url=settings.OPENAI_BASE_URL,
                timeout=settings.AI_REQUEST_TIMEOUT,
                max_retries=settings.AI_MAX_RETRIES,
            )
            try:
                history = self.memory.get_recent(10)
                if (
                    history
                    and history[-1].get("role") == "user"
                    and history[-1].get("content") == text
                ):
                    history = history[:-1]

                messages = [
                    {
                        "role": "system",
                        "content": (
                            f"You are {settings.JARVIS_NAME}, a helpful, witty, intelligent personal AI "
                            f"assistant inspired by Iron Man's J.A.R.V.I.S. You are talking with {settings.USER_NAME}. "
                            "Keep responses concise, helpful, and slightly formal."
                        ),
                    }
                ]
                for msg in history:
                    role = (
                        "assistant" if msg.get("role") == "jarvis"
                        else msg.get("role", "user")
                    )
                    messages.append({"role": role, "content": msg["content"]})
                messages.append({"role": "user", "content": text})

                response = await client.chat.completions.create(
                    model=settings.AI_MODEL,
                    messages=messages,
                    max_tokens=settings.AI_MAX_TOKENS,
                    temperature=settings.AI_TEMPERATURE,
                )
            finally:
                await client.close()

            content = (
                response.choices[0].message.content
                if response.choices else None
            )
            if content and content.strip():
                self._ai_provider_status = "online"
                return content.strip()

            self._ai_provider_status = "fallback"
            self.on_message("error", "AI provider returned an empty response.")
        except APIError as exc:
            self._ai_provider_status = "fallback"
            self.on_message(
                "error",
                f"AI provider request failed ({type(exc).__name__}); using offline responses.",
            )

        return self._offline_response(text)

    def _offline_response(self, text: str) -> str:
        """Smart offline responses when no API key."""
        import re
        import random
        from datetime import datetime
        from ai_jarvis.config.settings import USER_NAME, JARVIS_NAME

        lower = text.lower().strip()

        # Greetings
        if re.search(r"\b(hello|hi|hey|greetings)\b", lower):
            return f"Hello, {USER_NAME}. JARVIS is online and ready."
        if "how are you" in lower:
            return "All systems running at optimal capacity. How can I assist?"

        # Identity
        if re.search(r"\b(your name|who are you)\b", lower):
            return f"I am {JARVIS_NAME}, your personal AI assistant."
        if re.search(r"\b(who created you|who made you)\b", lower):
            return "I was created by my developer, inspired by Iron Man's J.A.R.V.I.S."

        # Time / Date
        if re.search(r"\btime\b", lower):
            return f"The current time is {datetime.now().strftime('%I:%M %p')}."
        if re.search(r"\b(date|today)\b", lower):
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

        # Jokes
        if "joke" in lower or "funny" in lower:
            jokes = [
                "Why do programmers prefer dark mode? Because light attracts bugs!",
                "Why did the computer go to the doctor? It had a virus!",
                "There are 10 types of people: those who understand binary, and those who don't.",
            ]
            return random.choice(jokes)

        # Knowledge base
        kb = {
            "python": "Python is a high-level, interpreted programming language known for readability.",
            "javascript": "JavaScript powers interactive websites and web applications.",
            "ai": "AI simulates human intelligence in machines.",
            "jarvis": "JARVIS is your personal AI assistant, inspired by Iron Man.",
        }
        for key, answer in kb.items():
            if key in lower:
                return answer

        return (
            "I can help with many things offline. Connect my AI brain with an OPENAI_API_KEY "
            "for full conversation capabilities."
        )

    def process_sync(self, text: str) -> str:
        """Synchronous wrapper for process (for GUI callbacks)."""
        return asyncio.run(self.process(text))

    def start_wake_word(self):
        """Enable always-on wake word listening."""
        self._wake_word_enabled = True
        self.on_message("system", "Wake word enabled. Say 'Hey JARVIS' to activate.")

    def stop_wake_word(self):
        self._wake_word_enabled = False
        self.on_message("system", "Wake word disabled.")

    def get_status(self) -> dict:
        """Get system status for UI display."""
        return {
            "skills": list(self.plugins.skills.keys()),
            "memory": self.memory.get_stats(),
            "ai": getattr(
                self, "_ai_provider_status",
                "configured" if settings.OPENAI_API_KEY else "offline",
            ),
            "tts": "online" if self.tts.is_available else "offline",
            "stt": "online" if self.stt.is_available else "offline",
            "wake_word": self._wake_word_enabled,
        }

    def shutdown(self):
        """Clean shutdown."""
        self.tts.shutdown()
