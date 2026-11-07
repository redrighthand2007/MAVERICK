"""Read-only questions about this PC. Nothing here changes anything on the PC.

The one thing written is MAVERICK's own disk history (~/.maverick/disk_history.tsv), for the 8.24 forecast.
"""
import json
import subprocess
import time
from pathlib import Path

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
    record_disks()  # every look at the drives also feeds the 8.24 forecast
    return Result(True, "Drives:\n" + "\n".join(lines), {"drives": found})


# --- Disk history and forecast (8.24) ---

HISTORY_PATH = Path.home() / ".maverick" / "disk_history.tsv"
RECORD_GAP = 3600       # seconds: at most one row per drive per hour, so the file stays small
WINDOW_DAYS = 30        # only the recent past: how you use a disk changes over months
MIN_SPAN_DAYS = 2       # less history than this can't tell a trend from one big download
MIN_READINGS = 3        # two points always make a perfect line; a third shows whether it's a trend


def record_disks(path: Path | None = None, now: float | None = None, usage=None) -> int:
    """Append 'time<TAB>drive<TAB>used<TAB>total' for every drive, unless the last row is under an hour old."""
    path = path or HISTORY_PATH  # looked up at call time, so tests can point it at a temporary file
    now = time.time() if now is None else now
    rows = read_history(path)
    if rows and now - max(t for t, *_ in rows) < RECORD_GAP:
        return 0
    if usage is None:
        usage = []
        for part in psutil.disk_partitions():
            try:
                u = psutil.disk_usage(part.mountpoint)
            except (PermissionError, OSError):
                continue
            usage.append((part.device.rstrip(":\\/").upper() + ":", u.total - u.free, u.total))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for drive, used, total in usage:
            f.write(f"{now:.0f}\t{drive}\t{used}\t{total}\n")
    return len(usage)


def read_history(path: Path | None = None) -> list[tuple[float, str, int, int]]:
    path = path or HISTORY_PATH
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) == 4:
            rows.append((float(parts[0]), parts[1], int(parts[2]), int(parts[3])))
    return rows


def forecast(drive: str = "C:", path: Path | None = None, now: float | None = None) -> Result:
    """'C: will be full in about 3 weeks', from a straight line through the last 30 days of disk usage."""
    from maverick.brain.forecast import LinearRegression

    now = time.time() if now is None else now
    if path is None:
        path = HISTORY_PATH
        record_disks(path, now)  # today's reading counts too
    drive = drive.rstrip(":\\/").upper() + ":"
    rows = [(t, used, total) for t, d, used, total in read_history(path)
            if d == drive and t >= now - WINDOW_DAYS * 86400]
    if not rows:
        return Result(False, f"No history for {drive} yet. I record it whenever MAVERICK starts or you ask about drives.")
    span_days = (rows[-1][0] - rows[0][0]) / 86400
    total = rows[-1][2]
    if len(rows) < MIN_READINGS or span_days < MIN_SPAN_DAYS:
        return Result(True, f"Not enough history for {drive} yet: {len(rows)} reading(s) over {span_days:.1f} days. "
                            f"I need at least {MIN_READINGS} readings spread over {MIN_SPAN_DAYS}+ days; I record "
                            "whenever MAVERICK starts or you ask about drives, so ask again later.", {"days": None})
    days = [(t - now) / 86400 for t, _, _ in rows]  # today = 0, the past is negative
    used_gb = [used / 1024 ** 3 for _, used, _ in rows]
    line = LinearRegression().fit(days, used_gb)
    per_day = line.slope
    free_gb = total / 1024 ** 3 - line.predict(0)
    trend = f"{drive} used space changes by {per_day:+.2f} GB a day (over {span_days:.0f} days, {len(rows)} readings)"
    if per_day <= 0.01:
        return Result(True, f"{trend}: it isn't filling up.", {"days": None, "per_day_gb": per_day})
    days_left = free_gb / per_day
    low, high = line.slope_range()
    span = ""
    if low > 0.01:
        span = f" (somewhere between {free_gb / high:.0f} and {free_gb / low:.0f} days)"
    fit = "a steady trend" if line.r2 >= 0.7 else "a bumpy trend, so take it loosely"
    return Result(True, f"{trend}. At that rate it will be full in about {as_words(days_left)}{span}. "
                        f"R² = {line.r2:.2f}: {fit}.",
                  {"days": days_left, "per_day_gb": per_day, "r2": line.r2})


def as_words(days: float) -> str:
    if days < 2:
        return f"{days * 24:.0f} hours"
    if days < 21:
        return f"{days:.0f} days"
    if days < 90:
        return f"{days / 7:.0f} weeks"
    if days < 730:
        return f"{days / 30:.0f} months"
    return f"{days / 365:.0f} years"
