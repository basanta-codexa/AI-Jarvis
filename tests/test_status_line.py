from ai_jarvis.ui.gui import status_line


def make_status(ai="offline", stt="offline", vector="offline"):
    return {
        "ai": ai,
        "stt": stt,
        "memory": {"vector_memory": vector},
    }


def test_status_line_reports_online_ai_and_available_subsystems():
    assert status_line(make_status("online", "online", "online")) == "Online · mic ready · memory on"


def test_status_line_marks_configured_ai_as_unverified():
    line = status_line(make_status("configured"))
    assert line.startswith("Key set (unverified)")
    assert not line.startswith("Online")


def test_status_line_reports_verified_online_ai():
    assert status_line(make_status("online")).startswith("Online")


def test_status_line_reports_offline_when_provider_unavailable():
    assert status_line(make_status("fallback")).startswith("Offline mode")
    assert status_line(make_status("offline")).startswith("Offline mode")


def test_status_line_notes_missing_mic_and_basic_memory():
    line = status_line(make_status("offline", "offline", "offline"))
    assert "no mic" in line
    assert "memory basic" in line
