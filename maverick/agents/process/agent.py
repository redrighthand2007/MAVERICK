import re

from maverick.agents.process import ops
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z0-9_.\-]+")

PROCESS_WORDS = {"process", "processes", "programs", "program", "apps", "tasks", "pid", "running",
                 "started", "launched", "opened", "parent", "children", "child", "spawned"}
ORIGIN_WORDS = {"started", "launched", "opened", "parent", "why", "who", "origin"}
CHILD_WORDS = {"children", "child", "spawned", "subprocesses"}
# Words that never name a program, so they are skipped when looking for "chrome" in "what started chrome".
FILLER = {
    "what", "whats", "which", "who", "why", "is", "are", "was", "the", "a", "an", "my", "this", "that", "it",
    "process", "processes", "program", "programs", "app", "apps", "task", "tasks", "pid", "running", "run",
    "started", "start", "launched", "launch", "opened", "open", "parent", "children", "child", "spawned",
    "did", "does", "do", "show", "me", "list", "of", "by", "for", "from", "on", "in", "please", "pls",
    "tell", "origin", "behind", "where", "come", "came", "comes", "subprocesses", "has", "have", "under",
}


def target_name(text: str) -> str:
    """The program being asked about: a PID, a name.exe, or the first word that isn't filler."""
    words = WORD_RE.findall(text.lower().replace("'", ""))
    for i, word in enumerate(words):
        if word == "pid" and i + 1 < len(words) and words[i + 1].isdigit():
            return words[i + 1]
    exe = next((w for w in words if w.endswith(".exe")), None)
    if exe:
        return exe
    return next((w.strip(".?!,") for w in words if w.strip(".?!,") not in FILLER), "")


class ProcessAgent(SubAgent):
    name = "process"
    description = "running programs: biggest by RAM or CPU, what started a program, what it started. e.g. what started chrome"

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower()))
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
        if operation == "list":
            return Intent("list", {"sort": "cpu" if re.search(r"\b(cpu|processor)\b", text.lower()) else "memory"})
        name = target_name(text)
        return Intent(operation, {"name": name}, [] if name else ["program name"])

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "list":
            return ops.top(**intent.args)
        return {"origin": ops.origin, "children": ops.children}[intent.operation](**intent.args)
