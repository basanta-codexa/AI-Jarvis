"""
AI-JARVIS Configuration
Cinematic Iron Man-inspired color palette and system settings.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent.parent.parent / ".env")


def _env_number(name: str, default, cast, *, minimum=None, maximum=None):
    """Read a numeric setting, falling back to *default* on bad input.

    A typo in .env must never crash the app at import time.
    """
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        value = cast(raw)
    except (TypeError, ValueError):
        print(f"[Settings] Invalid {name}={raw!r}; using {default}")
        return default
    if (minimum is not None and value < minimum) or (
        maximum is not None and value > maximum
    ):
        print(f"[Settings] {name}={value} out of range; using {default}")
        return default
    return value

# ═════════════════════════════════════════════════════════════════════
#  IDENTITY
# ═════════════════════════════════════════════════════════════════════
JARVIS_NAME = "J.A.R.V.I.S."
USER_NAME = os.getenv("USER_NAME", "Sir")
FULL_NAME = "Just A Rather Very Intelligent System"

# ═════════════════════════════════════════════════════════════════════
#  AI / LLM PROVIDERS (OpenAI, OpenRouter, Grok, or Groq)
# ═════════════════════════════════════════════════════════════════════
# Provider: "openai", "openrouter", "grok", or "groq"
_VALID_PROVIDERS = ("openai", "openrouter", "grok", "groq")
_raw_provider = os.getenv("AI_PROVIDER", "openai").strip().lower()
AI_PROVIDER = _raw_provider if _raw_provider in _VALID_PROVIDERS else "openai"
if AI_PROVIDER != _raw_provider:
    print(f"[Settings] Unknown AI_PROVIDER={_raw_provider!r}; using 'openai'")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Base URLs per provider
OPENAI_BASE_URL_OPENROUTER = "https://openrouter.ai/api/v1"
OPENAI_BASE_URL_GROK = "https://api.x.ai/v1"
OPENAI_BASE_URL_GROQ = "https://api.groq.com/openai/v1"
OPENAI_BASE_URL_OPENAI = "https://api.openai.com/v1"

# Resolve base URL based on provider
if AI_PROVIDER == "grok":
    OPENAI_BASE_URL = OPENAI_BASE_URL_GROK
elif AI_PROVIDER == "groq":
    OPENAI_BASE_URL = OPENAI_BASE_URL_GROQ
elif AI_PROVIDER == "openrouter":
    OPENAI_BASE_URL = OPENAI_BASE_URL_OPENROUTER
else:
    OPENAI_BASE_URL = OPENAI_BASE_URL_OPENAI

AI_MODEL = os.getenv("AI_MODEL", "gpt-3.5-turbo")
AI_TEMPERATURE = _env_number("AI_TEMPERATURE", 0.7, float, minimum=0.0, maximum=2.0)
AI_MAX_TOKENS = _env_number("AI_MAX_TOKENS", 600, int, minimum=1)
AI_REQUEST_TIMEOUT = _env_number("AI_REQUEST_TIMEOUT", 30.0, float, minimum=1.0)
AI_MAX_RETRIES = _env_number("AI_MAX_RETRIES", 1, int, minimum=0)

# ═════════════════════════════════════════════════════════════════════
#  CINEMATIC COLOR PALETTE (Iron Man / Holographic)
# ═════════════════════════════════════════════════════════════════════
# Backgrounds
COLOR_BG_DEEP = "#05070a"        # Almost black - deep space
COLOR_BG = "#0a0e1a"             # Main dark background
COLOR_BG_SURFACE = "#111827"     # Raised surface
COLOR_BG_GLASS = "#0f172a"       # Glassmorphism panels

# Accents (Holographic blue/cyan)
COLOR_ACCENT = "#00d4ff"         # Primary holographic cyan
COLOR_ACCENT_GLOW = "#00f0ff"    # Brighter glow
COLOR_ACCENT_DIM = "#006b8f"     # Dimmed accent
COLOR_ACCENT_PURPLE = "#7c3aed"  # Secondary purple accent
COLOR_ACCENT_RED = "#ef4444"     # Alert / listening red

# Text
COLOR_TEXT_PRIMARY = "#e2e8f0"   # Main text
COLOR_TEXT_SECONDARY = "#94a3b8" # Dim text
COLOR_TEXT_DIM = "#64748b"       # Very dim
COLOR_TEXT_ACCENT = "#00d4ff"    # Accent-colored text

# Status colors
COLOR_SUCCESS = "#22c55e"        # Green - online
COLOR_WARNING = "#f59e0b"        # Amber - standby
COLOR_ERROR = "#ef4444"          # Red - offline/error
COLOR_LISTENING = "#00d4ff"      # Cyan - active listening

# ═════════════════════════════════════════════════════════════════════
#  VOICE / TTS
# ═════════════════════════════════════════════════════════════════════
TTS_RATE = 175          # words per minute
TTS_VOLUME = 1.0        # 0.0 – 1.0
TTS_VOICE_INDEX = 1     # System dependent
STT_TIMEOUT = 5         # seconds to wait for speech
STT_PHRASE_LIMIT = 10   # max seconds per phrase

# ═════════════════════════════════════════════════════════════════════
#  MEMORY
# ═════════════════════════════════════════════════════════════════════
MEMORY_DIR = Path(__file__).resolve().parent.parent.parent.parent / "data"
VECTOR_MEMORY_ENABLED = True

# ═════════════════════════════════════════════════════════════════════
#  GUI
# ═════════════════════════════════════════════════════════════════════
WINDOW_TITLE = "J.A.R.V.I.S. — Neural Interface"
WINDOW_WIDTH = 1200
WINDOW_HEIGHT = 800
THEME = "dark"
FPS = 60
ANIMATION_SPEED = 1.0

# Typography
FONT_HEADER = ("Segoe UI", 24, "bold")
FONT_SUBHEADER = ("Segoe UI", 14, "bold")
FONT_MONO = ("Consolas", 12)
FONT_MONO_SMALL = ("Consolas", 10)
FONT_UI = ("Segoe UI", 11)

# ═════════════════════════════════════════════════════════════════════
#  APPROVED APPS / WEBSITES (Safety whitelist)
# ═════════════════════════════════════════════════════════════════════
APPROVED_APPS = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "paint": "mspaint.exe",
    "browser": "start chrome",
    "explorer": "explorer.exe",
    "vs code": "code",
    "task manager": "taskmgr.exe",
    "control panel": "control",
    "command prompt": "cmd.exe",
    "powershell": "powershell",
}

APPROVED_WEBSITES = {
    "google": "https://www.google.com",
    "youtube": "https://www.youtube.com",
    "github": "https://www.github.com",
    "wikipedia": "https://www.wikipedia.org",
    "stackoverflow": "https://stackoverflow.com",
    "reddit": "https://www.reddit.com",
    "twitter": "https://twitter.com",
    "linkedin": "https://www.linkedin.com",
}

# ═════════════════════════════════════════════════════════════════════
#  SYSTEM
# ═════════════════════════════════════════════════════════════════════
ENABLE_SYSTEM_INFO = True
ENABLE_VECTOR_MEMORY = True
LOG_LEVEL = "INFO"
