from unittest.mock import Mock

from ai_jarvis.voice.tts import TTS


def make_tts(monkeypatch, speak_now):
    monkeypatch.setattr(TTS, "_check_powershell", staticmethod(lambda: False))
    monkeypatch.setattr(TTS, "_speak_now", speak_now)
    return TTS()


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
