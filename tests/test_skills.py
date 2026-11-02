import asyncio

from ai_jarvis.skills.base import BaseSkill, SkillResult


class ExampleSkill(BaseSkill):
    name = "example"

    def setup(self):
        self.register_command(
            r"\bhello\b",
            lambda text: SkillResult(success=True, response=f"Hello: {text}"),
            "Respond to a greeting",
        )


class FailingSkill(BaseSkill):
    name = "failing"

    def setup(self):
        def fail(_text):
            raise RuntimeError("handler failure")

        self.register_command(r"\bfail\b", fail, "Raise a handler error")


def test_skill_matching_is_case_insensitive():
    skill = ExampleSkill(orchestrator=None)
    skill.setup()

    assert skill.match("  HELLO JARVIS ") is not None
    assert skill.match("goodbye") is None


def test_skill_execution_returns_handler_result():
    skill = ExampleSkill(orchestrator=None)
    skill.setup()
    command = skill.match("hello")

    result = asyncio.run(skill.execute(command, "hello there"))

    assert result == SkillResult(success=True, response="Hello: hello there")


def test_skill_execution_surfaces_handler_errors_without_speaking():
    skill = FailingSkill(orchestrator=None)
    skill.setup()
    command = skill.match("fail")

    result = asyncio.run(skill.execute(command, "fail"))

    assert result.success is False
    assert result.response == "Error in failing: handler failure"
    assert result.speak is False
