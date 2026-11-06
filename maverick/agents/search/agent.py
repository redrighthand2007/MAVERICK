import re
from pathlib import Path

from maverick.agents.search import ops
from maverick.agents.search.filters import FOLDERS, parse_query
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z]+")
SEARCH_WORDS = {"find", "search", "locate", "where", "look", "looking"}
# "group my downloads", "what kinds of files are in documents": 8.23 clustering, read-only.
GROUP_RE = re.compile(r"\b(?:group|groups|grouped|cluster|clusters|categori[sz]e|organi[sz]e|sort out)\b"
                      r"|\bwhat (?:kinds?|sorts?|types?) of files\b|\bsimilar files\b")
# "find size of x" and "find x and copy it" belong to the files agent.
OTHER_JOBS = {"size", "copy", "move", "rename", "duplicate", "transfer"}


class SearchAgent(SubAgent):
    name = "search"
    description = ('find files by name, kind, date, size or text inside. e.g. find dune movie in e drive  |  '
                   'pdf files edited this week in downloads  |  files containing "password"  |  group the files in downloads')

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower()))
        if GROUP_RE.search(text.lower()) and words & ({"files", "file"} | FOLDERS.keys()) and not words & OTHER_JOBS:
            return self.extract("group", text)
        if not words & SEARCH_WORDS or words & OTHER_JOBS:
            return None
        operation = "content" if parse_query(text).get("contains") else "find"
        return self.extract(operation, text)

    def extract(self, operation: str, text: str) -> Intent:
        filters = parse_query(text)
        if operation == "group":
            # "in D:\work" / "in my downloads", or just "my desktop"; Downloads when no folder is named.
            folder = next((f for w, f in FOLDERS.items() if w in set(WORD_RE.findall(text.lower()))), "")
            return Intent("group", {"root": filters.get("root") or (str(Path.home() / folder) if folder else "")})
        if operation == "content":
            return Intent("content", filters, [] if filters.get("contains") else ["text to look for"])
        # The brain may pick "find" for a sentence that also names text inside; keep that filter.
        what = {"name", "exts", "after", "before", "min_size", "max_size", "contains"}
        return Intent("find", filters, [] if what & filters.keys() else ["what to look for"])

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "group":
            return ops.group(**intent.args)
        return ops.find(**intent.args)
