"""
Speech-To-Text engine using SpeechRecognition + Google Web Speech API.
Graceful fallback when microphone/PyAudio is unavailable.
"""
from __future__ import annotations

import speech_recognition as sr

from ai_jarvis.config.settings import STT_TIMEOUT, STT_PHRASE_LIMIT


class STT:
    """Speech-to-text with mic availability detection."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.mic_available = self._check_mic()
        self._unavailable_reason = ""

        if not self.mic_available:
            self._unavailable_reason = "PyAudio not installed – mic disabled"
        else:
            self.recognizer.dynamic_energy_threshold = True
            self.recognizer.energy_threshold = 300

    def listen(self) -> str | None:
        """Record one phrase and return transcript. Returns None if mic unavailable."""
        if not self.mic_available:
            return None

        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            try:
                audio = self.recognizer.listen(
                    source,
                    timeout=STT_TIMEOUT,
                    phrase_time_limit=STT_PHRASE_LIMIT,
                )
            except sr.WaitTimeoutError:
                return None

        return self._transcribe(audio)

    def _transcribe(self, audio) -> str | None:
        try:
            text = self.recognizer.recognize_google(audio)
            return text
        except sr.UnknownValueError:
            return None
        except sr.RequestError:
            return None

    @staticmethod
    def _check_mic() -> bool:
        try:
            mics = sr.Microphone.list_microphone_names()
            return bool(mics)
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        return self.mic_available

    @property
    def unavailable_reason(self) -> str:
        return self._unavailable_reason
