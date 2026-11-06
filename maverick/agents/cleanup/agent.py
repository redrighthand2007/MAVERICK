import re

from maverick.agents.cleanup import ops
from maverick.agents.files.agent import split_words_and_paths
from maverick.agents.search.filters import DRIVE_RE
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z]+")
# "free up 5 gb", "i need 10 GB of room on D:": a GOAL, so MAVERICK plans which files (8.26).
AMOUNT_RE = re.compile(r"\b(\d+(?:\.\d+)?)\s*(gb|gigs?|g|mb|tb)\b")
UNITS = {"gb": 1024 ** 3, "gig": 1024 ** 3, "gigs": 1024 ** 3, "g": 1024 ** 3, "mb": 1024 ** 2, "tb": 1024 ** 4}
DELETE_WORDS = {"delete", "remove", "trash", "recycle", "erase", "bin"}
TEMP_WORDS = {"temp", "temporary", "tmp", "junk", "cache"}
# "free up", "clean", "make room": wanting space back, not asking how much is free (that's hardware).
SCAN_RE = re.compile(r"\bfree\s+up\b|\bclean|\bclear|\bdeclutter|\breclaim|\bmake\s+(?:some\s+)?(?:space|room)\b"
                     r"|\bwhat\s+can\s+i\s+delete\b|\bjunk\b|\bwasting\s+space\b|\bspace\s+hogs?\b")


class CleanupAgent(SubAgent):
    name = "cleanup"
    description = ("free up disk space: find temp files, big files, old downloads; delete to the Recycle Bin. "
                   "e.g. free up space  |  free up 5 GB  |  clear temp files  |  delete D:\\old.zip")
    risky = {"recycle", "free"}

    def parse(self, text: str) -> Intent | None:
        low = text.lower()
        words = set(WORD_RE.findall(low))
        if "empty" in words and "bin" in words:
            return None  # emptying the Recycle Bin is a permanent delete; MAVERICK doesn't do those
        if re.search(r"\bwhat\s+can\s+i\s+(?:delete|remove)\b", low):
            return self.extract("scan", text)
        if AMOUNT_RE.search(low) and (SCAN_RE.search(low) or re.search(r"\b(?:need|make|get)\b.*\b(?:free|room|space)\b", low)):
            return self.extract("free", text)
        if words & DELETE_WORDS or (SCAN_RE.search(low) and words & TEMP_WORDS):
            return self.extract("recycle", text)
        if SCAN_RE.search(low):
            return self.extract("scan", text)
        return None

    def extract(self, operation: str, text: str) -> Intent:
        low = text.lower()
        if operation in ("scan", "free"):
            drive = DRIVE_RE.search(low)
            letter = (drive.group(1) or drive.group(2)) if drive else None
            if not letter and (typed := re.search(r"\b([b-z]):", low)):
                letter = typed.group(1)
            root = f"{letter.upper()}:\\" if letter else ""
            if operation == "scan":
                return Intent("scan", {"root": root})
            amount = AMOUNT_RE.search(low)
            if not amount:
                return Intent("free", {"goal": 0, "root": root}, ["how much space (e.g. 5 GB)"])
            return Intent("free", {"goal": int(float(amount.group(1)) * UNITS[amount.group(2)]), "root": root})
        _, sure, possible = split_words_and_paths(text)
        # A typed path wins: "delete C:\...\Temp\old.zip" is one file, not "clear temp files".
        if not sure and set(WORD_RE.findall(low)) & TEMP_WORDS:
            return Intent("recycle", {"target": "temp"})
        paths = sure or [p for p in possible if p.lower() not in DELETE_WORDS | {"permanently", "please", "pls"}]
        return Intent("recycle", {"target": paths[0] if paths else ""}, [] if paths else ["what to delete"])

    def describe(self, intent: Intent) -> str:
        if intent.operation == "free":
            return ops.describe_free(**intent.args)
        return ops.describe_recycle(**intent.args)

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "scan":
            return ops.scan(**intent.args)
        if intent.operation == "free":
            return ops.free(**intent.args)
        return ops.recycle(**intent.args)
