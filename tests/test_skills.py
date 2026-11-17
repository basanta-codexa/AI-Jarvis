import asyncio

from ai_jarvis.skills.base import BaseSkill, SkillResult
from ai_jarvis.skills.system import SystemSkill, _safe_eval


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


# ── Math skill: safe evaluator (no eval) ──────────────────────────────

def make_math_skill():
    skill = SystemSkill(orchestrator=None)
    skill.setup()
    return skill


def run_math(text):
    skill = make_math_skill()
    command = skill.match(text)
    assert command is not None
    return asyncio.run(skill.execute(command, text))


def test_math_handles_basic_arithmetic():
    result = run_math("calculate 2 plus 2")
    assert result.success is True
    assert result.response == "The result is 4."


def test_math_handles_precedence_and_division():
    result = run_math("calculate (10 - 4) / 2")
    assert result.success is True
    assert result.response == "The result is 3.0."


def test_math_rejects_exponentiation_dos_vector():
    # `eval("9**9**9")` would try to build a ~370-million-digit integer.
    result = run_math("calculate 9**9**9")
    assert result.success is False
    assert "give me a math expression" in result.response


def test_math_rejects_unsupported_operations_and_names():
    for expr in ("9//9", "9%9", "__import__('os')", "2**3**4"):
        try:
            _safe_eval(expr)
            assert False, f"{expr!r} should have been rejected"
        except (ValueError, SyntaxError, TypeError):
            pass


def test_math_caps_literal_size():
    try:
        _safe_eval("10**30")  # rejected as Pow before the literal check
        assert False
    except ValueError:
        pass
    try:
        _safe_eval("1000000000000000")  # bare oversized literal
        assert False
    except ValueError:
        pass


def test_math_division_by_zero_degrades_gracefully():
    result = run_math("calculate 5 / 0")
    assert result.success is False
    assert result.speak is True  # failure here is a user-facing answer, not a crash
