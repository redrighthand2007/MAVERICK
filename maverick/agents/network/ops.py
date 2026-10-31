"""Network adapters: show IP / MAC / Wi-Fi details (anyone); turn an adapter on or off (Administrator)."""
import re
import socket
import subprocess

import psutil

from maverick.core import windows
from maverick.core.agent_base import Result
from maverick.core.safety import SafetyError

FIELD_RE = re.compile(r"^\s*([A-Za-z ()]+?)\s*:\s*(.+?)\s*$")
# Virtual adapters most people never care about.
HIDDEN = ("loopback", "vethernet", "bluetooth network", "teredo", "isatap", "local area connection*")


def wifi_details() -> dict:
    """SSID, signal, band ... from `netsh wlan show interfaces` (empty if there is no Wi-Fi card)."""
    out = subprocess.run(["netsh", "wlan", "show", "interfaces"], capture_output=True, text=True, shell=False,
                         timeout=15, stdin=subprocess.DEVNULL).stdout
    fields = {}
    for line in out.splitlines():
        m = FIELD_RE.match(line)
        if m and m.group(1).strip() not in fields:
            fields[m.group(1).strip()] = m.group(2)
    return fields


def adapters() -> list[dict]:
    stats, addrs = psutil.net_if_stats(), psutil.net_if_addrs()
    found = []
    for name, stat in stats.items():
        if name.lower().startswith(HIDDEN):
            continue
        info = {"name": name, "up": stat.isup, "speed": stat.speed, "ipv4": [], "ipv6": [], "mac": ""}
        for addr in addrs.get(name, []):
            if addr.family == socket.AF_INET:
                info["ipv4"].append(addr.address)
            elif addr.family == socket.AF_INET6 and not addr.address.startswith("fe80"):
                info["ipv6"].append(addr.address.split("%")[0])
            elif addr.family == psutil.AF_LINK:
                info["mac"] = addr.address
        found.append(info)
    return sorted(found, key=lambda a: (not a["up"], a["name"].lower()))


def info() -> Result:
    lines = ["Network adapters:"]
    for a in adapters():
        state = f"connected, {a['speed']} Mbps" if a["up"] else "off / disconnected"
        lines.append(f"  - {a['name']}: {state}")
        if a["ipv4"]:
            lines.append(f"      IPv4: {', '.join(a['ipv4'])}")
        if a["ipv6"]:
            lines.append(f"      IPv6: {', '.join(a['ipv6'])}")
        if a["mac"]:
            lines.append(f"      MAC:  {a['mac']}")
    wifi = wifi_details()
    if wifi.get("SSID"):
        lines.append(f"Wi-Fi: {wifi['SSID']}, signal {wifi.get('Signal', '?')}, {wifi.get('Band', '')} "
                     f"{wifi.get('Radio type', '')}".rstrip())
    elif wifi.get("State"):
        lines.append(f"Wi-Fi: {wifi['State']}")
    return Result(True, "\n".join(lines), {"adapters": adapters(), "wifi": wifi})


def find_adapter(name: str) -> str:
    """'' or 'wifi' -> the Wi-Fi adapter; otherwise the adapter whose name contains the words."""
    names = list(psutil.net_if_stats())
    wanted = name.lower().replace("-", "").replace(" ", "")
    if wanted in ("", "wifi", "wireless", "wlan"):
        wifi_name = wifi_details().get("Name")
        if wifi_name:
            return wifi_name
        wanted = "wifi"
    hits = [n for n in names if wanted in n.lower().replace("-", "").replace(" ", "")]
    if not hits:
        raise SafetyError(f"No network adapter called '{name or 'Wi-Fi'}'. Adapters: {', '.join(names)}")
    return hits[0]


def describe(adapter: str, state: str) -> str:
    name = find_adapter(adapter)
    admin = "" if windows.is_admin() else " (needs Administrator)"
    warning = " You will lose internet through it until it's turned back on." if state == "off" else ""
    return f"Turn {state} the {name} adapter{admin}?{warning}"


def switch(adapter: str, state: str) -> Result:
    name = find_adapter(adapter)
    if not windows.is_admin():
        return Result(False, windows.ADMIN_HINT)
    verb = "Enable-NetAdapter" if state == "on" else "Disable-NetAdapter"
    done = windows.powershell(f"{verb} -Name {windows.quote(name)} -Confirm:$false")
    if done.returncode != 0:
        reason = (done.stderr.strip().splitlines() or ["unknown error"])[0]
        return Result(False, f"Windows refused to turn {state} {name}: {reason}")
    return Result(True, f"Turned {state} {name}.", {"adapter": name, "state": state})
