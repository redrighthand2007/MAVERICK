from types import SimpleNamespace

import psutil
import pytest

from maverick.agents.hardware import ops
from maverick.agents.hardware.agent import HardwareAgent
from maverick.main import build

GB = 1024 ** 3


@pytest.mark.parametrize("sentence, operation", [
    ("how much ram do i have", "ram"),
    ("do I have empty RAM slots?", "slots"),
    ("is there a free memory slot", "slots"),
    ("what's my battery", "battery"),
    ("what cpu do i have", "cpu"),
    ("how much space is left on D:", "disks"),
    ("show free space on my drives", "disks"),
])
def test_parse_hardware_questions(sentence, operation):
    assert HardwareAgent().parse(sentence).operation == operation


@pytest.mark.parametrize("sentence", [
    "copy the memory dump to D:\\x",   # a file job that mentions memory
    "how big is D:\\games",             # folder size belongs to the files agent
    "rename notes.txt to ideas.txt",
    "tell me a joke",
])
def test_parse_leaves_other_requests_alone(sentence):
    assert HardwareAgent().parse(sentence) is None


def test_extract_finds_drive_letter():
    agent = HardwareAgent()
    assert agent.extract("disks", "free space on d: please").args == {"drive": "D:"}
    assert agent.extract("disks", "free space on my drives").args == {}


def test_ram_message(monkeypatch):
    fake = SimpleNamespace(total=16 * GB, available=4 * GB, percent=75.0)
    monkeypatch.setattr(psutil, "virtual_memory", lambda: fake)
    result = ops.ram()
    assert result.message == "RAM: 16.00 GB total, 12.00 GB in use (75%), 4.00 GB free"


def test_slots_counts_empty_slots(monkeypatch):
    def fake_info(cim_class, fields):
        if cim_class == "Win32_PhysicalMemory":
            return [{"Capacity": 8 * GB, "Speed": 3200, "SMBIOSMemoryType": 26, "DeviceLocator": "DIMM0", "Manufacturer": "Samsung"}]
        return [{"MemoryDevices": 2, "MaxCapacityEx": 64 * 1024 * 1024}]  # KB
    monkeypatch.setattr(ops, "windows_info", fake_info)
    result = ops.slots()
    assert result.data == {"slots": 2, "used": 1, "empty": 1}
    assert "Supports up to 64.00 GB" in result.message
    assert "DIMM0: 8.00 GB DDR4 3200 MHz (Samsung)" in result.message


def test_cpu_message(monkeypatch):
    monkeypatch.setattr(ops, "windows_info", lambda c, f: [{"Name": " Intel Core i7 "}])
    monkeypatch.setattr(psutil, "cpu_count", lambda logical=True: 16 if logical else 10)
    monkeypatch.setattr(psutil, "cpu_percent", lambda interval=None: 12.0)
    assert ops.cpu().message == "CPU: Intel Core i7, 10 cores / 16 threads, currently 12% busy"


@pytest.mark.parametrize("battery, expected", [
    (None, "No battery found. This looks like a desktop PC."),
    (SimpleNamespace(percent=80, power_plugged=True, secsleft=psutil.POWER_TIME_UNLIMITED), "Battery: 80%, plugged in, charging"),
    (SimpleNamespace(percent=100, power_plugged=True, secsleft=psutil.POWER_TIME_UNLIMITED), "Battery: 100%, plugged in, fully charged"),
    (SimpleNamespace(percent=45, power_plugged=False, secsleft=7800), "Battery: 45%, on battery, about 2 h 10 min left"),
])
def test_battery_messages(monkeypatch, battery, expected):
    monkeypatch.setattr(psutil, "sensors_battery", lambda: battery)
    assert ops.battery().message == expected


def test_disks_filter_and_skip_unreadable(monkeypatch):
    parts = [SimpleNamespace(device="C:\\", mountpoint="C:\\"), SimpleNamespace(device="D:\\", mountpoint="D:\\"),
             SimpleNamespace(device="F:\\", mountpoint="F:\\")]
    usage = {"C:\\": SimpleNamespace(total=500 * GB, free=100 * GB, percent=80.0),
             "D:\\": SimpleNamespace(total=200 * GB, free=150 * GB, percent=25.0)}

    def fake_usage(mount):
        if mount not in usage:
            raise PermissionError("no disc in drive")
        return usage[mount]

    monkeypatch.setattr(psutil, "disk_partitions", lambda: parts)
    monkeypatch.setattr(psutil, "disk_usage", fake_usage)
    assert [d["drive"] for d in ops.disks().data["drives"]] == ["C:", "D:"]
    assert ops.disks("d:").message == "Drives:\n  - D: 150.00 GB free of 200.00 GB (25% used)"
    assert not ops.disks("Z:").success


def test_real_pc_ram_and_disks():
    """Runs against this machine for real; read-only."""
    maverick = build()
    assert maverick.handle("how much ram do i have").message.startswith("RAM:")
    assert maverick.handle("how much free space on my drives").message.startswith("Drives:")


def test_hardware_questions_never_ask_for_confirmation():
    assert HardwareAgent.risky == set()
