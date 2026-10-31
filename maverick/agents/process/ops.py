"""Questions about running programs, plus ending them (5.1, 5.7). Only the end functions change anything, after y/n."""
import ctypes
import time
from collections import defaultdict
from ctypes import wintypes

import psutil

from maverick.core.agent_base import Result
from maverick.core.safety import SafetyError
from maverick.core.units import human_size

GONE = (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess)
# Plain-English hints for the parents people usually meet.
KNOWN_PARENTS = {
    "explorer.exe": "you opened it from the desktop, Start menu or taskbar",
    "services.exe": "it runs as a Windows service",
    "svchost.exe": "a Windows service host started it",
    "wininit.exe": "Windows started it during boot",
    "code.exe": "it was started from VS Code",
    "windowsterminal.exe": "it was started from Windows Terminal",
    "powershell.exe": "it was started from PowerShell",
    "cmd.exe": "it was started from Command Prompt",
    "taskhostw.exe": "a scheduled task started it",
}


def find(name: str) -> list[psutil.Process]:
    """Running processes matching a name ("chrome", "chrome.exe") or a PID ("1234")."""
    wanted = name.strip().lower()
    if wanted.isdigit():
        return [p for p in psutil.process_iter(["name", "create_time"]) if p.pid == int(wanted)]
    exact, partial = [], []
    for proc in psutil.process_iter(["name", "create_time"]):
        pname = (proc.info["name"] or "").lower()
        if pname in (wanted, wanted + ".exe"):
            exact.append(proc)
        elif wanted and wanted in pname:
            partial.append(proc)
    return exact or partial


def label(proc: psutil.Process) -> str:
    return f"{proc.info.get('name') if hasattr(proc, 'info') else proc.name()} (PID {proc.pid})"


def top(sort: str = "memory", limit: int = 10) -> Result:
    """Biggest programs right now, with all copies of the same program added together (chrome has dozens)."""
    procs = list(psutil.process_iter(["name", "memory_info"]))
    cpu = {}
    if sort == "cpu":
        for proc in procs:
            try:
                proc.cpu_percent(None)  # first call only starts the measurement
            except GONE:
                pass
        time.sleep(0.5)
        cores = psutil.cpu_count() or 1
        for proc in procs:
            try:
                cpu[proc.pid] = proc.cpu_percent(None) / cores  # psutil counts every core as 100%
            except GONE:
                pass

    groups = defaultdict(lambda: {"count": 0, "ram": 0, "cpu": 0.0})
    for proc in procs:
        name = proc.info["name"] or f"PID {proc.pid}"
        if proc.pid == 0 or name == "System Idle Process":
            continue
        group = groups[name]
        group["count"] += 1
        group["ram"] += proc.info["memory_info"].rss if proc.info["memory_info"] else 0
        group["cpu"] += cpu.get(proc.pid, 0.0)

    key = "cpu" if sort == "cpu" else "ram"
    ranked = sorted(groups.items(), key=lambda item: item[1][key], reverse=True)[:limit]
    lines = [f"Top {len(ranked)} programs by {'CPU' if sort == 'cpu' else 'RAM'} ({len(procs)} processes running):"]
    for name, g in ranked:
        copies = f" x{g['count']}" if g["count"] > 1 else ""
        cpu_text = f"CPU {g['cpu']:4.1f}%  " if sort == "cpu" else ""
        lines.append(f"  - {name}{copies}: {cpu_text}RAM {human_size(g['ram'])}")
    return Result(True, "\n".join(lines), {"programs": [{"name": n, **g} for n, g in ranked]})


def origin(name: str) -> Result:
    """Walk up the parent chain: what started this program, and what started that, and so on."""
    matches = find(name)
    if not matches:
        return Result(False, f"No running program called '{name}'.")
    proc = min(matches, key=lambda p: p.info["create_time"] or 0)  # the oldest copy is usually the main one
    lines = [f"{label(proc)}" + (f", {len(matches)} copies running" if len(matches) > 1 else "") + ":"]
    chain, current = [], proc
    for _ in range(15):
        try:
            ppid, started = current.ppid(), current.create_time()
        except GONE:
            break
        if not ppid:
            lines.append("  <- started by Windows itself")
            break
        try:
            parent = psutil.Process(ppid)
            # Windows reuses PIDs: a "parent" that started after its child is a different, newer program.
            alive = parent.create_time() <= started
        except GONE:
            alive = False
        if not alive:
            lines.append(f"  <- started by PID {ppid}, which has since closed")
            break
        chain.append(parent.name())
        lines.append(f"  <- started by {parent.name()} (PID {parent.pid})")
        current = parent
    if chain:
        direct = chain[0]
        lines.append(f"In short: {KNOWN_PARENTS.get(direct.lower(), f'{direct} started it')}.")
    return Result(True, "\n".join(lines), {"chain": chain})


def children(name: str) -> Result:
    """What this program started, directly and in total."""
    matches = find(name)
    if not matches:
        return Result(False, f"No running program called '{name}'.")
    proc = min(matches, key=lambda p: p.info["create_time"] or 0)
    try:
        direct = proc.children()
        everything = proc.children(recursive=True)
    except GONE:
        return Result(False, f"Windows won't show what {label(proc)} started (permission denied).")
    if not direct:
        return Result(True, f"{label(proc)} hasn't started any programs that are still running.", {"direct": 0, "total": 0})
    lines = [f"{label(proc)} started {len(direct)} programs directly, {len(everything)} in total:"]
    for child in direct[:15]:
        try:
            lines.append(f"  - {child.name()} (PID {child.pid})")
        except GONE:
            continue
    if len(direct) > 15:
        lines.append(f"  ... and {len(direct) - 15} more")
    return Result(True, "\n".join(lines), {"direct": len(direct), "total": len(everything)})


# Ending these crashes or locks Windows, so MAVERICK refuses even if you say yes.
PROTECTED = {
    "system", "registry", "memory compression", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe",
    "services.exe", "lsass.exe", "lsaiso.exe", "svchost.exe", "dwm.exe", "fontdrvhost.exe", "explorer.exe",
    "msmpeng.exe", "sihost.exe", "ctfmon.exe", "conhost.exe",
}


def plan_end(name: str) -> list[psutil.Process]:
    """The processes "end <name>" would stop, after the safety checks."""
    matches = find(name)
    if not matches:
        raise SafetyError(f"No running program called '{name}'.")
    names = {(p.info["name"] or "").lower() for p in matches}
    blocked = names & PROTECTED
    if blocked:
        raise SafetyError(f"{', '.join(sorted(blocked))} is part of Windows; ending it would crash or lock the PC.")
    # Never end MAVERICK itself or the terminal it runs in.
    me = psutil.Process()
    keep = {me.pid} | {p.pid for p in me.parents()}
    targets = [p for p in matches if p.pid not in keep]
    if not targets:
        raise SafetyError(f"'{name}' is MAVERICK itself (or the window it runs in).")
    return targets


def heaviest(sort: str = "memory") -> str:
    """Name of the biggest program you could end: "kill whatever is using the most ram"."""
    for program in top(sort, limit=50).data["programs"]:
        if program["name"].lower() not in PROTECTED:
            try:
                plan_end(program["name"])
                return program["name"]
            except SafetyError:
                continue
    return ""


def describe_end(targets: list[psutil.Process]) -> str:
    ram = 0
    for proc in targets:
        try:
            ram += proc.memory_info().rss
        except GONE:
            pass
    names = sorted({p.info["name"] for p in targets})
    copies = f"{len(targets)} copies, " if len(targets) > 1 else ""
    return f"End {', '.join(names)} ({copies}using {human_size(ram)} RAM)? Unsaved work in it will be lost."


def end(name: str) -> Result:
    """Ask each process to close, then force the ones that don't within 3 seconds."""
    targets = plan_end(name)
    for proc in targets:
        try:
            proc.terminate()
        except GONE:
            pass
    gone, alive = psutil.wait_procs(targets, timeout=3)
    for proc in alive:
        try:
            proc.kill()
        except GONE:
            pass
    _, still = psutil.wait_procs(alive, timeout=2)
    names = ", ".join(sorted({p.info["name"] for p in targets}))
    if still:
        return Result(False, f"Ended {len(targets) - len(still)} of {len(targets)} {names} processes; "
                             f"Windows refused the rest (try running MAVERICK as Administrator).",
                      {"ended": len(targets) - len(still), "failed": len(still)})
    return Result(True, f"Ended {names} ({len(targets)} process{'es' if len(targets) > 1 else ''}).",
                  {"ended": len(targets), "failed": 0})


def hung_windows() -> list[tuple[int, str]]:
    """(PID, window title) of every visible window Windows marks "Not Responding"."""
    user32 = ctypes.windll.user32
    found = []

    @ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def check(hwnd, _):
        if user32.IsWindowVisible(hwnd) and user32.IsHungAppWindow(hwnd):
            length = user32.GetWindowTextLengthW(hwnd)
            title = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, title, length + 1)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            found.append((pid.value, title.value))
        return True

    user32.EnumWindows(check, 0)
    return found


def hung_programs() -> list[dict]:
    """Not-responding programs, one entry per process (a frozen app can have several windows)."""
    programs = {}
    for pid, title in hung_windows():
        try:
            name = psutil.Process(pid).name()
        except GONE:
            continue
        programs.setdefault(pid, {"pid": pid, "name": name, "titles": []})["titles"].append(title)
    return list(programs.values())


def hung() -> Result:
    programs = hung_programs()
    if not programs:
        return Result(True, "No apps are frozen right now; every window is responding.", {"hung": []})
    lines = [f"{len(programs)} app{'s are' if len(programs) > 1 else ' is'} not responding:"]
    lines += [f"  - {p['name']} (PID {p['pid']}): \"{p['titles'][0]}\"" for p in programs]
    lines.append("To end them, say: end frozen apps")
    return Result(True, "\n".join(lines), {"hung": programs})


def plan_end_hung() -> list[dict]:
    programs = [p for p in hung_programs() if p["name"].lower() not in PROTECTED]
    if not programs:
        raise SafetyError("No frozen apps to end; every window is responding.")
    return programs


def describe_end_hung() -> str:
    names = ", ".join(f"{p['name']} (\"{p['titles'][0]}\")" for p in plan_end_hung())
    return f"End these frozen apps: {names}? Unsaved work in them will be lost."


def end_hung() -> Result:
    """Frozen apps can't answer a polite close, so they are forced straight away."""
    programs = plan_end_hung()
    ended = []
    for program in programs:
        try:
            psutil.Process(program["pid"]).kill()
            ended.append(program["name"])
        except GONE:
            pass
    if len(ended) < len(programs):
        return Result(False, f"Ended {len(ended)} of {len(programs)} frozen apps; Windows refused the rest "
                             "(try running MAVERICK as Administrator).", {"ended": len(ended)})
    return Result(True, f"Ended {len(ended)} frozen app{'s' if len(ended) > 1 else ''}: {', '.join(ended)}.",
                  {"ended": len(ended)})
