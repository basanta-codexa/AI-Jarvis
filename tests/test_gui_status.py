from types import SimpleNamespace

from ai_jarvis.ui.gui import COLOR_ERROR, COLOR_SUCCESS, COLOR_WARNING, JarvisGUI


class StatusLabel:
    def __init__(self):
        self.options = {}

    def configure(self, **options):
        self.options.update(options)


def test_status_panel_displays_live_subsystem_states():
    values = {
        "AI Provider": StatusLabel(),
        "Speech Output": StatusLabel(),
        "Microphone": StatusLabel(),
        "Vector Memory": StatusLabel(),
    }
    ai_status = StatusLabel()
    gui = SimpleNamespace(
        orch=SimpleNamespace(
            get_status=lambda: {
                "ai": "fallback",
                "tts": "online",
                "stt": "offline",
                "memory": {"vector_memory": "offline"},
            }
        ),
        _status_values=values,
        ai_status=ai_status,
    )

    JarvisGUI._refresh_system_status(gui)

    assert values["AI Provider"].options == {
        "text": "FALLBACK",
        "text_color": COLOR_ERROR,
    }
    assert values["Speech Output"].options == {
        "text": "ONLINE",
        "text_color": COLOR_SUCCESS,
    }
    assert values["Microphone"].options == {
        "text": "OFFLINE",
        "text_color": COLOR_WARNING,
    }
    assert values["Vector Memory"].options == {
        "text": "OFFLINE",
        "text_color": COLOR_WARNING,
    }
    assert ai_status.options["text"] == "FALLBACK"
