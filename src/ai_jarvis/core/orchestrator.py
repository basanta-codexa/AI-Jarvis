"""
Central orchestrator — routes input through skills → AI → response.
This is the brain of JARVIS.
"""
from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path

from openai import APIError, AsyncOpenAI

from ai_jarvis.core.plugin_manager import PluginManager
from ai_jarvis.core.memory import MemorySystem
from ai_jarvis.core.lookup import duckduckgo_answer, wikipedia_search, wikipedia_summary
from ai_jarvis.core.tools import ToolRegistry, build_default_registry
from ai_jarvis.voice.tts import TTS
from ai_jarvis.voice.stt import STT
from ai_jarvis.config import settings


class JarvisOrchestrator:
    """Main agent controller — the brain of JARVIS."""

    _LOOKUP_RE = re.compile(
        r"^\s*(?:(?:i'm|i am)\s+)?(?:what is|what's|who is|who's|define|"
        r"tell me about|explain|curious about|info on|information on|"
        r"details about|facts about|learn about)\s+(.+?)\??\s*$",
        re.IGNORECASE,
    )
    # Factual yes/no and "when/why/how" questions: "did dhoni retire from ipl".
    _FACT_RE = re.compile(
        r"^\s*(?:did|does|do|is|are|was|were|has|have|can|could|will|would|"
        r"when|where|why|how)\b\s+(.+?)\??\s*$",
        re.IGNORECASE,
    )
    _NON_FACT_SUBJECTS = frozenset({
        "you", "i", "it", "this", "that", "there", "they", "we", "he", "she",
    })

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

        # Capabilities the AI is allowed to invoke
        self.tools = build_default_registry(self)

        self._listening = False
        self.request_shutdown = False     # set by the exit skill; host apps poll it
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
            result = await skill.execute(cmd, text)
            response = result.response
            speak = result.speak
        else:
            # No skill matched — let the AI answer.
            response = await self._ai_fallback(text)
            speak = True

        self.on_message("jarvis", response)
        self.memory.add_message("jarvis", response)

        if speak:
            self.tts.speak(response)

        return response

    def _recall_for_prompt(self, text: str, limit: int = 3) -> list[str]:
        """Ground answers in what JARVIS already remembers.

        Memory is an enhancement, never a hard dependency: a failure or an
        empty result simply means no context is added.
        """
        try:
            recalled = self.memory.recall(text, n=limit) or []
        except Exception:
            return []
        cleaned = []
        for item in recalled:
            if not isinstance(item, str):
                continue
            item = item.strip()
            if not item or item == "No relevant memories found.":
                continue
            cleaned.append(item)
        return cleaned[:limit]

    async def _lookup_for_prompt(self, text: str) -> str | None:
        """Fetch a short reference for lookup-style questions, if any."""
        match = self._LOOKUP_RE.match(text)
        if match:
            subject = match.group(1).strip().strip("?.").strip()
        else:
            match = self._FACT_RE.match(text)
            if not match:
                return None
            subject = match.group(1).strip().strip("?.").strip()
            words = {w for w in re.findall(r"[a-z]+", subject.lower())}
            # "how are you" / "how can I …" are conversation, not lookups.
            if not words or words <= self._NON_FACT_SUBJECTS or {"i", "you"} & words:
                return None
        if not subject:
            return None
        summary = await asyncio.to_thread(wikipedia_summary, subject)
        if summary:
            return f"Reference about {subject}: {summary}"
        results = await asyncio.to_thread(wikipedia_search, subject, 3)
        if results:
            return f"Related Wikipedia articles about {subject}:\n{results}"
        answer = await asyncio.to_thread(duckduckgo_answer, subject)
        if answer:
            return f"Quick answer about {subject}: {answer}"
        return None

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

                from datetime import datetime
                local_time = datetime.now().strftime("%A, %B %d, %Y at %I:%M %p")
                system_prompt = (
                    f"You are {settings.JARVIS_NAME}, a helpful, witty, intelligent personal AI "
                    f"assistant inspired by Iron Man's J.A.R.V.I.S. You are talking with {settings.USER_NAME}. "
                    f"The current local date and time is {local_time}. "
                    "Keep responses concise, helpful, and slightly formal."
                )
                memories = self._recall_for_prompt(text)
                if memories:
                    system_prompt += (
                        "\n\nWhat you know about the user (use it when relevant):\n"
                        + "\n".join(f"- {m}" for m in memories)
                    )
                reference = await self._lookup_for_prompt(text)
                if reference:
                    system_prompt += (
                        "\n\nVerified reference (use it when relevant):\n- " + reference
                    )
                messages = [{"role": "system", "content": system_prompt}]
                for msg in history:
                    role = (
                        "assistant" if msg.get("role") == "jarvis"
                        else msg.get("role", "user")
                    )
                    messages.append({"role": role, "content": msg["content"]})
                messages.append({"role": "user", "content": text})

                request_kwargs = {
                    "model": settings.AI_MODEL,
                    "messages": messages,
                    "max_tokens": settings.AI_MAX_TOKENS,
                    "temperature": settings.AI_TEMPERATURE,
                }
                tools = getattr(self, "tools", None)
                if tools is not None and tools.names():
                    request_kwargs["tools"] = tools.schemas()
                    messages[0]["content"] += (
                        "\n\nUse your tools when they fit: remember_fact when the user states "
                        "something to remember, recall_facts when they ask what you know about "
                        "them, get_time/get_date for clock questions, open_target/search_web for "
                        "actions, and request_shutdown only when they clearly want to exit. "
                        "Prefer a tool over guessing."
                    )

                response = await client.chat.completions.create(**request_kwargs)

                # One tool round trip: the model may ask to use a capability.
                # Anything after that is ignored so a bad model cannot loop.
                tool_calls = (
                    getattr(response.choices[0].message, "tool_calls", None)
                    if response.choices else None
                )
                if tool_calls and tools is not None:
                    called = response.choices[0].message
                    messages.append({
                        "role": "assistant",
                        "content": called.content or "",
                        "tool_calls": [
                            {
                                "id": call.id,
                                "type": "function",
                                "function": {
                                    "name": call.function.name,
                                    "arguments": call.function.arguments,
                                },
                            }
                            for call in tool_calls
                        ],
                    })
                    for call in tool_calls:
                        try:
                            arguments = json.loads(call.function.arguments or "{}")
                        except (TypeError, ValueError):
                            arguments = {}
                        result = tools.dispatch(call.function.name, arguments)
                        messages.append({
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": result,
                        })
                    response = await client.chat.completions.create(**request_kwargs)
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
        }

    def shutdown(self):
        """Clean shutdown."""
        self.tts.shutdown()
