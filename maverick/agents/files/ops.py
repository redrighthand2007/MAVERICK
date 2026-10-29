import os
import shutil
from pathlib import Path

from maverick.core.agent_base import Result
from maverick.core.safety import SafetyError, plan_destination, require_existing, require_not_protected

# Characters Windows does not allow in a file name.
INVALID_NAME_CHARS = set('<>:"/\\|?*')


def human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.2f} {unit}"
        size /= 1024


def copy(source: str, destination: str) -> Result:
    src = require_existing(source)
    dest = plan_destination(src, destination)
    if src.is_dir():
        shutil.copytree(src, dest)
    else:
        shutil.copy2(src, dest)  # copy2 also keeps timestamps
    return Result(True, f"Copied {src} -> {dest}", {"output": str(dest)})


def plan_move(source: str, destination: str) -> tuple[Path, Path]:
    """All safety checks for a move, without touching anything. Returns (source, final destination)."""
    src = require_existing(source)
    require_not_protected(src)
    return src, plan_destination(src, destination)


def move(source: str, destination: str) -> Result:
    src, dest = plan_move(source, destination)
    shutil.move(src, dest)
    return Result(True, f"Moved {src} -> {dest}", {"output": str(dest)})


def plan_rename(source: str, new_name: str) -> tuple[Path, Path]:
    """All safety checks for a rename, without touching anything. Returns (source, new path)."""
    src = require_existing(source)
    require_not_protected(src)
    new_name = new_name.strip()
    if INVALID_NAME_CHARS & set(new_name):
        raise SafetyError(f"'{new_name}' is a path, not a name. Use 'move' to put it in another folder.")
    target = src.parent / new_name
    # samefile allows a case-only rename (notes.txt -> Notes.txt), since Windows ignores case.
    if target.exists() and not target.samefile(src):
        raise SafetyError(f"{target} already exists; MAVERICK never overwrites.")
    return src, target


def rename(source: str, new_name: str) -> Result:
    src, target = plan_rename(source, new_name)
    src.rename(target)
    return Result(True, f"Renamed {src.name} -> {target.name}", {"output": str(target)})


def size(path: str) -> Result:
    target = require_existing(path)
    if target.is_file():
        total = target.stat().st_size
        return Result(True, f"{target} is {human_size(total)}", {"bytes": total})

    total, files, skipped = 0, 0, 0
    for root, _dirs, names in os.walk(target):
        for name in names:
            try:
                total += (Path(root) / name).stat().st_size
                files += 1
            except OSError:
                skipped += 1  # locked or permission-denied files
    msg = f"{target} is {human_size(total)} ({files} files)"
    if skipped:
        msg += f", {skipped} files could not be read"
    return Result(True, msg, {"bytes": total, "files": files, "skipped": skipped})
