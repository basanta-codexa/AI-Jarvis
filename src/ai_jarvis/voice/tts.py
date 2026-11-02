"""
Text-To-Speech engine using Windows PowerShell System.Speech (built-in, reliable).
Queue-based worker thread so TTS never blocks the GUI.
"""
from __future__ import annotations

import base64
import queue
import subprocess
import threading
import os
from typing import Optional

from ai_jarvis.config.settings import TTS_RATE, TTS_VOLUME, TTS_VOICE_INDEX


class TTS:
    """Text-to-speech with a queue-based worker thread (non-blocking)."""

    def __init__(self):
        self._use_powershell = self._check_powershell()
        self._queue: "queue.Queue[str | None]" = queue.Queue()
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()
        if self._use_powershell:
            print("[TTS] PowerShell System.Speech backend active")
        else:
            print("[TTS] No TTS backend available")

    def _check_powershell(self) -> bool:
        if os.name != "nt":
            return False
        try:
            result = subprocess.run(
                ["powershell", "-Command", "Get-Host"],
                capture_output=True, timeout=3,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            return result.returncode == 0
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        return self._use_powershell

    def speak(self, text: str) -> None:
        """Queue text to be spoken. Non-blocking — returns immediately."""
        if not text or not text.strip():
            return
        self._queue.put(text.strip())

    def _run(self):
        """Worker thread: pulls from queue and speaks each item."""
        while True:
            item = self._queue.get()
            if item is None:  # shutdown signal
                break
            self._speak_now(item)
            self._queue.task_done()

    def _speak_now(self, text: str) -> None:
        """Speak a single item using PowerShell."""
        if self._use_powershell:
            self._speak_powershell(text)

    def _speak_powershell(self, text: str) -> None:
        """Speak using Windows PowerShell System.Speech."""
        try:
            speech_rate = max(-10, min(10, round((TTS_RATE - 175) / 10)))
            text_b64 = base64.b64encode(text.encode("utf-8")).decode("ascii")
            ps_script = f"""
$ErrorActionPreference = 'Stop'
$text = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('{text_b64}'))
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {{
    $voices = @($synth.GetInstalledVoices() | Where-Object {{ $_.Enabled }})
    if ($voices.Count -gt 0) {{
        $voiceIndex = [Math]::Min({TTS_VOICE_INDEX}, $voices.Count - 1)
        $synth.SelectVoice($voices[$voiceIndex].VoiceInfo.Name)
    }}
    $synth.Rate = {speech_rate}
    $synth.Volume = {int(TTS_VOLUME * 100)}
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
                len(text.split()) * 60 / max(TTS_RATE, 1) + 10,
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

    def set_rate(self, rate: int) -> None:
        global TTS_RATE
        TTS_RATE = rate

    def set_volume(self, volume: float) -> None:
        global TTS_VOLUME
        TTS_VOLUME = max(0.0, min(1.0, volume))

    def shutdown(self):
        """Signal the worker thread to stop."""
        self._queue.put(None)
