from unittest.mock import Mock

from ai_jarvis.voice.tts import TTS, _speech_timeout


def make_tts(monkeypatch, speak_now):
    monkeypatch.setattr(TTS, "_check_powershell", staticmethod(lambda: False))
    monkeypatch.setattr(TTS, "_speak_now", speak_now)
    return TTS()


def test_speech_timeout_is_generous_enough_not_to_cut_off_speech():
    # The reported failure: 214 words at 175 wpm gave a ~83s timeout and the
    # process was killed mid-sentence. New cap must be well above that.
    text = " ".join(["word"] * 214)
    timeout = _speech_timeout(text)
    assert timeout >= 150
    assert timeout > 214 * 60 / 175  # strictly above the pure speech duration


def test_speech_timeout_has_a_floor_for_short_text():
    assert _speech_timeout("hi") >= 30


def test_on_idle_fires_when_queue_drains(monkeypatch):
    spoken = []
    tts = make_tts(monkeypatch, lambda self, text: spoken.append(text))
    idle = Mock()
    tts.on_idle = idle

    tts.speak("All systems nominal.")
    tts._queue.join()          # worker marks the item done after on_idle

    assert spoken == ["All systems nominal."]
    idle.assert_called_once()
    tts.shutdown()


def test_on_idle_not_fired_for_shutdown_sentinel(monkeypatch):
    tts = make_tts(monkeypatch, lambda self, text: None)
    idle = Mock()
    tts.on_idle = idle

    tts.shutdown()
    tts._queue.join()

    idle.assert_not_called()
