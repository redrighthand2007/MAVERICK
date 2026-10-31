"""Folder watcher: a background job that moves (or copies) every NEW matching file from one folder to another."""
import shutil
from pathlib import Path

from maverick.core.agent_base import Result
from maverick.core.background import Background, Job
from maverick.core.safety import SafetyError, is_inside, require_existing, require_not_protected

# Browsers write these while a download is still running; moving them would break the download.
UNFINISHED = {".crdownload", ".part", ".partial", ".tmp", ".download", ".opdownload"}


def free_name(folder: Path, name: str) -> Path:
    """notes.pdf -> notes (2).pdf if notes.pdf is already there. MAVERICK never overwrites."""
    target = folder / name
    stem, suffix, n = target.stem, target.suffix, 2
    while target.exists():
        target = folder / f"{stem} ({n}){suffix}"
        n += 1
    return target


class WatchJob(Job):
    kind = "watch"
    interval = 3.0

    def __init__(self, source: str, destination: str, exts: list[str], action: str = "move"):
        super().__init__()
        self.source, self.destination = Path(source), Path(destination)
        self.exts, self.action = sorted(e.lower() for e in exts), action
        # Files already there when watching starts are left alone: only new arrivals count.
        self.seen = {p.name for p in self.files()}
        self.sizes: dict[str, int] = {}

    def describe(self) -> str:
        what = ", ".join(f".{e}" for e in self.exts) + " file" if self.exts else "file"
        return f"watching {self.source}: {self.action} every new {what} to {self.destination}"

    def files(self) -> list[Path]:
        if not self.source.is_dir():
            return []
        return [p for p in self.source.iterdir() if p.is_file()]

    def wanted(self, path: Path) -> bool:
        if path.suffix.lower() in UNFINISHED or path.name.startswith("~$"):
            return False
        return not self.exts or path.suffix.lower().lstrip(".") in self.exts

    def tick(self) -> list[str]:
        if not self.source.is_dir():
            return [f"{self.source} is gone; nothing to watch until it comes back."]
        messages = []
        for path in self.files():
            if path.name in self.seen or not self.wanted(path):
                continue
            # Wait until the size stops changing between two ticks: the file has finished arriving.
            size = path.stat().st_size
            if self.sizes.get(path.name) != size:
                self.sizes[path.name] = size
                continue
            self.destination.mkdir(parents=True, exist_ok=True)
            target = free_name(self.destination, path.name)
            try:
                if self.action == "copy":
                    shutil.copy2(path, target)
                else:
                    shutil.move(str(path), str(target))
            except OSError as exc:  # still open in another program: try again next tick
                messages.append(f"couldn't {self.action} {path.name} yet ({exc.strerror}); will retry")
                continue
            self.seen.add(path.name)
            self.sizes.pop(path.name, None)
            verb = "copied" if self.action == "copy" else "moved"
            messages.append(f"{verb} {path.name} -> {target}")
        return messages

    def to_dict(self) -> dict:
        return {"source": str(self.source), "destination": str(self.destination), "exts": self.exts,
                "action": self.action}


def from_dict(saved: dict) -> WatchJob:
    if not Path(saved["source"]).is_dir():
        raise ValueError("watched folder is gone")
    return WatchJob(saved["source"], saved["destination"], saved["exts"], saved.get("action", "move"))


Background.register("watch", from_dict)


def plan(source: str, destination: str, exts: list[str], action: str = "move") -> WatchJob:
    src = require_existing(source)
    if not src.is_dir():
        raise SafetyError(f"{src} is a file; I can only watch folders.")
    require_not_protected(src)
    dest = Path(destination).expanduser()
    if not dest.is_absolute():
        raise SafetyError(f"Where should files go? '{destination}' is not a full folder path.")
    require_not_protected(dest)
    if dest.exists() and not dest.is_dir():
        raise SafetyError(f"{dest} is a file, not a folder.")
    if is_inside(dest.resolve(), src) or is_inside(src, dest.resolve()):
        raise SafetyError("The two folders can't be inside each other; files would go round in circles.")
    return WatchJob(str(src), str(dest), exts, action)


def describe(source: str, destination: str, exts: list[str], action: str = "move") -> str:
    job = plan(source, destination, exts, action)
    return f"Start {job.describe()}? It keeps running in the background."


def start(background: Background, source: str, destination: str, exts: list[str], action: str = "move") -> Result:
    job = background.add(plan(source, destination, exts, action))
    return Result(True, f"Job {job.id} started: {job.describe()}. Say 'stop job {job.id}' to end it.",
                  {"job": job.id})
