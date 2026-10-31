import json
import subprocess

import pytest

from maverick.agents.accounts import ops
from maverick.agents.accounts.agent import AccountsAgent
from maverick.core import windows
from maverick.main import build


@pytest.mark.parametrize("sentence", ["who has admin on this pc", "am i admin", "list administrators",
                                      "which accounts have admin rights", "is maverick elevated"])
def test_parse_admin_questions(sentence):
    assert AccountsAgent().parse(sentence).operation == "admins"


@pytest.mark.parametrize("sentence", [
    "run as admin",                            # an action, not an audit
    "give tom admin rights",
    'delete "C:\\Users\\Admin\\old notes.txt"',  # "Admin" inside a path is not a question
    "copy C:\\Users\\Admin\\a.txt to D:\\x",
])
def test_parse_leaves_other_requests_alone(sentence):
    assert AccountsAgent().parse(sentence) is None


def test_audit_report(monkeypatch):
    members = [{"Name": "PC\\me", "ObjectClass": "User", "PrincipalSource": 4},
               {"Name": "PC\\Administrator", "ObjectClass": "User", "PrincipalSource": 1},
               {"Name": "PC\\helpdesk", "ObjectClass": "User", "PrincipalSource": 1},
               {"Name": "PC\\olduser", "ObjectClass": "User", "PrincipalSource": 1}]
    users = [{"Name": "me", "Enabled": True}, {"Name": "Administrator", "Enabled": False},
             {"Name": "helpdesk", "Enabled": True}, {"Name": "olduser", "Enabled": True}]

    def fake_powershell(script, timeout=30):
        out = members if "LocalGroupMember" in script else users
        return subprocess.CompletedProcess([], 0, json.dumps(out), "")
    monkeypatch.setattr(windows, "powershell", fake_powershell)
    monkeypatch.setattr(windows, "is_admin", lambda: False)
    monkeypatch.setattr(ops.getpass, "getuser", lambda: "me")

    result = build().handle("who has admin on this pc")
    assert "  - PC\\me (Microsoft account, you)" in result.message
    assert "  - PC\\Administrator (this PC, disabled)" in result.message
    assert "3 active admin accounts" in result.message
    assert result.data["active"] == 3 and not result.data["elevated"]


def test_audit_never_changes_anything():
    assert AccountsAgent.risky == set()


def test_real_pc_audit_is_read_only():
    result = ops.admins()
    assert result.success and result.data["admins"]
