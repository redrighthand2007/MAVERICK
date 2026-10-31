"""MAVERICK's background runner: jobs that keep working while you type (or while nothing is typed at all).

A job is anything with a tick() that is called every `interval` seconds and returns messages to show you,
e.g. the folder watcher (6.2) or the log rotator (6.5). Jobs are saved to a JSON file so they come back
the next time MAVERICK starts.
"""
import json
import threading
import time
from pathlib import Path

JOBS_PATH = Path.home() / ".maverick" / "jobs.json"


class Job:
    kind = "job"            # saved in jobs.json so the right class is rebuilt on start
    interval = 5.0          # seconds between ticks

    def __init__(self):
        self.id = 0
        self.next_run = 0.0

    def describe(self) -> str:
        raise NotImplementedError

    def tick(self) -> list[str]:
        """Do one round of work; return messages for the user (empty list if nothing happened)."""
        raise NotImplementedError

    def to_dict(self) -> dict:
        raise NotImplementedError


class Background:
    # kind -> function that rebuilds a job from its saved dict; agents register theirs here.
    job_types: dict = {}

    def __init__(self, path: Path | None = None, notify=print):
        self.path = path            # None: jobs live only in memory (tests, one-shot mode)
        self.notify = notify
        self.jobs: dict[int, Job] = {}
        self.lock = threading.Lock()
        self.thread: threading.Thread | None = None
        self.stopping = threading.Event()

    @classmethod
    def register(cls, kind: str, from_dict) -> None:
        cls.job_types[kind] = from_dict

    def add(self, job: Job) -> Job:
        with self.lock:
            job.id = max(self.jobs, default=0) + 1
            self.jobs[job.id] = job
        self.save()
        self.start()
        return job

    def remove(self, job_id: int) -> Job | None:
        with self.lock:
            job = self.jobs.pop(job_id, None)
        self.save()
        return job

    def list(self) -> list[Job]:
        with self.lock:
            return list(self.jobs.values())

    def run_due(self, now: float | None = None) -> None:
        """One pass over the jobs: tick every job whose time has come. The thread calls this every second."""
        now = time.time() if now is None else now
        for job in self.list():
            if now < job.next_run:
                continue
            job.next_run = now + job.interval
            try:
                messages = job.tick()
            except Exception as exc:  # one broken job must never stop the others
                messages = [f"job {job.id} hit a problem: {exc}"]
            for message in messages:
                self.notify(f"[job {job.id}] {message}")

    def start(self) -> None:
        if self.thread and self.thread.is_alive():
            return
        self.stopping.clear()
        self.thread = threading.Thread(target=self._loop, name="maverick-background", daemon=True)
        self.thread.start()

    def stop(self) -> None:
        self.stopping.set()

    def _loop(self) -> None:
        while not self.stopping.wait(1.0):
            self.run_due()

    def save(self) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        data = [{"kind": job.kind, **job.to_dict()} for job in self.list()]
        self.path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def load(self) -> int:
        """Bring back the jobs saved last time. Returns how many came back."""
        if self.path is None or not self.path.exists():
            return 0
        restored = 0
        for saved in json.loads(self.path.read_text(encoding="utf-8")):
            maker = self.job_types.get(saved.pop("kind", ""))
            if maker is None:
                continue
            try:
                job = maker(saved)
            except (KeyError, ValueError, OSError):
                continue  # e.g. the watched folder was deleted since
            with self.lock:
                job.id = max(self.jobs, default=0) + 1
                self.jobs[job.id] = job
            restored += 1
        if restored:
            self.start()
        return restored
