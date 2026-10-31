import re
from pathlib import Path

from maverick.agents.files.agent import TOKEN_RE
from maverick.agents.search.filters import EXT_WORDS, FOLDERS, KINDS
from maverick.agents.watch import ops
from maverick.core.agent_base import Intent, Result, SubAgent
from maverick.core.background import Background

WATCH_RE = re.compile(r"\bwatch\b|\bmonitor\b|\bkeep an eye\b|\bwhenever\b|\bevery new\b|\beach new\b|\bany new\b"
                      r"|\b(?:move|copy|send|put)\s+(?:all\s+)?new\b|\bautomatically\b|\bauto[- ]?(?:move|sort|copy)\b|\bnew\b.*\b(?:arrive|arrives|appear|appears|lands?)\b")
COPY_WORDS = {"copy", "copies", "backup", "back", "duplicate"}
# A folder word only means the folder after one of these: "new videos in downloads to videos" = kind, then folders.
BEFORE_FOLDER = {"to", "into", "in", "from", "my", "the", "watch", "monitor", "on", "inside", "of", "over"}
TO_WORDS = {"to", "into"}


def find_folders(text: str) -> tuple[str, str, list[str]]:
    """(source folder, destination folder, extensions) from a watcher sentence."""
    source = destination = ""
    exts: set[str] = set()
    previous, heading_to = "", False
    for quoted, plain in TOKEN_RE.findall(text):
        raw = quoted or plain.rstrip("?!.,;")
        low = raw.lower()
        folder = ""
        if quoted or re.match(r"^[a-z]:\\|^\\\\|^~", low):
            folder = raw
        elif low in FOLDERS and previous in BEFORE_FOLDER:
            folder = str(Path.home() / FOLDERS[low])
        elif low in KINDS or low + "s" in KINDS:  # "photos", "screenshot"
            exts.update(KINDS.get(low) or KINDS[low + "s"])
        elif low.lstrip("*.") in EXT_WORDS:
            exts.add(low.lstrip("*."))
        elif low.endswith("s") and low[:-1] in EXT_WORDS:  # "pdfs", "pngs"
            exts.add(low[:-1])
        if low in TO_WORDS:
            heading_to = True
        if folder:
            if heading_to and not destination:
                destination = folder
            elif not source:
                source = folder
            heading_to = False
        if low not in {"my", "the"}:
            previous = low
    return source, destination, sorted(exts)


class WatchAgent(SubAgent):
    name = "watch"
    description = ("folder watcher (runs in the background): move or copy every new file of a kind. "
                   "e.g. move every new pdf in downloads to documents")
    risky = {"start"}  # it will move files on its own later, so it asks once now

    def __init__(self, background: Background):
        self.background = background

    def parse(self, text: str) -> Intent | None:
        if not WATCH_RE.search(text.lower()):
            return None
        return self.extract("start", text)

    def extract(self, operation: str, text: str) -> Intent:
        source, destination, exts = find_folders(text)
        action = "copy" if set(re.findall(r"[a-z]+", text.lower())) & COPY_WORDS else "move"
        args = {"source": source, "destination": destination, "exts": exts, "action": action}
        missing = [label for label, value in (("folder to watch", source), ("where to put the files", destination))
                   if not value]
        return Intent("start", args, missing)

    def describe(self, intent: Intent) -> str:
        return ops.describe(**intent.args)

    def handle(self, intent: Intent) -> Result:
        return ops.start(self.background, **intent.args)
