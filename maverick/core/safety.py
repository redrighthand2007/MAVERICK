import os
from pathlib import Path


class SafetyError(ValueError):
    """Raised when an operation would be unsafe, so nothing is touched."""


# Folders MAVERICK must never write into or move things out of.
PROTECTED_ROOTS = [
    Path(os.environ.get("SystemRoot", r"C:\Windows")),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")),
    Path(os.environ.get("ProgramData", r"C:\ProgramData")),
]


def to_path(raw: str) -> Path:
    if not raw or not raw.strip():
        raise SafetyError("No path given.")
    return Path(os.path.expandvars(os.path.expanduser(raw.strip().strip('"')))).resolve()


def require_existing(raw: str) -> Path:
    path = to_path(raw)
    if not path.exists():
        raise SafetyError(f"Path does not exist: {path}")
    return path


def is_inside(child: Path, parent: Path) -> bool:
    return child == parent or parent in child.parents


def require_not_protected(path: Path) -> None:
    for root in PROTECTED_ROOTS:
        if is_inside(path, root.resolve()):
            raise SafetyError(f"{path} is inside a protected system folder ({root}).")
    if path.parent == path:
        raise SafetyError(f"Refusing to operate on a whole drive: {path}")


def plan_destination(source: Path, raw_dest: str) -> Path:
    """Work out the final target path for a copy/move and check it is safe.

    If the destination is an existing folder, the item goes inside it,
    like dragging a file onto a folder in Explorer.
    """
    dest = to_path(raw_dest)
    if dest.is_dir():
        dest = dest / source.name
    if not dest.parent.exists():
        raise SafetyError(f"Destination folder does not exist: {dest.parent}")
    if dest.exists():
        raise SafetyError(f"{dest} already exists; MAVERICK never overwrites.")
    if dest == source:
        raise SafetyError("Source and destination are the same.")
    if source.is_dir() and is_inside(dest, source):
        raise SafetyError("Cannot put a folder inside itself.")
    require_not_protected(dest)
    return dest
