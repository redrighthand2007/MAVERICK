"""Log rotator: copy a big log into a compressed, dated .gz beside it, then empty the original.

The program writing the log keeps its file open and simply carries on writing into the now-empty file.
Old rotated copies are never deleted.
"""
import gzip
import shutil
import time
from pathlib import Path

from maverick.core.agent_base import Result
from maverick.core.background import Background, Job
from maverick.core.safety import SafetyError, require_existing, require_not_protected
from maverick.core.units import human_size


def plan(path: str) -> Path:
    log = require_existing(path)
    if not log.is_file():
        raise SafetyError(f"{log} is a folder; name the log file itself.")
    require_not_protected(log)
    return log


def rotated_name(log: Path, now: float | None = None) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S", time.localtime(now))
    target = log.with_name(f"{log.stem}-{stamp}{log.suffix}.gz")
    n = 2
    while target.exists():
        target = log.with_name(f"{log.stem}-{stamp}-{n}{log.suffix}.gz")
        n += 1
    return target


def rotate_now(log: Path) -> tuple[Path, int, int]:
    """Returns (archive, original size, archive size). The original is emptied only after the copy is safe."""
    size = log.stat().st_size
    archive = rotated_name(log)
    with open(log, "rb") as src, gzip.open(archive, "wb") as dest:
        shutil.copyfileobj(src, dest)
    with open(log, "r+b") as f:  # empty it in place, so a program that has it open keeps working
        f.truncate(0)
    return archive, size, archive.stat().st_size


def rotate(path: str) -> Result:
    log = plan(path)
    if log.stat().st_size == 0:
        return Result(True, f"{log.name} is already empty; nothing to rotate.", {"rotated": False})
    archive, before, after = rotate_now(log)
    return Result(True, f"Rotated {log.name}: saved {human_size(before)} as {archive.name} ({human_size(after)}), "
                        f"and emptied the log.", {"archive": str(archive), "rotated": True})


def describe(path: str, max_size: int = 0) -> str:
    log = plan(path)
    if max_size:
        return (f"Start a background job that rotates {log} whenever it grows past {human_size(max_size)} "
                f"(now {human_size(log.stat().st_size)})?")
    return (f"Rotate {log} ({human_size(log.stat().st_size)})? It is saved as a dated .gz next to it, "
            f"then the log is emptied.")


class RotateJob(Job):
    kind = "rotate"
    interval = 60.0

    def __init__(self, path: str, max_size: int):
        super().__init__()
        self.path, self.max_size = Path(path), max_size

    def describe(self) -> str:
        return f"rotating {self.path} when bigger than {human_size(self.max_size)}"

    def tick(self) -> list[str]:
        if not self.path.exists():
            return []
        if self.path.stat().st_size <= self.max_size:
            return []
        archive, before, after = rotate_now(self.path)
        return [f"rotated {self.path.name} ({human_size(before)} -> {archive.name}, {human_size(after)})"]

    def to_dict(self) -> dict:
        return {"path": str(self.path), "max_size": self.max_size}


Background.register("rotate", lambda saved: RotateJob(saved["path"], saved["max_size"]))


def start(background: Background, path: str, max_size: int) -> Result:
    job = background.add(RotateJob(str(plan(path)), max_size))
    return Result(True, f"Job {job.id} started: {job.describe()}. Say 'stop job {job.id}' to end it.", {"job": job.id})
