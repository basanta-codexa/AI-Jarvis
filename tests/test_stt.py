import numpy as np
import pytest
from unittest.mock import Mock

from ai_jarvis.voice import stt


def test_rms_of_silence_is_zero():
    assert stt._rms(np.zeros((480, 1), dtype=np.int16)) == 0.0


def test_rms_of_constant_signal_matches_amplitude():
    block = np.full((480, 1), 1000, dtype=np.int16)
    assert stt._rms(block) == pytest.approx(1000.0, rel=1e-3)


def test_rms_of_empty_block_is_zero():
    assert stt._rms(np.array([], dtype=np.int16).reshape(0, 1)) == 0.0


def test_stt_constructs_and_reports_boolean_availability():
    instance = stt.STT()
    assert isinstance(instance.is_available, bool)
    if not instance.is_available:
        assert instance.unavailable_reason  # always explains why


class FakeStream:
    """Yields scripted sound levels (int16 amplitudes) block by block."""

    def __init__(self, amplitudes):
        self._amplitudes = list(amplitudes)
        self._index = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, block_size):
        amp = self._amplitudes[self._index] if self._index < len(self._amplitudes) else 0
        self._index += 1
        return np.full((block_size, 1), amp, dtype=np.int16), False


def make_stt_instance():
    instance = stt.STT.__new__(stt.STT)   # skip device query — unit test the VAD only
    instance.recognizer = None
    instance.mic_available = True
    instance._unavailable_reason = ""
    instance.last_error = None
    instance.on_speech_start = Mock()
    instance.on_volume = Mock()
    instance._cached_threshold = 1000.0
    return instance


def test_capture_fires_speech_start_and_volume():
    instance = make_stt_instance()
    blocks = [0] * 10 + [2000] * 40 + [0] * 40   # onset, then ~1.2s of silence
    stream = FakeStream(blocks)

    frames = instance._capture_phrase(stream, 1000.0)

    assert frames
    instance.on_speech_start.assert_called_once()
    assert any(call.args[0] > 0.5 for call in instance.on_volume.call_args_list)


def test_capture_waits_for_speech_and_gives_up_quietly(monkeypatch):
    monkeypatch.setattr(stt, "STT_TIMEOUT", 0.15)   # shrink the wait — no real-time delay
    instance = make_stt_instance()
    stream = FakeStream([0] * 50)

    frames = instance._capture_phrase(stream, 1000.0)

    assert frames == []
    instance.on_speech_start.assert_not_called()
