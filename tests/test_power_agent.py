import pytest

from maverick.agents.power import ops
from maverick.agents.power.agent import PowerAgent

POWERCFG = """Existing Power Schemes (* Active)
-----------------------------------
Power Scheme GUID: 381b4222-f694-41f0-9685-ff5bb260df2e  (Balanced) *
Power Scheme GUID: e9a42b02-d5df-448d-aa00-03f14749eb61  (Ultimate Performance)
"""


@pytest.mark.parametrize("sentence, operation, wants", [
    ("switch to power saver", "plan", "best power efficiency"),
    ("turn on battery saver", "plan", "best power efficiency"),
    ("use best performance", "plan", "best performance"),
    ("go to balanced power mode", "plan", "balanced"),
    ("what power mode am i on", "plan", ""),
    ("show power plans", "plan", ""),
])
def test_parse_power_modes(sentence, operation, wants):
    intent = PowerAgent().parse(sentence)
    assert intent.operation == operation
    assert ops.match_mode(intent.args["name"]) == wants


@pytest.mark.parametrize("sentence, level", [
    ("set brightness to 40", "40"),
    ("make the screen brighter", "+20"),
    ("dim the screen", "-20"),
    ("full brightness", "100"),
    ("how bright is my screen", ""),
])
def test_parse_brightness(sentence, level):
    assert PowerAgent().parse(sentence).args == {"level": level}


@pytest.mark.parametrize("sentence", ["what's my battery", "is my laptop charging", "how much ram do i have"])
def test_parse_leaves_other_requests_alone(sentence):
    assert PowerAgent().parse(sentence) is None


@pytest.fixture
def fake_windows(monkeypatch):
    """Records every change instead of making it."""
    state = {"mode": "balanced", "commands": [], "brightness": 60}
    monkeypatch.setattr(ops, "run", lambda args: state["commands"].append(args) or POWERCFG)
    monkeypatch.setattr(ops, "current_mode", lambda: state["mode"])
    monkeypatch.setattr(ops, "set_mode", lambda name: state.update(mode=name))
    monkeypatch.setattr(ops, "get_brightness", lambda: state["brightness"])
    monkeypatch.setattr(ops, "powershell", lambda script: state["commands"].append(script) or "")
    return state


def test_show_lists_mode_and_plans(fake_windows):
    message = ops.plan().message
    assert message.startswith("Power mode: balanced")
    assert "  - Balanced  (active)" in message and "  - Ultimate Performance" in message


def test_switch_mode(fake_windows):
    result = ops.plan("switch to power saver")
    assert result.message == "Power mode: balanced -> best power efficiency."
    assert fake_windows["mode"] == "best power efficiency"


def test_a_named_plan_wins_over_modes(fake_windows):
    result = ops.plan("use the ultimate performance plan")
    assert result.message == "Switched to the Ultimate Performance power plan."
    assert ["powercfg", "/setactive", "e9a42b02-d5df-448d-aa00-03f14749eb61"] in fake_windows["commands"]


def test_unknown_mode_lists_choices(fake_windows):
    result = ops.plan("switch power plan")
    assert not result.success and "Ultimate Performance" in result.message


@pytest.mark.parametrize("level, expected", [("40", 40), ("+20", 80), ("-80", 0), ("150", 100)])
def test_brightness_is_kept_between_0_and_100(fake_windows, level, expected):
    assert ops.brightness(level).data == {"brightness": expected}
    assert f"Brightness={expected}" in fake_windows["commands"][-1]


def test_external_monitor_brightness_explains(monkeypatch):
    monkeypatch.setattr(ops, "get_brightness", lambda: None)
    assert "external monitor" in ops.brightness("50").message


def test_real_pc_read_only():
    """Reads the real power mode and plans; changes nothing."""
    assert ops.current_mode() in {*ops.MODES, "unknown"}
    assert ops.plans(), "powercfg should list at least one plan"
