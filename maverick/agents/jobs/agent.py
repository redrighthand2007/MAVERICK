import re

from maverick.core.agent_base import Intent, Result, SubAgent
from maverick.core.background import Background

WORD_RE = re.compile(r"[a-z0-9]+")
JOB_WORDS = {"job", "jobs", "background", "watcher", "watchers", "watching", "watches", "rotating", "rotation",
             "rotations", "monitoring", "tasks"}
STOP_WORDS = {"stop", "cancel", "remove", "end", "kill", "delete", "pause", "quit", "disable"}
FILLER = JOB_WORDS | STOP_WORDS | {"the", "a", "my", "all", "every", "please", "pls", "number", "no", "id", "for",
                                   "of", "that", "is", "which", "what", "show", "list", "running", "now", "in", "on"}
# "plan my maintenance between 10 pm and 2 am": a timetable from the 8.27 constraint solver.
PLAN_RE = re.compile(r"\b(?:plan|schedule|timetable)\b.*\b(?:maintenance|chores|jobs|tasks)\b"
                     r"|\b(?:maintenance|chores)\b.*\b(?:plan|schedule|timetable|when)\b"
                     r"|\bwhen\b.*\b(?:maintenance|chores)\b")
TIME_RE = re.compile(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b")
DEFAULT_WINDOW = (23 * 60, 1 * 60)  # 23:00-01:00


def minutes(match) -> int:
    hour, minute, half = int(match.group(1)) % 24, int(match.group(2) or 0), match.group(3)
    if half == "pm" and hour < 12:
        hour += 12
    if half == "am" and hour == 12:
        hour = 0
    return hour * 60 + minute


def plan_maintenance(start: int, end: int) -> Result:
    from maverick.brain.constraints import BEFORE, MAINTENANCE, clock, maintenance_csp

    csp = maintenance_csp(start, end)
    answer = csp.solve()
    window = f"{clock(start)}-{clock(end)}"
    if not answer:
        need = sum(j.minutes for j in MAINTENANCE if j.disk_heavy)
        return Result(False, f"No timetable fits {window}: the disk-heavy jobs alone need {need} minutes one after "
                             f"another. Try a longer window, e.g. 'plan maintenance between 11 pm and 2 am'.")
    by_name = {j.name: j for j in MAINTENANCE}
    lines = [f"Maintenance timetable for {window} (found after trying {csp.nodes} choices):"]
    for name, begin in sorted(answer.items(), key=lambda nv: nv[1]):
        lines.append(f"  {clock(begin)}-{clock(begin + by_name[name].minutes)}  {name}")
    lines.append("Every rule holds: disk-heavy jobs never overlap, at most 2 jobs at once, "
                 + ", ".join(f"'{a}' before '{b}'" for a, b in BEFORE) + ".")
    lines.append("This is a plan only: MAVERICK can't start jobs at set times yet (the 6.4 task scheduler was skipped).")
    return Result(True, "\n".join(lines), {"timetable": answer})


class JobsAgent(SubAgent):
    name = "jobs"
    description = ("background jobs (folder watchers, log rotators): list or stop them. "
                   "e.g. show background jobs  |  stop job 2  |  stop watching downloads")

    def __init__(self, background: Background):
        self.background = background

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower()))
        if PLAN_RE.search(text.lower()):
            return self.extract("plan", text)
        if not words & JOB_WORDS:
            return None
        # "watch downloads for pdfs" creates a job; that belongs to the watch agent.
        if not words & STOP_WORDS and not words & {"show", "list", "what", "which", "running", "jobs", "any"}:
            return None
        return self.extract("stop" if words & STOP_WORDS else "list", text)

    def extract(self, operation: str, text: str) -> Intent:
        if operation == "list":
            return Intent("list")
        if operation == "plan":
            times = [m for m in TIME_RE.finditer(text.lower()) if m.group(2) or m.group(3)]
            start, end = (minutes(times[0]), minutes(times[1])) if len(times) >= 2 else DEFAULT_WINDOW
            return Intent("plan", {"start": start, "end": end})
        words = WORD_RE.findall(text.lower())
        if set(words) & {"all", "every", "everything"}:
            return Intent("stop", {"which": "all"})
        number = next((w for w in words if w.isdigit()), "")
        if number:
            return Intent("stop", {"which": number})
        hints = [w for w in words if w not in FILLER]
        return Intent("stop", {"which": " ".join(hints)}, [] if hints else ["which job (say: show background jobs)"])

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "plan":
            return plan_maintenance(**intent.args)
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
