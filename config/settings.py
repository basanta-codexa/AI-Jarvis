# ──────────────────────────────────────────────
#  AI-JARVIS  •  Configuration & Settings
# ──────────────────────────────────────────────
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# ── Identity ──────────────────────────────────
JARVIS_NAME = "JARVIS"
USER_NAME = os.getenv("USER_NAME", "Sir")

# ── OpenAI / OpenRouter ───────────────────────
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
# Support OpenRouter (sk-or-v1-...) and OpenAI (sk-...)
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL = os.getenv("AI_MODEL", "gpt-3.5-turbo")
AI_SYSTEM_PROMPT = (
    f"You are {JARVIS_NAME}, a helpful, witty, and intelligent personal AI "
    f"assistant inspired by Iron Man's JARVIS. You are talking with {USER_NAME}. "
    "Keep responses concise, helpful, and slightly formal. "
    "When executing commands, confirm them clearly."
)

# ── Voice / TTS ──────────────────────────────
TTS_RATE = 175          # words per minute
TTS_VOLUME = 1.0        # 0.0 – 1.0
TTS_VOICE_INDEX = 1     # 0 = male, 1 = female (system dependent)
STT_TIMEOUT = 5         # seconds to wait for speech
STT_PHRASE_LIMIT = 10   # max seconds per phrase

# ── Memory ───────────────────────────────────
MEMORY_FILE = Path(__file__).resolve().parent.parent / "data" / "memory.json"

# ── GUI ──────────────────────────────────────
WINDOW_TITLE = "J.A.R.V.I.S."
WINDOW_WIDTH = 1000
WINDOW_HEIGHT = 700
THEME = "dark"          # "dark" | "light" | "system"

# Colour palette
COLOR_BG        = "#0a0e1a"
COLOR_SURFACE   = "#111827"
COLOR_ACCENT    = "#00d4ff"
COLOR_ACCENT2   = "#7c3aed"
COLOR_TEXT      = "#e2e8f0"
COLOR_TEXT_DIM  = "#64748b"
COLOR_USER      = "#3b82f6"
COLOR_JARVIS    = "#00d4ff"
COLOR_ERROR     = "#ef4444"
COLOR_SUCCESS   = "#22c55e"

# ── System Info ──────────────────────────────
ENABLE_SYSTEM_INFO = True

# Approved apps / websites (safety list)
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
