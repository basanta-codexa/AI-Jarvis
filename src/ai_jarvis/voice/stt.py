"""
Speech-To-Text using sounddevice (microphone) + SpeechRecognition (Google Web Speech).

Why sounddevice instead of PyAudio: PyAudio needs platform-specific PortAudio
binaries and fails to install on many machines. sounddevice ships prebuilt
wheels and exposes the same microphone access more reliably.

How listen() works (kept simple on purpose):
  1. Calibrate — ~0.6s of ambient noise sets a speech threshold.
  2. Wait for speech — blocks above the threshold start recording.
  3. Stop on silence — ~0.8s below threshold ends the phrase.
  4. Transcribe — the captured audio goes to Google Web Speech.
"""
from __future__ import annotations

import time

import numpy as np               # hard dependency — always available
import speech_recognition as sr

from ai_jarvis.config.settings import STT_TIMEOUT, STT_PHRASE_LIMIT

try:
    import sounddevice as sd
    _CAPTURE_AVAILABLE = True
except Exception:                # sounddevice/PortAudio missing (e.g. CI without libportaudio2)
    sd = None
    _CAPTURE_AVAILABLE = False

SAMPLE_RATE = 16000          # Hz — what Google Web Speech expects
BLOCK = 480                  # frames per read (30 ms at 16 kHz)
CALIBRATION_BLOCKS = 20      # ~0.6s of ambient noise
SILENCE_SECONDS = 0.8        # pause that ends a phrase
NOISE_MULTIPLIER = 2.0       # speech must exceed this × room noise (was 3.0)
MIN_PHRASE_SECONDS = 0.3     # shorter captures are treated as accidental clicks


def _rms(block: np.ndarray) -> float:
    """Volume of one audio block (root mean square, int16 scale)."""
    samples = block.astype(np.float32).reshape(-1)
    return float(np.sqrt(np.mean(samples * samples))) if samples.size else 0.0


class STT:
    """Speech-to-text with mic detection and adaptive silence cut-off."""

    def __init__(self):
        self.recognizer = sr.Recognizer()
        self.mic_available, self._unavailable_reason = self._check_mic()
        self.last_error: str | None = None   # surfaced to the UI when recognising fails
        self.on_speech_start = None           # optional callable, fired at voice onset
        self.on_volume = None                 # optional callable(level 0..1) for a live meter
        self._cached_threshold: float | None = None  # reuse room calibration between listens

    # ── Mic handling ──────────────────────────────────────────────

    @staticmethod
    def _check_mic() -> tuple[bool, str]:
        if not _CAPTURE_AVAILABLE:
            return False, "sounddevice/PortAudio not installed"
        try:
            devices = sd.query_devices()
            has_input = any(d.get("max_input_channels", 0) > 0 for d in devices)
            if has_input:
                return True, ""
            return False, "No input device found"
        except Exception as e:
            return False, f"sounddevice unavailable ({e})"

    @property
    def is_available(self) -> bool:
        return self.mic_available

    @property
    def unavailable_reason(self) -> str:
        return self._unavailable_reason

    # ── Listening ─────────────────────────────────────────────────

    def listen(self) -> str | None:
        """Record one spoken phrase and return the transcript (or None)."""
        if not self.mic_available:
            return None
        self.last_error = None

        try:
            with sd.InputStream(
                samplerate=SAMPLE_RATE, channels=1, dtype="int16", blocksize=BLOCK,
            ) as stream:
                threshold = self._calibrate(stream)
                frames = self._capture_phrase(stream, threshold)
        except Exception as e:
            self._cached_threshold = None              # recalibrate next time
            self._unavailable_reason = f"Microphone error ({e})"
            self.last_error = self._unavailable_reason
            print(f"[STT] {self._unavailable_reason}")
            return None

        if not frames:
            return None
        if len(frames) * BLOCK / SAMPLE_RATE < MIN_PHRASE_SECONDS:
            return None                      # too short to be real speech
        raw = np.concatenate(frames).astype(np.int16).tobytes()
        return self._transcribe(sr.AudioData(raw, SAMPLE_RATE, 2))

    def _emit_level(self, volume: float):
        """Forward the mic level (0..1) to the UI, if a callback is set."""
        cb = self.on_volume
        if not cb:
            return
        try:
            cb(min(1.0, max(0.0, volume / 3000.0)))
        except Exception:
            pass

    def _calibrate(self, stream) -> float:
        """Measure the room once and reuse it for the next listens."""
        if self._cached_threshold is not None:
            return self._cached_threshold
        noise = [
            _rms(stream.read(BLOCK)[0]) for _ in range(CALIBRATION_BLOCKS)
        ]
        self._cached_threshold = max(350.0, float(np.median(noise)) * NOISE_MULTIPLIER)
        return self._cached_threshold

    def _capture_phrase(self, stream, threshold: float) -> list[np.ndarray]:
        """Wait for speech to start, then record until silence."""
        frames: list[np.ndarray] = []
        waited = 0.0
        speaking = False
        silence = 0.0
        recorded = 0.0

        while True:
            block = stream.read(BLOCK)[0]
            volume = _rms(block)
            now_delta = BLOCK / SAMPLE_RATE
            self._emit_level(volume)

            if not speaking:
                if volume >= threshold:
                    speaking = True
                    frames.append(block)
                    recorded += now_delta
                    if self.on_speech_start:
                        try:
                            self.on_speech_start()        # let the UI show "hearing you…"
                        except Exception:
                            pass
                elif (waited := waited + now_delta) >= STT_TIMEOUT:
                    self._emit_level(0.0)
                    return []
                continue

            frames.append(block)
            recorded += now_delta
            silence = 0.0 if volume >= threshold else silence + now_delta
            if silence >= SILENCE_SECONDS or recorded >= STT_PHRASE_LIMIT:
                self._emit_level(0.0)
                return frames

    # ── Transcription ─────────────────────────────────────────────

    def _transcribe(self, audio: sr.AudioData) -> str | None:
        try:
            return self.recognizer.recognize_google(audio)
        except sr.UnknownValueError:
            return None                      # speech not understood
        except sr.RequestError as e:
            # Google Web Speech server timeout / unreachable — usually means
            # the connection dropped or the service is slow that moment.
            self.last_error = f"Speech service unreachable ({e}) — check your internet connection."
            print(f"[STT] Speech service error: {e}")
            return None
