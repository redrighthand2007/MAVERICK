"""Devices and drivers: list them and spot problems (anyone); restart one device, e.g. a stuck webcam (Administrator)."""
import json
import subprocess

from maverick.core import windows
from maverick.core.agent_base import Result
from maverick.core.safety import SafetyError

# Plain words -> Windows device classes.
KINDS = {
    "webcam": ["Camera", "Image"], "camera": ["Camera", "Image"], "cam": ["Camera", "Image"],
    "audio": ["AudioEndpoint", "MEDIA"], "sound": ["AudioEndpoint", "MEDIA"], "speaker": ["AudioEndpoint"],
    "speakers": ["AudioEndpoint"], "mic": ["AudioEndpoint"], "microphone": ["AudioEndpoint"],
    "headphones": ["AudioEndpoint"], "bluetooth": ["Bluetooth"], "usb": ["USB", "USBDevice"],
    "mouse": ["Mouse"], "keyboard": ["Keyboard"], "touchpad": ["HIDClass", "Mouse"], "trackpad": ["HIDClass", "Mouse"],
    "gpu": ["Display"], "graphics": ["Display"], "display": ["Display"], "monitor": ["Monitor"],
    "wifi": ["Net"], "network": ["Net"], "ethernet": ["Net"], "printer": ["Printer", "PrintQueue"],
    "fingerprint": ["Biometric"], "battery": ["Battery"],
}
# Restarting these can freeze or crash Windows, or cut off the disk it runs from.
NEVER_RESTART = {"System", "Computer", "Processor", "DiskDrive", "Volume", "VolumeSnapshot", "SCSIAdapter", "HDC",
                 "Firmware", "SoftwareComponent", "SoftwareDevice", "Battery"}


def all_devices() -> list[dict]:
    done = windows.powershell("Get-PnpDevice -PresentOnly | Select-Object FriendlyName, Class, Status, InstanceId "
                              "| ConvertTo-Json -Compress")
    data = json.loads(done.stdout or "[]")
    data = data if isinstance(data, list) else [data]
    return [{"name": d.get("FriendlyName") or "", "class": d.get("Class") or "", "status": d.get("Status") or "",
             "id": d.get("InstanceId") or ""} for d in data if d.get("FriendlyName")]


def matching(query: str, devices: list[dict]) -> list[dict]:
    words = query.lower().split()
    classes = {c for w in words for c in KINDS.get(w, [])}
    if classes:
        return [d for d in devices if d["class"] in classes]
    return [d for d in devices if all(w in d["name"].lower() for w in words)]


def line(device: dict) -> str:
    flag = "" if device["status"] == "OK" else f"  <-- {device['status']}"
    return f"  - {device['name']} [{device['class']}]{flag}"


def list_devices(query: str = "") -> Result:
    devices = all_devices()
    problems = [d for d in devices if d["status"] not in ("OK", "")]
    if query:
        found = matching(query, devices)
        if not found:
            return Result(False, f"No device matches '{query}'.")
        lines = [f"{len(found)} device{'s' if len(found) > 1 else ''} for '{query}':"] + [line(d) for d in found[:30]]
        return Result(True, "\n".join(lines), {"devices": [d["name"] for d in found]})
    lines = [f"{len(devices)} devices connected."]
    if problems:
        lines.append(f"{len(problems)} with problems:")
        lines += [line(d) for d in problems]
    else:
        lines.append("No device reports a problem.")
    lines.append("Ask about one kind, e.g. 'show my webcam' or 'list audio devices'.")
    return Result(True, "\n".join(lines), {"count": len(devices), "problems": [d["name"] for d in problems]})


def plan(name: str) -> dict:
    found = matching(name, all_devices())
    # A class word like "audio" covers many endpoints; prefer the real hardware that has a problem, if any.
    if len(found) > 1:
        broken = [d for d in found if d["status"] not in ("OK", "")]
        found = broken if len(broken) == 1 else found
    if not found:
        raise SafetyError(f"No device matches '{name}'. Try 'show devices' to see them.")
    if len(found) > 1:
        names = ", ".join(d["name"] for d in found[:8])
        raise SafetyError(f"'{name}' matches {len(found)} devices: {names}. Say which one.")
    device = found[0]
    if device["class"] in NEVER_RESTART:
        raise SafetyError(f"{device['name']} is a core part of the PC ({device['class']}); restarting it could crash Windows.")
    return device


def describe(name: str) -> str:
    device = plan(name)
    admin = "" if windows.is_admin() else " (needs Administrator)"
    return f"Restart {device['name']}{admin}? It switches off and on again, like unplugging it."


def restart(name: str) -> Result:
    device = plan(name)
    if not windows.is_admin():
        return Result(False, windows.ADMIN_HINT)
    done = subprocess.run(["pnputil", "/restart-device", device["id"]], capture_output=True, text=True, shell=False,
                          timeout=60, stdin=subprocess.DEVNULL)
    if done.returncode not in (0, 3010):  # 3010: restarted, but Windows wants a reboot to finish
        reason = (done.stdout.strip().splitlines() or ["unknown error"])[-1]
        return Result(False, f"Windows couldn't restart {device['name']}: {reason}")
    extra = " Windows asks for a reboot to finish." if done.returncode == 3010 else ""
    return Result(True, f"Restarted {device['name']}.{extra}", {"device": device["name"]})
