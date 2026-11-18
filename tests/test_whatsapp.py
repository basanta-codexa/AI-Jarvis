import asyncio
from types import SimpleNamespace

from ai_jarvis.core.plugin_manager import PluginManager
from ai_jarvis.skills.memory import MemorySkill
from ai_jarvis.skills.system import SystemSkill
from ai_jarvis.skills.web import WebSkill
from ai_jarvis.skills.whatsapp import WhatsAppSkill


class FakeController:
    def __init__(self):
        self.calls = []

    def open(self):
        self.calls.append(("open",))

    def find_chat(self, name):
        self.calls.append(("find", name))

    def send_message(self, message):
        self.calls.append(("send", message))

    def close(self):
        self.calls.append(("close",))


def make_manager():
    controller = FakeController()
    orch = SimpleNamespace(whatsapp_controller=controller)
    manager = PluginManager(orch)
    orch.plugins = manager
    for cls in (SystemSkill, WebSkill, MemorySkill, WhatsAppSkill):
        skill = cls(orch)
        skill.setup()
        manager.skills[skill.name] = skill
        for command in skill.commands:
            manager.command_index.append((command, skill))
    return manager, controller


def run(manager, text):
    command, skill = manager.find_skill(text)
    return skill.name, asyncio.run(skill.execute(command, text))


def test_whatsapp_commands_route_correctly():
    manager, _ = make_manager()
    assert run(manager, "open whatsapp")[0] == "whatsapp"
    assert run(manager, "find siba prasada padhi's chat")[0] == "whatsapp"
    assert run(manager, "send a message hello")[0] == "whatsapp"
    assert run(manager, "close the whatsapp")[0] == "whatsapp"


def test_full_whatsapp_conversation_flow():
    manager, ctrl = make_manager()

    _, opened = run(manager, "open whatsapp")
    assert opened.success is True
    assert "Opening WhatsApp" in opened.response

    _, found = run(manager, "find siba prasada padhi's chat")
    assert found.success is True
    assert "Found siba prasada padhi's chat" in found.response
    assert "warn them" in found.response     # a little humour

    _, sent = run(manager, "send a message hello , good morning")
    assert sent.success is True
    assert "Message sent to siba prasada padhi" in sent.response

    _, closed = run(manager, "close the whatsapp")
    assert closed.success is True
    assert "closed" in closed.response

    assert ctrl.calls == [
        ("open",),
        ("find", "siba prasada padhi"),
        ("send", "hello, good morning"),
        ("close",),
    ]


def test_send_without_finding_a_chat_is_rejected():
    manager, ctrl = make_manager()
    _, result = run(manager, "send a message hello there")
    assert result.success is False
    assert "Mention a name first" in result.response
    assert ctrl.calls == []


def test_send_with_recipient_finds_chat_then_sends():
    manager, ctrl = make_manager()
    skill_name, result = run(manager, "send a good morning message to maheswar")
    assert skill_name == "whatsapp"
    assert result.success is True
    assert "Message sent to maheswar" in result.response
    assert ctrl.calls == [("find", "maheswar"), ("send", "good morning")]


def test_send_various_natural_phrasings():
    manager, ctrl = make_manager()
    run(manager, "message maheswar good morning")
    assert ctrl.calls == [("find", "maheswar"), ("send", "good morning")]

    manager, ctrl = make_manager()
    run(manager, "send hello there")
    assert ctrl.calls == []  # no recipient and no prior chat — safely rejected


def test_existing_skills_still_route_normally():
    manager, _ = make_manager()
    assert run(manager, "open notepad")[0] == "system"
    assert run(manager, "search for python")[0] == "web"
