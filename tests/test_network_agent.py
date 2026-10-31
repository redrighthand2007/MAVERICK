import subprocess

import pytest

from maverick.agents.network import ops
from maverick.agents.network.agent import NetworkAgent
from maverick.core import windows
from maverick.main import build


@pytest.mark.parametrize("sentence, operation, args", [
    ("what's my ip address", "info", {}),
    ("which wifi am i connected to", "info", {}),
    ("show network adapters", "info", {}),
    ("turn off wifi", "wifi", {"adapter": "wifi", "state": "off"}),
    ("turn on wi-fi", "wifi", {"adapter": "wifi", "state": "on"}),
    ("disable the ethernet adapter", "wifi", {"adapter": "ethernet", "state": "off"}),
])
def test_parse_network_requests(sentence, operation, args):
    intent = NetworkAgent().parse(sentence)
    assert (intent.operation, intent.args) == (operation, args)


@pytest.mark.parametrize("sentence", ["connect to wifi", "turn bluetooth on", "kill chrome", "show running services"])
def test_parse_leaves_other_requests_alone(sentence):
    assert NetworkAgent().parse(sentence) is None


@pytest.fixture
def fake_windows(monkeypatch):
    """A fake Wi-Fi card and a fake PowerShell: your real network is never switched off."""
    ran = []
    monkeypatch.setattr(ops, "wifi_details", lambda: {"Name": "Wi-Fi", "SSID": "home", "Signal": "90%"})
    monkeypatch.setattr(ops.psutil, "net_if_stats", lambda: {"Wi-Fi": None, "Ethernet 2": None})
    monkeypatch.setattr(windows, "is_admin", lambda: True)
    monkeypatch.setattr(windows, "powershell",
                        lambda script, timeout=30: ran.append(script) or subprocess.CompletedProcess([], 0, "", ""))
    return ran


def test_turn_off_wifi_warns_asks_and_runs(fake_windows):
    maverick = build()
    question = maverick.handle("turn off wifi")
    assert question.data.get("confirm") and "lose internet" in question.message
    assert maverick.confirm(True).success
    assert fake_windows == ["Disable-NetAdapter -Name 'Wi-Fi' -Confirm:$false"]


def test_adapter_found_by_part_of_its_name(fake_windows):
    maverick = build()
    maverick.handle("turn on the ethernet adapter")
    maverick.confirm(True)
    assert fake_windows == ["Enable-NetAdapter -Name 'Ethernet 2' -Confirm:$false"]


def test_unknown_adapter_is_refused(fake_windows):
    result = build().handle("disable the lan adapter")
    assert result.message.startswith("Blocked for safety") and fake_windows == []


def test_no_admin_no_change(fake_windows, monkeypatch):
    monkeypatch.setattr(windows, "is_admin", lambda: False)
    maverick = build()
    maverick.handle("turn off wifi")
    assert "Run as administrator" in maverick.confirm(True).message
    assert fake_windows == []


def test_real_pc_info_is_read_only():
    result = build().handle("what's my ip address")
    assert result.success and result.message.startswith("Network adapters:")
