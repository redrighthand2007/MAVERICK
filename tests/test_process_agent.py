import os
import subprocess
import sys

import psutil
import pytest

from maverick.agents.process import ops
from maverick.agents.process.agent import ProcessAgent, target_name
from maverick.main import build


@pytest.mark.parametrize("sentence, operation", [
    ("show running processes", "list"),
    ("which programs use the most memory", "list"),
    ("what started chrome", "origin"),
    ("why is code.exe running", "origin"),
    ("who launched powershell", "origin"),
    ("what did explorer start", "children"),
    ("show children of pid 4", "children"),
])
def test_parse_process_questions(sentence, operation):
    assert ProcessAgent().parse(sentence).operation == operation


@pytest.mark.parametrize("sentence", [
    "am i running out of ram",      # hardware, not a process
    "how much ram do i have",
    "copy notes.txt to D:\\backup",
])
def test_parse_leaves_other_requests_alone(sentence):
    assert ProcessAgent().parse(sentence) is None


@pytest.mark.parametrize("sentence, name", [
    ("what started chrome", "chrome"),
    ("why is code.exe running", "code.exe"),
    ("show children of pid 1234", "1234"),
    ("who is the parent of node.exe", "node.exe"),
])
def test_target_name(sentence, name):
    assert target_name(sentence) == name


def test_list_sorts_by_cpu_when_asked():
    agent = ProcessAgent()
    assert agent.extract("list", "which app is hogging the cpu").args == {"sort": "cpu"}
    assert agent.extract("list", "what is eating my memory").args == {"sort": "memory"}


def test_origin_without_a_name_asks_for_it():
    assert ProcessAgent().extract("origin", "what started it").missing == ["program name"]


def test_top_groups_copies_of_the_same_program():
    result = ops.top("memory", limit=50)
    names = [p["name"] for p in result.data["programs"]]
    assert len(names) == len(set(names))  # chrome.exe x18 appears once
    rams = [p["ram"] for p in result.data["programs"]]
    assert rams == sorted(rams, reverse=True)


def test_origin_of_this_test_run_finds_its_parent():
    """pytest is running inside python.exe right now, so its parent chain is real."""
    me = psutil.Process(os.getpid())
    result = ops.origin(str(me.pid))
    assert result.success
    assert result.message.startswith(f"{me.name()} (PID {me.pid})")


def test_unknown_program_is_reported():
    result = ops.origin("definitely-not-running-xyz")
    assert not result.success and "No running program" in result.message


def test_real_pc_list_through_maverick():
    assert build().handle("show running processes").message.startswith("Top ")


def test_only_ending_a_program_asks_for_confirmation():
    assert ProcessAgent.risky == {"end"}


@pytest.mark.parametrize("sentence, name", [
    ("kill chrome", "chrome"),
    ("close notepad please", "notepad"),
    ("force close code.exe", "code.exe"),
    ("end pid 1234", "1234"),
])
def test_parse_end_requests(sentence, name):
    intent = ProcessAgent().parse(sentence)
    assert (intent.operation, intent.args) == ("end", {"name": name})


@pytest.mark.parametrize("sentence", [
    "stop the print spooler service",  # services agent
    "stop watching my downloads",      # background jobs
    "turn off wifi",
])
def test_end_leaves_other_agents_alone(sentence):
    intent = ProcessAgent().parse(sentence)
    assert intent is None or intent.operation != "end"


def test_end_without_a_name_asks_for_it():
    assert ProcessAgent().parse("close it").missing == ["program name"]


@pytest.mark.parametrize("name", ["svchost", "explorer.exe", "csrss"])
def test_windows_processes_are_never_ended(name):
    result = build().handle(f"kill {name}")
    assert result.message.startswith("Blocked for safety")


def test_maverick_never_ends_itself():
    me = psutil.Process()
    result = build().handle(f"kill pid {me.pid}")
    assert "MAVERICK itself" in result.message


def test_heaviest_skips_protected_programs(monkeypatch):
    fake = ops.Result(True, "", {"programs": [{"name": "svchost.exe"}, {"name": "definitely-not-running-xyz.exe"}]})
    monkeypatch.setattr(ops, "top", lambda sort, limit=50: fake)
    assert ops.heaviest() == ""  # svchost is protected and the other isn't running


def test_end_a_real_program_after_yes():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        maverick = build()
        question = maverick.handle(f"kill pid {child.pid}")
        assert question.data.get("confirm"), question.message
        assert question.message.startswith("End python")
        result = maverick.confirm(True)
        assert result.success, result.message
        assert child.wait(timeout=5) is not None
    finally:
        if child.poll() is None:
            child.kill()


def test_saying_no_keeps_the_program_running():
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        maverick = build()
        maverick.handle(f"kill pid {child.pid}")
        assert not maverick.confirm(False).success
        assert child.poll() is None
    finally:
        child.kill()


def test_end_the_heaviest_hunts_by_cpu_or_ram(monkeypatch):
    asked = []
    monkeypatch.setattr(ops, "heaviest", lambda sort="memory": asked.append(sort) or "notepad.exe")
    agent = ProcessAgent()
    assert agent.parse("kill whatever uses the most cpu").args == {"name": "notepad.exe"}
    assert agent.parse("end the biggest program").args == {"name": "notepad.exe"}
    assert asked == ["cpu", "memory"]


@pytest.mark.parametrize("sentence, operation, args", [
    ("which apps are not responding", "hung", {"end": False}),
    ("my pc is frozen", "hung", {"end": False}),
    ("end frozen apps", "hung", {"end": True}),
    ("force close everything that's not responding", "hung", {"end": True}),
    ("kill excel it is stuck", "end", {"name": "excel"}),  # names one program, so only that one
])
def test_parse_frozen_app_requests(sentence, operation, args):
    intent = ProcessAgent().parse(sentence)
    assert (intent.operation, intent.args) == (operation, args)


def test_only_ending_frozen_apps_is_risky():
    agent = ProcessAgent()
    assert not agent.is_risky(agent.parse("show frozen apps"))
    assert agent.is_risky(agent.parse("end frozen apps"))


def test_nothing_frozen():
    # On a healthy PC this is the real answer; it only reads window states.
    result = ops.hung()
    assert result.success


def test_end_frozen_apps_after_yes(monkeypatch):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        monkeypatch.setattr(ops, "hung_windows", lambda: [(child.pid, "Untitled - Frozen")])
        maverick = build()
        listed = maverick.handle("which apps are not responding")
        assert f"(PID {child.pid}): \"Untitled - Frozen\"" in listed.message
        question = maverick.handle("end frozen apps")
        assert question.data.get("confirm") and "Untitled - Frozen" in question.message
        result = maverick.confirm(True)
        assert result.success, result.message
        assert child.wait(timeout=5) is not None
    finally:
        if child.poll() is None:
            child.kill()


def test_frozen_windows_parts_are_never_ended(monkeypatch):
    explorer = next(p for p in psutil.process_iter(["name"]) if (p.info["name"] or "").lower() == "explorer.exe")
    monkeypatch.setattr(ops, "hung_windows", lambda: [(explorer.pid, "File Explorer")])
    result = build().handle("end frozen apps")
    assert result.message.startswith("Blocked for safety")
