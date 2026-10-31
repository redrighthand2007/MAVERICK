"""Read-only file search. Nothing here changes, moves or opens a file."""
import os
import time
from datetime import datetime
from pathlib import Path

from maverick.core.agent_base import Result
from maverick.core.safety import require_existing
from maverick.core.units import human_size

# Folders that are huge, system-owned, or never hold your own files. Skipped below the starting folder.
SKIP_DIRS = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "appdata",
             "system volume information", "node_modules", ".git", "__pycache__", ".venv", "venv", ".pytest_cache"}
TEXT_EXTS = {"txt", "md", "py", "js", "ts", "json", "csv", "tsv", "html", "css", "xml", "yml", "yaml",
             "ini", "cfg", "log", "java", "c", "cpp", "h", "sql", "bat", "ps1", "env", "toml"}
MAX_TEXT_SIZE = 5 * 1024 * 1024  # don't read inside files bigger than 5 MB
SHOW = 20


def find(root: str = "", name: str = "", exts: list[str] | None = None, after: float | None = None,
         before: float | None = None, min_size: int | None = None, max_size: int | None = None,
         contains: str = "", time_limit: float = 20.0) -> Result:
    start = require_existing(root) if root else Path.home()
    words = name.lower().split()
    exts = {e.lower().lstrip(".") for e in exts or []}
    if contains:
        exts = exts or TEXT_EXTS  # only text files can be searched inside
    needle = contains.lower()

    found, scanned, stopped = [], 0, False
    began = time.monotonic()
    for folder, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS]
        for filename in files:
            scanned += 1
            low = filename.lower()
            if words and not all(w in low for w in words):
                continue
            if exts and low.rsplit(".", 1)[-1] not in exts:
                continue
            path = Path(folder) / filename
            try:
                info = path.stat()
            except OSError:
                continue
            if (after and info.st_mtime < after) or (before and info.st_mtime >= before):
                continue
            if (min_size is not None and info.st_size <= min_size) or (max_size is not None and info.st_size >= max_size):
                continue
            line = ""
            if needle:
                line = first_matching_line(path, info.st_size, needle)
                if line is None:
                    continue
            found.append((path, info.st_size, info.st_mtime, line))
        if time.monotonic() - began > time_limit:
            stopped = True
            break

    if min_size is not None:
        found.sort(key=lambda f: f[1], reverse=True)  # "bigger than" questions want the biggest first
    elif after is not None:
        found.sort(key=lambda f: f[2], reverse=True)  # date questions want the newest first

    took = time.monotonic() - began
    header = f"Found {len(found)} file{'s' if len(found) != 1 else ''} in {start} (looked at {scanned:,} files in {took:.1f} s)"
    if stopped:
        header += f". Stopped after {time_limit:.0f} s, so there may be more; try a smaller folder"
    if not found:
        return Result(True, header + ".", {"count": 0, "scanned": scanned, "stopped": stopped})
    lines = [header + ":"]
    for path, size, mtime, line in found[:SHOW]:
        lines.append(f"  - {path}  {human_size(size)}  {datetime.fromtimestamp(mtime):%Y-%m-%d %H:%M}")
        if line:
            lines.append(f"      \"{line}\"")
    if len(found) > SHOW:
        lines.append(f"  ... and {len(found) - SHOW} more")
    return Result(True, "\n".join(lines), {"count": len(found), "scanned": scanned, "stopped": stopped,
                                           "files": [str(f[0]) for f in found]})


def first_matching_line(path: Path, size: int, needle: str) -> str | None:
    if size > MAX_TEXT_SIZE:
        return None
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if needle in line.lower():
                    text = line.strip()
                    return text if len(text) <= 80 else text[:77] + "..."
    except OSError:
        return None
    return None
