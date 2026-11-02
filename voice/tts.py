# ──────────────────────────────────────────────
#  voice/tts.py  –  Text‑To‑Speech engine
# ──────────────────────────────────────────────
"""
Text‑to‑speech using Windows PowerShell System.Speech (built‑in, reliable).
Falls back to pyttsx3 if PowerShell is unavailable.

Uses a dedicated worker thread with a queue so TTS never blocks the GUI.
"""
import queue
import base64
import subprocess
import threading
import os
import sys

try:
    import pyttsx3
    _PYYTTSX3_AVAILABLE = True
except ImportError:
    _PYYTTSX3_AVAILABLE = False

from config import settings


class TTS:
    """Text‑to‑speech with a queue‑based worker thread (non‑blocking)."""

    def __init__(self):
        self._use_powershell = self._check_powershell()
        self._engine = None
        if not self._use_powershell and _PYYTTSX3_AVAILABLE:
            self._init_pyttsx3()
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    # ── Backend selection ─────────────────────────────────────────────

    def _check_powershell(self) -> bool:
        """Check if PowerShell is available (Windows built‑in)."""
        if os.name != "nt":
            return False
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Host"],
                capture_output=True, timeout=3, creationflags=subprocess.CREATE_NO_WINDOW
            )
            return result.returncode == 0
        except Exception:
            return False

    def _init_pyttsx3(self):
        try:
            self._engine = pyttsx3.init()
            voices = self._engine.getProperty("voices")
            idx = settings.TTS_VOICE_INDEX
            if voices and idx < len(voices):
                self._engine.setProperty("voice", voices[idx].id)
            elif voices:
                self._engine.setProperty("voice", voices[0].id)
            self._engine.setProperty("rate", settings.TTS_RATE)
            self._engine.setProperty("volume", settings.TTS_VOLUME)
        except Exception as e:
            print(f"[TTS] pyttsx3 init error: {e}")
            self._engine = None

    # ── Public API ────────────────────────────────────────────────────

    def speak(self, text: str) -> None:
        """Queue text to be spoken. Non‑blocking — returns immediately."""
        if not text:
            return
        self._queue.put(text)

    def _run(self):
        """Worker thread: pulls from queue and speaks each item."""
        while True:
            item = self._queue.get()
            if item is None:
                break
            self._speak_now(item)
            self._queue.task_done()

    def _speak_now(self, text: str) -> None:
        """Speak a single item using the best available backend."""
        if self._use_powershell:
            self._speak_powershell(text)
        elif self._engine:
            self._speak_pyttsx3(text)
        else:
            print(f"[TTS] No backend available for: {text[:50]}")

    def _speak_powershell(self, text: str) -> None:
        """Speak using Windows PowerShell System.Speech."""
        try:
            speech_rate = max(
                -10, min(10, round((settings.TTS_RATE - 175) / 10))
            )
            text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
            ps_script = f"""
$ErrorActionPreference = 'Stop'
$text = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{text_b64}'))
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
    $voices = @($synth.GetInstalledVoices() | Where-Object {{ $_.Enabled }})
    if ($voices.Count -gt 0) {{
        $voiceIndex = [Math]::Min({settings.TTS_VOICE_INDEX}, $voices.Count - 1)
        $synth.SelectVoice($voices[$voiceIndex].VoiceInfo.Name)
    }}
    $synth.Rate = {speech_rate}
    $synth.Volume = {int(settings.TTS_VOLUME * 100)}
    $synth.Speak($text)
}} finally {{
    $synth.Dispose()
}}
"""
            encoded_script = base64.b64encode(
                ps_script.encode("utf-16le")
            ).decode("ascii")
            timeout = max(
                15,
                len(text.split()) * 60 / max(settings.TTS_RATE, 1) + 10,
            )
            subprocess.run(
                [
                    "powershell", "-NoProfile", "-NonInteractive",
                    "-EncodedCommand", encoded_script,
                ],
                capture_output=True, timeout=timeout,
                creationflags=subprocess.CREATE_NO_WINDOW,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            detail = (e.stderr or e.stdout or b"").decode(
                "utf-8", errors="replace"
            ).strip()
            print(f"[TTS] PowerShell synthesis failed: {detail or e}")
        except Exception as e:
            print(f"[TTS] PowerShell error: {e}")
            # Fall back to pyttsx3 if available
            if self._engine:
                self._speak_pyttsx3(text)

    def _speak_pyttsx3(self, text: str) -> None:
        """Speak using pyttsx3."""
        try:
            self._engine.say(text)
            self._engine.runAndWait()
        except Exception as e:
            print(f"[TTS] pyttsx3 error: {e}")
            try:
                self._init_pyttsx3()
                if self._engine:
                    self._engine.say(text)
                    self._engine.runAndWait()
            except Exception as e2:
                print(f"[TTS] pyttsx3 retry error: {e2}")

    def set_rate(self, rate: int) -> None:
        settings.TTS_RATE = rate
        if self._engine:
            self._engine.setProperty("rate", rate)

    def set_volume(self, volume: float) -> None:
        settings.TTS_VOLUME = max(0.0, min(1.0, volume))
        if self._engine:
            self._engine.setProperty("volume", settings.TTS_VOLUME)

    def list_voices(self) -> list:
        """Return a list of available voice names."""
        if self._engine:
            voices = self._engine.getProperty("voices")
            return [v.name for v in voices] if voices else []
        return ["Microsoft David", "Microsoft Zira"]  # PowerShell defaults

    def shutdown(self):
        """Signal the worker thread to stop."""
        self._queue.put(None)
