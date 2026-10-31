"""Read-only questions about this PC. Nothing here changes anything."""
import json
import subprocess

import psutil

from maverick.core.agent_base import Result
from maverick.core.units import human_size

# Windows reports the RAM generation as a number (SMBIOS memory type).
RAM_TYPES = {20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 27: "LPDDR", 28: "LPDDR2",
             29: "LPDDR3", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5"}


def windows_info(cim_class: str, fields: str) -> list[dict]:
    """Ask Windows (WMI/CIM) for hardware details psutil doesn't have, e.g. RAM slots and the CPU's name."""
    command = f"Get-CimInstance {cim_class} | Select-Object {fields} | ConvertTo-Json -Compress"
    out = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                         capture_output=True, text=True, timeout=30, check=True).stdout.strip()
    if not out:
        return []
    data = json.loads(out)
    return data if isinstance(data, list) else [data]  # one item comes back as an object, not a list


def ram() -> Result:
    mem = psutil.virtual_memory()
    used = mem.total - mem.available
    return Result(True, f"RAM: {human_size(mem.total)} total, {human_size(used)} in use ({mem.percent:.0f}%), "
                        f"{human_size(mem.available)} free",
                  {"total": mem.total, "used": used, "free": mem.available, "percent": mem.percent})


def slots() -> Result:
    sticks = windows_info("Win32_PhysicalMemory", "Capacity,Speed,SMBIOSMemoryType,DeviceLocator,Manufacturer")
    boards = windows_info("Win32_PhysicalMemoryArray", "MemoryDevices,MaxCapacityEx")
    total_slots = sum(b.get("MemoryDevices") or 0 for b in boards) or len(sticks)
    empty = max(total_slots - len(sticks), 0)
    max_bytes = sum(b.get("MaxCapacityEx") or 0 for b in boards) * 1024  # Windows reports this in KB

    lines = [f"RAM slots: {total_slots} total, {len(sticks)} used, {empty} empty."]
    if max_bytes:
        lines[0] += f" Supports up to {human_size(max_bytes)}."
    for stick in sticks:
        kind = RAM_TYPES.get(stick.get("SMBIOSMemoryType"), "RAM")
        maker = (stick.get("Manufacturer") or "").strip()
        lines.append(f"  - {stick.get('DeviceLocator', 'slot')}: {human_size(stick.get('Capacity') or 0)} {kind} "
                     f"{stick.get('Speed') or '?'} MHz" + (f" ({maker})" if maker else ""))
    return Result(True, "\n".join(lines), {"slots": total_slots, "used": len(sticks), "empty": empty})


def cpu() -> Result:
    name = next((p.get("Name", "").strip() for p in windows_info("Win32_Processor", "Name")), "Unknown CPU")
    cores, threads = psutil.cpu_count(logical=False), psutil.cpu_count(logical=True)
    usage = psutil.cpu_percent(interval=0.5)  # measured over half a second
    return Result(True, f"CPU: {name}, {cores} cores / {threads} threads, currently {usage:.0f}% busy",
                  {"name": name, "cores": cores, "threads": threads, "usage": usage})


def battery() -> Result:
    bat = psutil.sensors_battery()
    if bat is None:
        return Result(True, "No battery found. This looks like a desktop PC.", {"present": False})
    if bat.power_plugged:
        state = "plugged in" + (", fully charged" if bat.percent >= 100 else ", charging")
    elif bat.secsleft not in (psutil.POWER_TIME_UNLIMITED, psutil.POWER_TIME_UNKNOWN):
        hours, minutes = divmod(bat.secsleft // 60, 60)
        state = f"on battery, about {hours} h {minutes} min left"
    else:
        state = "on battery"
    return Result(True, f"Battery: {bat.percent:.0f}%, {state}",
                  {"present": True, "percent": bat.percent, "plugged": bat.power_plugged})


def disks(drive: str = "") -> Result:
    wanted = drive.rstrip(":\\/").upper()
    lines, found = [], []
    for part in psutil.disk_partitions():
        letter = part.device.rstrip(":\\/").upper()
        if wanted and letter != wanted:
            continue
        try:
            usage = psutil.disk_usage(part.mountpoint)
        except (PermissionError, OSError):
            continue  # e.g. an empty card reader or DVD drive
        found.append({"drive": f"{letter}:", "total": usage.total, "free": usage.free})
        lines.append(f"  - {letter}: {human_size(usage.free)} free of {human_size(usage.total)} ({usage.percent:.0f}% used)")
    if not found:
        return Result(False, f"Drive {wanted}: was not found." if wanted else "No drives found.")
    return Result(True, "Drives:\n" + "\n".join(lines), {"drives": found})
