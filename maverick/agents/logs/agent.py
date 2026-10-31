import re

from maverick.agents.files.agent import split_words_and_paths
from maverick.agents.logs import ops
from maverick.core.agent_base import Intent, Result, SubAgent
from maverick.core.background import Background

ROTATE_RE = re.compile(r"\brotat|\btruncate\b|\b(?:empty|clear|shrink|trim|compress|archive|reset)\b.*\blogs?\b"
                       r"|\blogs?\b.*\b(?:too big|huge|growing|bigger than|over|larger than)\b")
SIZE_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(kb|mb|gb)\b")
UNITS = {"kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3}
NOT_PATHS = {"rotate", "rotation", "log", "logs", "file", "when", "whenever", "it", "gets", "bigger", "than", "over",
             "every", "time", "truncate", "empty", "clear", "compress", "the", "my", "please", "grows", "past",
             "larger", "goes", "above", "is", "reaches", "keep", "small", "and", "a", "an", "of", "trim", "shrink"}


class LogsAgent(SubAgent):
    name = "logs"
    description = ("log rotator: save a big log as a dated .gz and empty it, now or whenever it grows too big. "
                   "e.g. rotate D:\\app\\server.log  |  rotate server.log when it gets bigger than 50 mb")
    risky = {"rotate"}  # it empties the log (after saving a copy)

    def __init__(self, background: Background):
        self.background = background

    def parse(self, text: str) -> Intent | None:
        # Paths don't count as words: "compress D:\logs as tar.gz" is an archive job, not a log rotation.
        words_only = text
        for path in split_words_and_paths(text)[1]:
            words_only = words_only.replace(path, " ")
        if not ROTATE_RE.search(words_only.lower()) and not re.search(r"\brotat|\btruncate\b", text.lower()):
            return None
        return self.extract("rotate", text)

    def extract(self, operation: str, text: str) -> Intent:
        _, sure, possible = split_words_and_paths(text)
        candidates = [p for p in sure if not SIZE_RE.fullmatch(p.lower())]
        logs = [p for p in candidates if p.lower().endswith((".log", ".txt", ".out"))] or candidates
        if not logs:
            logs = [p for p in possible if p.lower() not in NOT_PATHS and not SIZE_RE.fullmatch(p.lower())
                    and not p.isdigit() and p.lower() not in UNITS]
        size = SIZE_RE.search(text.lower())
        max_size = int(float(size.group(1)) * UNITS[size.group(2)]) if size else 0
        args = {"path": logs[0] if logs else "", "max_size": max_size}
        return Intent("rotate", args, [] if logs else ["log file"])

    def describe(self, intent: Intent) -> str:
        return ops.describe(**intent.args)

    def handle(self, intent: Intent) -> Result:
        if intent.args["max_size"]:
            return ops.start(self.background, **intent.args)
        return ops.rotate(intent.args["path"])
