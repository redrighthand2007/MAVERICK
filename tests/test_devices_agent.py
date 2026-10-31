import subprocess

import pytest

from maverick.agents.devices import ops
from maverick.agents.devices.agent import DevicesAgent
from maverick.core import windows
from maverick.main import build

FAKE = [
    {"name": "USB2.0 HD UVC WebCam", "class": "Camera", "status": "OK", "id": "USB\\VID_3277&PID_0036\\1"},
    {"name": "Realtek(R) Audio", "class": "MEDIA", "status": "OK", "id": "HDAUDIO\\1"},
    {"name": "Speakers (Realtek(R) Audio)", "class": "AudioEndpoint", "status": "Error", "id": "SWD\\MMDEVAPI\\1"},
    {"name": "Microphone Array", "class": "AudioEndpoint", "status": "OK", "id": "SWD\\MMDEVAPI\\2"},
    {"name": "Samsung SSD 980", "class": "DiskDrive", "status": "OK", "id": "SCSI\\DISK\\1"},
]


@pytest.mark.parametrize("sentence, operation, args", [
    ("restart the webcam", "restart", {"name": "webcam"}),
    ("my webcam is stuck, restart it", "restart", {"name": "webcam"}),
    ("show devices with problems", "list", {"query": ""}),
    ("is my gpu working", "list", {"query": "gpu"}),
    ("list usb devices", "list", {"query": "usb"}),
])
def test_parse_device_requests(sentence, operation, args):
    intent = DevicesAgent().parse(sentence)
    assert (intent.operation, intent.args) == (operation, args)


@pytest.mark.parametrize("sentence", ["restart my pc", "kill chrome", "restart the spooler service"])
def test_parse_leaves_other_requests_alone(sentence):
    assert DevicesAgent().parse(sentence) is None


@pytest.fixture
def fake_windows(monkeypatch):
    """Fake devices and a fake pnputil: no real device is ever restarted."""
    ran = []
    monkeypatch.setattr(ops, "all_devices", lambda: [dict(d) for d in FAKE])
    monkeypatch.setattr(windows, "is_admin", lambda: True)
    monkeypatch.setattr(ops.subprocess, "run",
                        lambda args, **kw: ran.append(args) or subprocess.CompletedProcess(args, 0, "", ""))
    return ran


def test_problems_are_listed(fake_windows):
    message = build().handle("show devices with problems").message
    assert "1 with problems" in message and "Speakers (Realtek(R) Audio) [AudioEndpoint]  <-- Error" in message


def test_restart_webcam_asks_then_uses_pnputil(fake_windows):
    maverick = build()
    question = maverick.handle("restart the webcam")
    assert question.message.startswith("Restart USB2.0 HD UVC WebCam?")
    assert maverick.confirm(True).success
    assert fake_windows == [["pnputil", "/restart-device", "USB\\VID_3277&PID_0036\\1"]]


def test_broad_word_picks_the_broken_device(fake_windows):
    question = build().handle("restart the speakers device")
    assert question.message.startswith("Restart Speakers (Realtek(R) Audio)")


def test_disks_are_never_restarted(fake_windows):
    result = build().handle("restart the samsung ssd device")
    assert result.message.startswith("Blocked for safety") and fake_windows == []


def test_no_admin_no_restart(fake_windows, monkeypatch):
    monkeypatch.setattr(windows, "is_admin", lambda: False)
    maverick = build()
    maverick.handle("restart the webcam")
    assert "Run as administrator" in maverick.confirm(True).message
    assert fake_windows == []


def test_real_pc_listing_is_read_only():
    result = ops.list_devices()
    assert result.success and result.data["count"] > 10
