# ──────────────────────────────────────────────
#  voice/stt.py  –  Speech‑To‑Text engine
# ──────────────────────────────────────────────
"""
Uses the SpeechRecognition library (Google free API by default).
Falls back gracefully when the microphone or PyAudio is unavailable.
"""
import speech_recognition as sr
from config import settings


class STT:
    """Speech‑to‑text using SpeechRecognition + Google Web Speech API."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.mic_available = self._check_mic()

        # Tune energy threshold for quicker pickup
        self.recognizer.dynamic_energy_threshold = True
        self.recognizer.energy_threshold = 300

        # Reason for unavailability (shown in GUI)
        if not self.mic_available:
            self._unavailable_reason = "PyAudio not installed – mic disabled"
        else:
            self._unavailable_reason = ""

    # ── Public ────────────────────────────────────────────────────────

    def listen(self) -> str | None:
        """
        Record one phrase from the microphone and return the transcript.
        Returns None on error or if no speech detected.
        """
        if not self.mic_available:
            return None

        with sr.Microphone() as source:
            self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
            print("[STT] Listening…", flush=True)
            try:
                audio = self.recognizer.listen(
                    source,
                    timeout=settings.STT_TIMEOUT,
                    phrase_time_limit=settings.STT_PHRASE_LIMIT,
                )
            except sr.WaitTimeoutError:
                return None

        return self._transcribe(audio)

    def transcribe_audio(self, audio_data) -> str | None:
        """Transcribe a pre‑recorded AudioData object."""
        return self._transcribe(audio_data)

    # ── Internal ──────────────────────────────────────────────────────

    def _transcribe(self, audio) -> str | None:
        try:
            text = self.recognizer.recognize_google(audio)
            print(f"[STT] Heard: {text}", flush=True)
            return text
        except sr.UnknownValueError:
            print("[STT] Could not understand audio.", flush=True)
            return None
        except sr.RequestError as e:
            print(f"[STT] API error: {e}", flush=True)
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
