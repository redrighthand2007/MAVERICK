import re

from maverick.core.agent_base import Intent, Result, SubAgent
from maverick.core.background import Background

WORD_RE = re.compile(r"[a-z0-9]+")
JOB_WORDS = {"job", "jobs", "background", "watcher", "watchers", "watching", "watches", "rotating", "rotation",
             "rotations", "monitoring", "tasks"}
STOP_WORDS = {"stop", "cancel", "remove", "end", "kill", "delete", "pause", "quit", "disable"}
FILLER = JOB_WORDS | STOP_WORDS | {"the", "a", "my", "all", "every", "please", "pls", "number", "no", "id", "for",
                                   "of", "that", "is", "which", "what", "show", "list", "running", "now", "in", "on"}


class JobsAgent(SubAgent):
    name = "jobs"
    description = ("background jobs (folder watchers, log rotators): list or stop them. "
                   "e.g. show background jobs  |  stop job 2  |  stop watching downloads")

    def __init__(self, background: Background):
        self.background = background

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower()))
        if not words & JOB_WORDS:
            return None
        # "watch downloads for pdfs" creates a job; that belongs to the watch agent.
        if not words & STOP_WORDS and not words & {"show", "list", "what", "which", "running", "jobs", "any"}:
            return None
        return self.extract("stop" if words & STOP_WORDS else "list", text)

    def extract(self, operation: str, text: str) -> Intent:
        if operation == "list":
            return Intent("list")
        words = WORD_RE.findall(text.lower())
        if set(words) & {"all", "every", "everything"}:
            return Intent("stop", {"which": "all"})
        number = next((w for w in words if w.isdigit()), "")
        if number:
            return Intent("stop", {"which": number})
        hints = [w for w in words if w not in FILLER]
        return Intent("stop", {"which": " ".join(hints)}, [] if hints else ["which job (say: show background jobs)"])

    def handle(self, intent: Intent) -> Result:
        jobs = self.background.list()
        if intent.operation == "list":
            if not jobs:
                return Result(True, "No background jobs are running.", {"jobs": []})
            lines = [f"{len(jobs)} background job{'s' if len(jobs) > 1 else ''}:"]
            lines += [f"  {job.id}. {job.describe()}" for job in jobs]
            return Result(True, "\n".join(lines), {"jobs": [job.id for job in jobs]})

        which = intent.args["which"]
        if which == "all":
            targets = jobs
        elif which.isdigit():
            targets = [job for job in jobs if job.id == int(which)]
        else:
            # "stop watching downloads": every hint word must appear in the job's description.
            targets = [job for job in jobs if all(w in job.describe().lower() for w in which.split())]
        if not targets:
            return Result(False, f"No background job matches '{which}'. Say 'show background jobs' to see them.")
        for job in targets:
            self.background.remove(job.id)
        names = "; ".join(f"{job.id}. {job.describe()}" for job in targets)
        return Result(True, f"Stopped {len(targets)} job{'s' if len(targets) > 1 else ''}: {names}",
                      {"stopped": [job.id for job in targets]})
