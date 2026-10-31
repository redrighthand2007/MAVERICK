import subprocess

import pytest

from maverick.agents.services import ops
from maverick.agents.services.agent import ServicesAgent
from maverick.core import windows
from maverick.main import build

FAKE = [
    {"name": "Spooler", "display": "Print Spooler", "status": "running", "start": "automatic"},
    {"name": "wuauserv", "display": "Windows Update", "status": "stopped", "start": "manual"},
    {"name": "XblAuthManager", "display": "Xbox Live Auth Manager", "status": "stopped", "start": "manual"},
    {"name": "XboxNetApiSvc", "display": "Xbox Live Networking Service", "status": "stopped", "start": "manual"},
    {"name": "WinDefend", "display": "Microsoft Defender Antivirus Service", "status": "running", "start": "automatic"},
]


@pytest.mark.parametrize("sentence, operation, args", [
    ("is the print spooler running", "list", {"query": "print spooler"}),
    ("show running services", "list", {"query": ""}),
    ("restart the spooler service", "change", {"name": "spooler print", "action": "restart"}),
    ("stop the windows update service", "change", {"name": "windows update", "action": "stop"}),
    ("enable the spooler service at boot", "change", {"name": "spooler print", "action": "enable"}),
    ("disable the xbox services", "change", {"name": "xbox", "action": "disable"}),
])
def test_parse_service_requests(sentence, operation, args):
    intent = ServicesAgent().parse(sentence)
    assert (intent.operation, intent.args) == (operation, args)


@pytest.mark.parametrize("sentence", ["kill chrome", "start notepad", "what cpu do i have"])
def test_parse_leaves_other_requests_alone(sentence):
    assert ServicesAgent().parse(sentence) is None


@pytest.fixture
def fake_windows(monkeypatch):
    """Fake services and a fake PowerShell, so no real service is ever touched."""
    ran = []
    monkeypatch.setattr(ops, "all_services", lambda: [dict(s) for s in FAKE])
    monkeypatch.setattr(windows, "is_admin", lambda: True)
    monkeypatch.setattr(windows, "powershell",
                        lambda script, timeout=30: ran.append(script) or subprocess.CompletedProcess([], 0, "", ""))
    return ran


def test_change_asks_first_then_runs(fake_windows):
    maverick = build()
    question = maverick.handle("restart the spooler service")
    assert question.message == "Restart the Print Spooler service (Spooler, now running)?"
    assert maverick.confirm(True).success
    assert fake_windows == ["Restart-Service -Name 'Spooler'"]


def test_enable_at_boot_sets_automatic(fake_windows):
    maverick = build()
    maverick.handle("enable the windows update service at boot")
    maverick.confirm(True)
    assert fake_windows == ["Set-Service -Name 'wuauserv' -StartupType Automatic"]


def test_core_services_are_never_stopped(fake_windows):
    result = build().handle("stop the microsoft defender antivirus service")
    assert result.message.startswith("Blocked for safety") and "core Windows service" in result.message
    assert fake_windows == []


def test_ambiguous_name_asks_which(fake_windows):
    result = build().handle("disable the xbox services")
    assert "matches 2 services" in result.message and fake_windows == []


def test_without_admin_nothing_runs(fake_windows, monkeypatch):
    monkeypatch.setattr(windows, "is_admin", lambda: False)
    maverick = build()
    assert maverick.handle("restart the spooler service").message.endswith("(needs Administrator)?")
    result = maverick.confirm(True)
    assert not result.success and "Run as administrator" in result.message
    assert fake_windows == []


def test_names_are_quoted_for_powershell():
    assert windows.quote("a'; Remove-Item C:\\ -Recurse; '") == "'a''; Remove-Item C:\\ -Recurse; '''"


def test_real_pc_listing_is_read_only():
    result = ops.list_services()
    assert result.success and result.data["total"] > 50
    assert build().handle("is the print spooler running").success
