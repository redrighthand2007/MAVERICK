"""Questions about running programs, ending them (5.1, 5.7), and spotting leaks (7.13, 7.14).

Only the end functions change anything, and only after y/n.
"""
import ctypes
import math
import statistics
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


def ram_by_program() -> dict[str, int]:
    """Total RAM per program name right now (all copies added together)."""
    totals = defaultdict(int)
    for proc in psutil.process_iter(["name", "memory_info"]):
        if proc.info["memory_info"] and proc.pid:
            totals[proc.info["name"] or f"PID {proc.pid}"] += proc.info["memory_info"].rss
    return totals


MIN_GROWTH = 20 * 1024 ** 2  # less than this is normal wobble


# What the model compares. Per COPY and relative to the program's own size, so it judges behaviour, not size:
# with plain totals, svchost.exe (80 copies) and a big browser were "unusual" just for being big.
COLUMNS = ["ram per copy", "ram growth %/min", "cpu per copy", "threads per copy", "handles per thread",
           "connections per copy"]
# Isolation-forest score from which a program is reported (about 0.5 = normal). Chosen from
# `python -m maverick.brain.anomaly`: the three planted fakes scored 0.54-0.59, ordinary programs mostly under 0.53.
UNUSUAL_SCORE = 0.55


def program_snapshot() -> dict[str, dict]:
    """Per program name (all copies added together): RAM, threads, handles, copies, CPU time so far."""
    totals = defaultdict(lambda: {"ram": 0, "threads": 0, "handles": 0, "copies": 0, "cpu_time": 0.0, "pids": set()})
    for proc in psutil.process_iter(["name", "memory_info", "num_threads", "num_handles", "cpu_times"]):
        info = proc.info
        if not proc.pid or not info["memory_info"]:
            continue
        row = totals[info["name"] or f"PID {proc.pid}"]
        row["ram"] += info["memory_info"].rss
        row["threads"] += info["num_threads"] or 0
        row["handles"] += info["num_handles"] or 0
        row["copies"] += 1
        row["cpu_time"] += sum(info["cpu_times"][:2]) if info["cpu_times"] else 0.0
        row["pids"].add(proc.pid)
    return totals


def connections_by_pid() -> dict[int, int]:
    counts = defaultdict(int)
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.pid:
                counts[conn.pid] += 1
    except psutil.AccessDenied:
        pass  # without the list, every program just counts 0 connections
    return counts


def featurize(v: dict) -> list[float]:
    """Raw values -> the numbers the model sees, in COLUMNS order.

    Log scale, because RAM goes from 1 MB to 2 GB: without it, one huge program would dwarf every other difference.
    """
    copies = max(v["copies"], 1)
    mb = v["ram"] / 1024 ** 2
    # Only growth counts: a browser freeing 100 MB is tidying up, not misbehaving (the first live run flagged those).
    return [math.log1p(mb / copies), math.log1p(max(0.0, 100 * v["ram growth"] / max(v["ram"], 1))),
            math.log1p(v["cpu"] / copies), math.log1p(v["threads"] / copies),
            math.log1p(v["handles"] / max(v["threads"], 1)), math.log1p(v["connections"] / copies)]


def program_table(seconds: int = 6) -> tuple[list[str], list[list[float]], list[dict]]:
    """Watch every program for a few seconds: names, rows of numbers for the model, and the raw values."""
    first = program_snapshot()
    time.sleep(seconds)
    second, conns = program_snapshot(), connections_by_pid()
    names, rows, raw = [], [], []
    for name, now in sorted(second.items()):
        before = first.get(name)
        if not before:
            continue  # started during the watch: no growth to measure
        values = {
            "ram": now["ram"],
            "ram growth": (now["ram"] - before["ram"]) * 60 / seconds,  # bytes per minute
            "cpu": max(0.0, now["cpu_time"] - before["cpu_time"]) / seconds * 100,  # % of one core
            "threads": now["threads"], "handles": now["handles"],
            "connections": sum(conns.get(pid, 0) for pid in now["pids"]), "copies": now["copies"],
        }
        names.append(name)
        raw.append(values)
        rows.append(featurize(values))
    return names, rows, raw


def planted_fakes(raw: list[dict]) -> list[tuple[str, dict]]:
    """Three made-up programs with ONE odd habit each, to check the model finds what we know is there.

    Each starts as the most typical program (the median of every raw value, one copy) and gets one strange value.
    """
    typical = {key: statistics.median(v[key] for v in raw) for key in raw[0]}
    typical.update({"copies": 1, "ram growth": 0, "connections": 0})
    leaker = {**typical, "ram growth": 300 * 1024 ** 2}               # +300 MB a minute
    chatty = {**typical, "connections": 400}                          # 400 network connections
    threads = {**typical, "threads": 3000, "handles": 3000}           # 3000 threads, ~1 handle each
    return [("FAKE leaker.exe", leaker), ("FAKE chatty.exe", chatty), ("FAKE threadbomb.exe", threads)]


def describe_value(column: str, v: dict) -> str:
    """A reason in plain numbers, e.g. 'RAM +300 MB/min' or '400 connections'."""
    if column == "ram per copy":
        return f"RAM {human_size(v['ram'])} in {v['copies']} cop{'y' if v['copies'] == 1 else 'ies'}"
    if column == "ram growth %/min":
        return f"RAM {'+' if v['ram growth'] >= 0 else '-'}{human_size(abs(v['ram growth']))}/min"
    if column == "cpu per copy":
        return f"CPU {v['cpu']:.0f}%"
    if column == "threads per copy":
        return f"{v['threads']} threads"
    if column == "handles per thread":
        return f"{v['handles']} handles for {v['threads']} threads"
    return f"{v['connections']} network connections"


def unusual(seconds: int = 6) -> Result:
    """Programs that behave unlike all the others right now (8.22: isolation forest, no labels needed)."""
    from maverick.brain.anomaly import IsolationForest, reasons

    seconds = max(3, min(seconds, 120))
    names, rows, raw = program_table(seconds)
    if len(rows) < 10:
        return Result(False, "Too few programs to compare.")
    scores = IsolationForest().fit(rows).scores(rows)
    # Also needs one clearly extreme number, so every report comes with a reason a person can check.
    found = sorted(((s, i) for i, s in enumerate(scores) if s >= UNUSUAL_SCORE and reasons(rows, i, COLUMNS)),
                   reverse=True)[:5]
    if not found:
        return Result(True, f"Watched {len(names)} programs for {seconds} s: none stands out from the rest.",
                      {"unusual": []})
    lines = [f"Watched {len(names)} programs for {seconds} s. These look least like the others:"]
    for score, i in found:
        why = reasons(rows, i, COLUMNS)
        detail = ", ".join(describe_value(c, raw[i]) for c in why) or "an unusual mix of everything"
        lines.append(f"  - {names[i]} (score {score:.2f}): {detail}")
    lines.append("Unusual isn't the same as harmful: check the name, and say 'what started <name>' to see where it came from.")
    return Result(True, "\n".join(lines), {"unusual": [names[i] for _, i in found]})


def growing(seconds: int = 10, samples: int = 5) -> Result:
    """Programs whose RAM went up at every sample: the usual sign of a memory leak."""
    seconds = max(4, min(seconds, 300))
    history = [ram_by_program()]
    for _ in range(samples - 1):
        time.sleep(seconds / (samples - 1))
        history.append(ram_by_program())
    suspects = []
    for name in history[0]:
        values = [snapshot.get(name, 0) for snapshot in history]
        rising = all(later >= earlier for earlier, later in zip(values, values[1:]))
        growth = values[-1] - values[0]
        if rising and growth >= MIN_GROWTH:
            suspects.append((growth, name, values[-1]))
    suspects.sort(reverse=True)
    if not suspects:
        return Result(True, f"Watched every program for {seconds} s: no RAM kept growing "
                            f"(more than {human_size(MIN_GROWTH)}). Try a longer watch, e.g. 'for 2 minutes'.",
                      {"growing": []})
    lines = [f"Watched for {seconds} s. RAM kept growing in:"]
    for growth, name, now in suspects[:10]:
        per_minute = growth * 60 / seconds
        lines.append(f"  - {name}: +{human_size(growth)} (about +{human_size(per_minute)}/min), now {human_size(now)}")
    lines.append("If one keeps climbing for minutes, restarting it frees the memory: say 'kill <name>'.")
    return Result(True, "\n".join(lines), {"growing": [name for _, name, _ in suspects]})


HANDLE_WARNING = 10_000  # a single process holding more than this usually leaks handles


def handles(limit: int = 10) -> Result:
    """Programs holding the most Windows handles (open files, registry keys, threads, events ...)."""
    groups = defaultdict(lambda: {"count": 0, "handles": 0, "worst": 0})
    for proc in psutil.process_iter(["name"]):
        try:
            n = proc.num_handles()
        except GONE:
            continue
        group = groups[proc.info["name"] or f"PID {proc.pid}"]
        group["count"] += 1
        group["handles"] += n
        group["worst"] = max(group["worst"], n)
    ranked = sorted(groups.items(), key=lambda item: item[1]["worst"], reverse=True)[:limit]
    lines = [f"Programs holding the most handles (one process over {HANDLE_WARNING:,} usually means a leak):"]
    suspects = []
    for name, g in ranked:
        copies = f" x{g['count']}" if g["count"] > 1 else ""
        flag = "  <-- suspicious" if g["worst"] > HANDLE_WARNING else ""
        if flag:
            suspects.append(name)
        lines.append(f"  - {name}{copies}: {g['worst']:,} in its biggest process ({g['handles']:,} total){flag}")
    if suspects:
        lines.append("Restarting a leaking program gives its handles back: say 'kill <name>'.")
    return Result(True, "\n".join(lines), {"suspects": suspects, "top": [n for n, _ in ranked]})
