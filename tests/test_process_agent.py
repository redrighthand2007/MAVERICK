import os

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
