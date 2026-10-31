"""Read-only questions about running programs. Nothing here stops or changes a process."""
import time
from collections import defaultdict

import psutil

from maverick.core.agent_base import Result
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
