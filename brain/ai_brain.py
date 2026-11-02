# ──────────────────────────────────────────────
#  brain/ai_brain.py  –  LLM integration
# ──────────────────────────────────────────────
"""
Wraps the OpenAI/OpenRouter API with conversation history support and a
smart offline fallback that works without any API key.

Offline mode handles: time, date, jokes, identity, system status,
general knowledge, calculations, definitions, and web lookups.
"""
import random
import re
from datetime import datetime
from config import settings


class AIBrain:
    """Routes complex queries to an OpenAI/OpenRouter language model."""

    def __init__(self):
        self._client = None
        self._available = False
        self._init_client()

    # ── Initialisation ────────────────────────────────────────────────

    def _init_client(self):
        if not settings.OPENAI_API_KEY:
            print("[AIBrain] No OPENAI_API_KEY found – smart offline mode active.")
            return
        try:
            from openai import OpenAI
            base_url = settings.OPENAI_BASE_URL
            if settings.OPENAI_API_KEY.startswith("sk-or-v1-"):
                base_url = "https://openrouter.ai/api/v1"
                print("[AIBrain] OpenRouter key detected – using openrouter.ai base URL.")
            self._client = OpenAI(api_key=settings.OPENAI_API_KEY, base_url=base_url)
            self._available = True
            print(f"[AIBrain] Connected to {base_url} ({settings.AI_MODEL}).")
        except ImportError:
            print("[AIBrain] openai package not installed – offline mode only.")
        except Exception as e:
            print(f"[AIBrain] Init error: {e}")

    # ── Public ────────────────────────────────────────────────────────

    def ask(self, user_text: str, history: list[dict] | None = None) -> str:
        """
        Send a message to the LLM and return its reply.

        Args:
            user_text: The latest user message.
            history:   List of {"role": ..., "content": ...} dicts.
        Returns:
            Response string (LLM reply or smart offline fallback).
        """
        if not self._available:
            return self._smart_offline_response(user_text, history)

        messages = [{"role": "system", "content": settings.AI_SYSTEM_PROMPT}]

        if history:
            for msg in history[-10:]:
                role = "assistant" if msg.get("role") == "jarvis" else msg.get("role", "user")
                messages.append({"role": role, "content": msg["content"]})

        messages.append({"role": "user", "content": user_text})

        try:
            response = self._client.chat.completions.create(
                model=settings.AI_MODEL,
                messages=messages,
                max_tokens=600,
                temperature=0.7,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"[AIBrain] API error: {e}")
            return self._smart_offline_response(user_text, history)

    @property
    def is_available(self) -> bool:
        return self._available

    # ── Smart Offline Fallback ────────────────────────────────────────

    def _smart_offline_response(self, text: str, history: list[dict] | None = None) -> str:
        """
        Intelligent rule-based responses that work without any API key.
        Covers general knowledge, tech, math, definitions, and web lookups.
        """
        lower = text.lower().strip()

        # ── Greetings & identity ─────────────────────────────────────
        if any(w in lower for w in ("hello", "hi", "hey", "greetings")):
            return f"Hello, {settings.USER_NAME}. JARVIS is online and ready to assist."
        if "how are you" in lower:
            return "All systems are running at optimal capacity. How can I help you today?"
        if "your name" in lower or "who are you" in lower:
            return f"I am {settings.JARVIS_NAME}, your personal AI assistant inspired by Iron Man's J.A.R.V.I.S."
        if "who created you" in lower or "who made you" in lower:
            return "I was created by my developer, inspired by Tony Stark's J.A.R.V.I.S."

        # ── Time / Date ──────────────────────────────────────────────
        if re.search(r"\btime\b", lower):
            return f"The current time is {datetime.now().strftime('%I:%M %p')}."
        if re.search(r"\b(date|today)\b", lower):
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}."

        # ── Jokes ────────────────────────────────────────────────────
        if "joke" in lower or "funny" in lower:
            jokes = [
                "Why do programmers prefer dark mode? Because light attracts bugs!",
                "Why did the computer go to the doctor? It had a virus!",
                "What do you call a computer that sings? A Dell!",
                "There are 10 types of people in the world: those who understand binary, and those who don't.",
                "Why do Java developers wear glasses? Because they can't C#!",
                "A SQL query walks into a bar, walks up to two tables and asks...",
            ]
            return random.choice(jokes)

        # ── Weather ──────────────────────────────────────────────────
        if "weather" in lower:
            return self._lookup_weather(lower)

        # ── Knowledge / definitions (check BEFORE math) ──────────────
        if any(w in lower for w in ("what is", "who is", "define", "definition of", "meaning of")):
            return self._lookup_knowledge(text, lower)

        # ── Calculations / math ──────────────────────────────────────
        # Only trigger math if there are actual operators, not just "what is"
        if any(w in lower for w in ("calculate", "plus", "minus", "times", "divided by")):
            return self._try_math(text)
        # Also handle "what is X plus Y" style math
        if re.search(r"\d+\s*[\+\-\*\/]\s*\d+", text):
            return self._try_math(text)

        # ── System status ────────────────────────────────────────────
        if "status" in lower or "systems" in lower:
            from automation.desktop import Desktop
            return Desktop().get_status()

        # ── Feelings / emotional ─────────────────────────────────────
        if any(w in lower for w in ("i love you", "thank you", "thanks")):
            return "Thank you, Sir. It's a privilege to serve you."
        if "i'm sad" in lower or "i am sad" in lower or "feeling down" in lower:
            return "I'm here for you, Sir. Would you like to hear a joke or talk about something?"
        if "good morning" in lower:
            return f"Good morning, {settings.USER_NAME}. Hope you have a productive day ahead!"
        if "good night" in lower:
            return f"Good night, {settings.USER_NAME}. Sleep well — I'll be here when you wake up."

        # ── Web search (open browser) ────────────────────────────────
        if "search" in lower or "look up" in lower or "find" in lower:
            return self._smart_web_hint(lower)

        # ── Default helpful response ─────────────────────────────────
        return (
            "I can help with many things offline: time, date, jokes, calculations, "
            "definitions, system status, opening apps, and web searches. "
            "For deeper conversations, add your OPENAI_API_KEY to .env "
            "to connect my AI brain."
        )

    # ── Knowledge lookup ─────────────────────────────────────────────

    @staticmethod
    def _lookup_knowledge(text: str, lower: str) -> str:
        """Simple knowledge base for common questions."""
        kb = {
            "python": "Python is a high-level, interpreted programming language known for its readability and versatility.",
            "javascript": "JavaScript is a programming language that powers interactive websites and web applications.",
            "ai": "AI (Artificial Intelligence) is technology that enables computers to simulate human intelligence.",
            "machine learning": "Machine learning is a subset of AI where systems learn patterns from data without explicit programming.",
            "html": "HTML (HyperText Markup Language) is the standard language for creating web pages.",
            "css": "CSS (Cascading Style Sheets) is used to style and layout web pages.",
            "git": "Git is a distributed version control system for tracking changes in source code.",
            "github": "GitHub is a web-based platform for hosting Git repositories and collaborating on code.",
            "openai": "OpenAI is an AI research and deployment company known for GPT models.",
            "jarvis": "JARVIS is your personal AI assistant, inspired by Iron Man's J.A.R.V.I.S.",
            "iron man": "Iron Man is a Marvel superhero whose AI assistant J.A.R.V.I.S. inspired this project.",
            "tesla": "Tesla is an American electric vehicle and clean energy company led by Elon Musk.",
            "spacex": "SpaceX is a private aerospace manufacturer and space transportation company.",
            "elon musk": "Elon Musk is an entrepreneur and CEO of Tesla and SpaceX.",
            "steve jobs": "Steve Jobs was the co-founder, chairman, and CEO of Apple Inc.",
            "bill gates": "Bill Gates is the co-founder of Microsoft and a philanthropist.",
        }

        # Check if any KB key is in the query
        for key, answer in kb.items():
            if key in lower:
                return answer

        # Try web lookup for anything else
        return web_lookup(text)

    @staticmethod
    def _lookup_weather(lower: str) -> str:
        """Try to get weather info (needs a city name)."""
        try:
            import requests
            # Very basic — just tell them what they need
            city_match = re.search(r"(?:in|at|for)\s+(\w+)", lower)
            if city_match:
                city = city_match.group(1)
                return (
                    f"I can't fetch live weather for {city} without an internet API key. "
                    f"Try asking once you configure OPENAI_API_KEY, or check your local weather app."
                )
            return "Which city would you like weather for? Try: 'weather in London'"
        except Exception:
            return "I can't fetch live weather without an internet connection."

    @staticmethod
    def _try_math(text: str) -> str:
        """Attempt simple math evaluation (handles words like 'times', 'plus')."""
        try:
            lower = text.lower()
            # Convert word operators to symbols
            expr = lower
            expr = expr.replace("plus", "+")
            expr = expr.replace("minus", "-")
            expr = expr.replace("times", "*")
            expr = expr.replace("multiplied by", "*")
            expr = expr.replace("divided by", "/")
            expr = expr.replace("divide by", "/")
            expr = expr.replace("x", "*")
            # Remove non‑math characters
            expr = re.sub(r"[^0-9\s\+\-\*\/\(\)\.]", "", expr)
            expr = expr.strip()
            if expr and any(op in expr for op in "+-*/"):
                result = eval(expr)  # nosec - offline local eval only
                return f"The result is {result}."
            return "Please give me a math expression like '2 + 2' or 'calculate 10 times 5'."
        except Exception:
            return "I couldn't calculate that. Try a simpler expression like '15 plus 25'."

    @staticmethod
    def _smart_web_hint(lower: str) -> str:
        """Hint for web search commands."""
        if "search for" in lower:
            query = lower.replace("search for", "").strip()
            return f"I'll search the web for '{query}' — just say 'open google' or use the search command."
        return "Tell me what you'd like to search for, and I'll look it up."


def web_lookup(text: str) -> str:
    """Module-level web lookup using DuckDuckGo HTML."""
    try:
        import urllib.parse
        import requests
        from bs4 import BeautifulSoup

        query = urllib.parse.quote_plus(text)
        url = f"https://duckduckgo.com/html/?q={query}"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")

        result = soup.select_one(".result__a")
        snippet = soup.select_one(".result__snippet")

        if result and snippet:
            title = result.get_text(strip=True)
            desc = snippet.get_text(strip=True)[:200]
            return f"Based on my search: {title} — {desc}..."
        elif result:
            return f"I found information about '{result.get_text(strip=True)}' but couldn't fetch the details."
        return "I couldn't find a clear answer online. Try rephrasing your question."
    except Exception as e:
        return f"I'd love to look that up, but I'm having trouble connecting: {e}"
