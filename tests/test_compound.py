import asyncio
from unittest.mock import patch

from ai_jarvis.core.plugin_manager import PluginManager
from ai_jarvis.skills.compound import CompoundSkill
from ai_jarvis.skills.memory import MemorySkill
from ai_jarvis.skills.system import SystemSkill
from ai_jarvis.skills.web import WebSkill

import ai_jarvis.skills.system as system_module
import ai_jarvis.skills.web as web_module


def make_manager():
    orch = type("O", (), {})()
    manager = PluginManager(orch)
    orch.plugins = manager
    for cls in (SystemSkill, WebSkill, MemorySkill, CompoundSkill):
        skill = cls(orch)
        skill.setup()
        manager.skills[skill.name] = skill
        for command in skill.commands:
            manager.command_index.append((command, skill))
    return manager


def test_compound_request_routes_to_compound_skill():
    manager = make_manager()
    command, skill = manager.find_skill(
        "open google and search for retirement of dhoni in ipl"
    )
    assert skill.name == "compound"


def test_compound_request_opens_site_and_searches_with_clean_query():
    manager = make_manager()
    command, skill = manager.find_skill(
        "open google and search for retirement of dhoni in ipl"
    )
    urls = []

    with patch.object(system_module.webbrowser, "open", side_effect=urls.append), \
         patch.object(web_module.webbrowser, "open", side_effect=urls.append):
        result = asyncio.run(skill.execute(command,
            "open google and search for retirement of dhoni in ipl"))

    assert result.success is True
    assert urls == [
        "https://www.google.com",
        "https://www.google.com/search?q=retirement+of+dhoni+in+ipl",
    ]
    assert "Opening Google" in result.response
    assert "retirement of dhoni in ipl" in result.response


def test_simple_requests_still_route_to_their_original_skills():
    manager = make_manager()
    assert manager.find_skill("open notepad")[1].name == "system"
    assert manager.find_skill("search for python")[1].name == "web"
