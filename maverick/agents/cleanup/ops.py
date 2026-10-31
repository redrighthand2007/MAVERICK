"""Find what is filling the disk, and send chosen things to the Recycle Bin (never a permanent delete)."""
import os
import tempfile
import time
from pathlib import Path

from maverick.agents.cleanup.recycle_bin import send_to_recycle_bin
from maverick.agents.search.ops import SKIP_DIRS
from maverick.core.agent_base import Result
from maverick.core.safety import SafetyError, require_existing, require_not_protected
from maverick.core.units import human_size

BIG_FILE = 500 * 1024 ** 2   # files at least this big are worth a look
OLD_DAYS = 90                # downloads untouched this long are probably forgotten
TEMP_MIN_AGE = 86400         # temp files younger than a day may still be in use
SCAN_LIMIT = 20              # seconds before a huge drive scan stops


def temp_dir() -> Path:
    return Path(tempfile.gettempdir())


def folder_size(path: Path) -> int:
    total = 0
    for root, _, files in os.walk(path):
        for name in files:
            try:
                total += os.path.getsize(os.path.join(root, name))
            except OSError:
                pass
    return total


def old_temp_items(now: float | None = None) -> list[Path]:
    """Things in your Temp folder older than a day: safe to throw away."""
    now = now or time.time()
    items = []
    for entry in temp_dir().iterdir():
        try:
            if now - entry.stat().st_mtime > TEMP_MIN_AGE:
                items.append(entry)
        except OSError:
            pass
    return items


def items_size(items: list[Path]) -> int:
    return sum(folder_size(p) if p.is_dir() else p.stat().st_size for p in items if p.exists())


def scan(root: str = "") -> Result:
    """Where space can be won back: temp files, big files, and old downloads."""
    home = Path.home()
    start = Path(root) if root else home
    now = time.time()
    temp = old_temp_items(now)
    temp_bytes = items_size(temp)

    big, old_downloads, stopped = [], [], False
    downloads = home / "Downloads"
    deadline = now + SCAN_LIMIT
    for folder, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith("$")]
        if time.time() > deadline:
            stopped = True
            break
        for name in files:
            path = Path(folder, name)
            try:
                st = path.stat()
            except OSError:
                continue
            if st.st_size >= BIG_FILE:
                big.append((st.st_size, path))
            if downloads in path.parents and now - st.st_mtime > OLD_DAYS * 86400:
                old_downloads.append((st.st_size, path))
    big.sort(reverse=True)
    old_downloads.sort(reverse=True)

    lines = [f"Space you could free in {start}:"]
    lines.append(f"  - Temp files older than a day: {len(temp)} items, {human_size(temp_bytes)}  (say: clear temp files)")
    if big:
        lines.append(f"  - Big files (over {human_size(BIG_FILE)}):")
        lines += [f"      {human_size(s):>10}  {p}" for s, p in big[:10]]
    if old_downloads:
        total = sum(s for s, _ in old_downloads)
        lines.append(f"  - Downloads untouched for {OLD_DAYS}+ days: {len(old_downloads)} files, {human_size(total)}")
        lines += [f"      {human_size(s):>10}  {p}" for s, p in old_downloads[:5]]
    if stopped:
        lines.append(f"(Stopped after {SCAN_LIMIT} s; name a smaller folder for a full scan.)")
    lines.append("To delete one, say: delete <path>. It goes to the Recycle Bin, so you can restore it.")
    return Result(True, "\n".join(lines), {"temp_bytes": temp_bytes, "big": [str(p) for _, p in big],
                                            "old_downloads": [str(p) for _, p in old_downloads]})


def plan_recycle(target: str) -> list[Path]:
    """What "delete <target>" would send to the Recycle Bin, after the safety checks."""
    if target == "temp":
        return old_temp_items()
    path = require_existing(target)
    require_not_protected(path)
    home = Path.home()
    if path == home or path.parent == home:
        raise SafetyError(f"{path} is one of your main user folders; delete what's inside it instead.")
    return [path]


def describe_recycle(target: str) -> str:
    items = plan_recycle(target)
    if not items:
        return "Nothing to delete."
    size = human_size(items_size(items))
    what = f"{len(items)} old items from your Temp folder" if target == "temp" else str(items[0])
    return f"Send {what} ({size}) to the Recycle Bin? You can restore it from there."


def recycle(target: str) -> Result:
    items = plan_recycle(target)
    if not items:
        return Result(True, "Nothing to delete.", {"recycled": 0})
    size = items_size(items)
    if target == "temp":
        # Some temp files are always locked by running programs; skip those instead of failing.
        done = 0
        for item in items:
            try:
                send_to_recycle_bin([item])
                done += 1
            except OSError:
                pass
        return Result(True, f"Sent {done} of {len(items)} temp items to the Recycle Bin "
                            f"(the rest are in use). Empty the Recycle Bin to really free the space.", {"recycled": done})
    send_to_recycle_bin(items)
    return Result(True, f"Sent {items[0]} ({human_size(size)}) to the Recycle Bin.", {"recycled": 1})
