import asyncio
from types import SimpleNamespace

from ai_jarvis.skills.system import SystemSkill
from ai_jarvis.voice.tts import TTS


def test_exit_skill_sets_request_shutdown():
    orchestrator = SimpleNamespace(request_shutdown=False)
    skill = SystemSkill(orchestrator=orchestrator)
    skill.setup()
    command = skill.match("exit")

    result = asyncio.run(skill.execute(command, "exit"))

    assert orchestrator.request_shutdown is True
    assert "Goodbye" in result.response


def test_tts_shutdown_waits_for_pending_speech(monkeypatch):
    spoken = []
    monkeypatch.setattr(TTS, "_check_powershell", staticmethod(lambda: False))
    monkeypatch.setattr(TTS, "_speak_now", lambda self, text: spoken.append(text))
    tts = TTS()

    tts.speak("Goodbye, Sir.")
    tts.shutdown()   # must wait for the goodbye to finish, not cut it off

    assert spoken == ["Goodbye, Sir."]
    assert tts._queue.empty()
