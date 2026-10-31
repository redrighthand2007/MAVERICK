import re

from maverick.agents.process import ops
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z0-9_.\-]+")

PROCESS_WORDS = {"process", "processes", "programs", "program", "apps", "tasks", "pid", "running",
                 "started", "launched", "opened", "parent", "children", "child", "spawned"}
ORIGIN_WORDS = {"started", "launched", "opened", "parent", "why", "who", "origin"}
CHILD_WORDS = {"children", "child", "spawned", "subprocesses"}
HEAVY_WORDS = {"most", "biggest", "heaviest", "hungriest", "top"}
END_WORDS = {"end", "kill", "close", "terminate", "stop", "quit"}
# "stop the spooler service", "stop watching downloads", "kill the process on port 8080" belong to other agents.
NOT_END = {"service", "services", "job", "jobs", "watcher", "watching", "watch", "rotating", "rotation", "wifi", "wi-fi", "port",
           "device", "bluetooth", "window", "windows"}
GROW_RE = re.compile(r"\bleak|\b(?:ram|memory)\b.*\b(?:grow|grows|growing|growth|increasing|climbing|creeping|going up)\b"
                     r"|\b(?:grow|grows|growing|keeps growing)\b.*\b(?:ram|memory)\b")
HANDLES_RE = re.compile(r"\bhandles?\b.*\b(?:leak|leaks|leaking|too many|most|count|counts|open|usage|using|hog)"
                        r"|\b(?:most|many|top|count|leaking|open)\b.*\bhandles\b")
DURATION_RE = re.compile(r"\bfor\s+(\d+)\s*(seconds?|secs?|s|minutes?|mins?|m)\b")
HUNG_RE = re.compile(r"not\s+responding|\bfrozen\b|\bfreez|\bhung\b|\bhanging\b|\bstuck\b|\bunresponsive\b")
HUNG_FILLER = {"frozen", "freezing", "freezed", "frozen.", "stuck", "hung", "hanging", "unresponsive", "not", "responding",
               "window", "windows", "everything", "any", "there", "its", "every", "again", "and", "up", "thats", "anything"}
# Words that never name a program, so they are skipped when looking for "chrome" in "what started chrome".
FILLER = {
    "what", "whats", "which", "who", "why", "is", "are", "was", "the", "a", "an", "my", "this", "that", "it",
    "process", "processes", "program", "programs", "app", "apps", "task", "tasks", "pid", "running", "run",
    "started", "start", "launched", "launch", "opened", "open", "parent", "children", "child", "spawned",
    "did", "does", "do", "show", "me", "list", "of", "by", "for", "from", "on", "in", "please", "pls",
    "tell", "origin", "behind", "where", "come", "came", "comes", "subprocesses", "has", "have", "under",
    "end", "kill", "close", "terminate", "stop", "quit", "force", "can", "you", "u", "now", "all", "every",
}


def target_name(text: str, extra_filler: set[str] = frozenset()) -> str:
    """The program being asked about: a PID, a name.exe, or the first word that isn't filler."""
    words = WORD_RE.findall(text.lower().replace("'", ""))
    for i, word in enumerate(words):
        if word == "pid" and i + 1 < len(words) and words[i + 1].isdigit():
            return words[i + 1]
    exe = next((w for w in words if w.endswith(".exe")), None)
    if exe:
        return exe
    skip = FILLER | extra_filler
    return next((w.strip(".?!,") for w in words if w.strip(".?!,") not in skip), "")


class ProcessAgent(SubAgent):
    name = "process"
    description = ("running programs: biggest by RAM or CPU, what started a program, what it started, end a program, "
                   "frozen apps, memory leaks. e.g. what started chrome, kill chrome, end frozen apps, "
                   "which app is leaking memory, which app has the most handles")
    risky = {"end"}

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower()))
        if HANDLES_RE.search(text.lower()):  # before GROW_RE: a "handle leak" is not a memory leak
            return self.extract("handles", text)
        if GROW_RE.search(text.lower()):
            return self.extract("growing", text)
        if HUNG_RE.search(text.lower()):
            return self.extract("hung", text)
        if words & END_WORDS and not words & NOT_END:
            return self.extract("end", text)
        did_start = "did" in words and bool(words & {"start", "launch", "open"})  # "what did explorer start"
        if not (words & PROCESS_WORDS or did_start) or ("running" in words and "out" in words):  # "running out of space" isn't a process
            return None
        if words & CHILD_WORDS or did_start:
            operation = "children"
        elif words & ORIGIN_WORDS:
            operation = "origin"
        else:
            operation = "list"
        return self.extract(operation, text)

    def extract(self, operation: str, text: str) -> Intent:
        if operation == "handles":
            return Intent("handles")
        if operation == "growing":
            # "watch for 2 minutes" / "for 30 seconds"; a short default keeps MAVERICK responsive.
            m = DURATION_RE.search(text.lower())
            seconds = int(m.group(1)) * (60 if m.group(2).startswith("m") else 1) if m else 10
            return Intent("growing", {"seconds": seconds})
        if operation == "hung":
            if not set(WORD_RE.findall(text.lower())) & END_WORDS:
                return Intent("hung", {"end": False})
            # "kill excel, it's frozen" names one program; "end frozen apps" means every frozen one.
            name = target_name(text, HUNG_FILLER)
            return Intent("end", {"name": name}) if name else Intent("hung", {"end": True})
        if operation == "list":
            return Intent("list", {"sort": "cpu" if re.search(r"\b(cpu|processor)\b", text.lower()) else "memory"})
        if operation == "end" and set(WORD_RE.findall(text.lower())) & HEAVY_WORDS:
            # "kill whatever uses the most cpu": hunt down the top program first.
            sort = "cpu" if re.search(r"\b(cpu|processor)\b", text.lower()) else "memory"
            name = ops.heaviest(sort)
            return Intent("end", {"name": name}, [] if name else ["program name"])
        name = target_name(text)
        return Intent(operation, {"name": name}, [] if name else ["program name"])

    def is_risky(self, intent: Intent) -> bool:
        return intent.operation == "end" or (intent.operation == "hung" and intent.args.get("end", False))

    def describe(self, intent: Intent) -> str:
        if intent.operation == "hung":
            return ops.describe_end_hung()
        return ops.describe_end(ops.plan_end(**intent.args))

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "handles":
            return ops.handles()
        if intent.operation == "growing":
            return ops.growing(**intent.args)
        if intent.operation == "hung":
            return ops.end_hung() if intent.args["end"] else ops.hung()
        if intent.operation == "end":
            return ops.end(**intent.args)
        if intent.operation == "list":
            return ops.top(**intent.args)
        return {"origin": ops.origin, "children": ops.children}[intent.operation](**intent.args)
