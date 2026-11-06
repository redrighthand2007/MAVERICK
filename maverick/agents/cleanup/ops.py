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


# --- "Free up 5 GB": choose the files (8.26) ---

PLAN_MIN_FILE = 50 * 1024 ** 2   # smaller files aren't worth a decision each
NEVER_REGRET = 0.9               # files you'd miss this much are never offered
DOC_TYPES = {"doc", "docx", "pdf", "xls", "xlsx", "ppt", "pptx", "txt", "md", "odt", "csv", "jpg", "jpeg", "png",
             "heic", "raw", "psd"}
INSTALLER_TYPES = {"exe", "msi", "iso", "img", "dmg", "apk"}
ARCHIVE_TYPES = {"zip", "rar", "7z", "tar", "gz"}
VIDEO_TYPES = {"mp4", "mkv", "avi", "mov", "wmv", "webm"}


def regret(path: Path, mtime: float, now: float) -> float:
    """0 = nobody misses it .. 1 = you'd want it back. A person's rules of thumb, written down."""
    ext = path.suffix.lower().lstrip(".")
    base = (0.1 if ext in INSTALLER_TYPES else 0.3 if ext in ARCHIVE_TYPES else 0.5 if ext in VIDEO_TYPES
            else 0.8 if ext in DOC_TYPES else 0.5)
    days = (now - mtime) / 86400
    base += 0.4 if days < 30 else 0.2 if days < 180 else 0.0  # recent things are probably still in use
    if Path.home() / "Downloads" in path.parents:
        base -= 0.1                                          # downloads are often one-off copies
    return round(min(1.0, max(0.0, base)), 2)


def free_candidates(root: str = "", now: float | None = None) -> tuple[list[tuple[Path, int, float]], bool]:
    """(path, size, regret) for old temp files (as one item) and every file over 50 MB; and whether the scan stopped."""
    now = now or time.time()
    start = Path(root) if root else Path.home()
    found = []
    temp = old_temp_items(now)
    if temp:
        found.append((Path("temp"), items_size(temp), 0.0))
    deadline, stopped = time.time() + SCAN_LIMIT, False
    for folder, dirs, files in os.walk(start):
        dirs[:] = [d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith(("$", "."))]
        if time.time() > deadline:
            stopped = True
            break
        for name in files:
            path = Path(folder, name)
            try:
                st = path.stat()
                if st.st_size < PLAN_MIN_FILE:
                    continue
                require_not_protected(path)
            except (OSError, SafetyError):
                continue
            r = regret(path, st.st_mtime, now)
            if r < NEVER_REGRET:
                found.append((path, st.st_size, r))
    return found, stopped


def plan_free(goal: int, root: str = "") -> tuple[list[tuple[Path, int, float]], str]:
    """The least-regret set that frees `goal` bytes, plus a note if that's impossible or the scan stopped."""
    from maverick.brain.plan import optimal

    found, stopped = free_candidates(root)
    chosen = optimal([(size, r) for _, size, r in found], goal)
    note = f" (the scan stopped after {SCAN_LIMIT} s, so a smaller folder may give a better plan)" if stopped else ""
    if not chosen:
        available = sum(size for _, size, _ in found)
        return [], (f"I can only find {human_size(available)} that is safe to suggest, not {human_size(goal)}" + note)
    return [found[i] for i in chosen], note


# The plan last shown in a y/n question: "yes" must delete exactly that list, never a fresh plan.
shown_plans: dict[tuple[int, str], list[tuple[Path, int, float]]] = {}


def describe_free(goal: int, root: str = "") -> str:
    plan, note = plan_free(goal, root)
    shown_plans[(goal, root)] = plan
    if not plan:
        return note + ". Nothing will be deleted; say 'free up space' to see where the space goes."
    lines = [f"To free {human_size(goal)}, the least-missed choice is {len(plan)} item(s), "
             f"{human_size(sum(s for _, s, _ in plan))} in all{note}:"]
    for path, size, r in sorted(plan, key=lambda p: -p[1]):
        what = "old temp files" if str(path) == "temp" else str(path)
        lines.append(f"  - {human_size(size):>10}  {what}  (would you miss it: {r:.1f})")
    lines.append("Send them all to the Recycle Bin?")
    return "\n".join(lines)


def free(goal: int, root: str = "") -> Result:
    """Recycle exactly the items shown in the y/n question; each one still passes recycle()'s safety checks."""
    plan = shown_plans.pop((goal, root), None)
    if not plan:
        return Result(False, "There is no approved plan to carry out. Nothing was deleted.", {"recycled": 0})
    done, size = 0, 0
    for path, item_size, _ in plan:
        try:
            result = recycle(str(path))
        except (OSError, SafetyError):
            continue  # gone or locked since the plan was made: skip it, never substitute another file
        if result.success:
            done, size = done + 1, size + item_size
    return Result(True, f"Sent {done} of {len(plan)} item(s), {human_size(size)}, to the Recycle Bin. "
                        "Empty the Recycle Bin to really get the space back.", {"recycled": done})


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
