import re

from maverick.agents.search import ops
from maverick.agents.search.filters import parse_query
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z]+")
SEARCH_WORDS = {"find", "search", "locate", "where", "look", "looking"}
# "find size of x" and "find x and copy it" belong to the files agent.
OTHER_JOBS = {"size", "copy", "move", "rename", "duplicate", "transfer"}


class SearchAgent(SubAgent):
    name = "search"
    description = ('find files by name, kind, date, size or text inside. e.g. find dune movie in e drive  |  '
                   'pdf files edited this week in downloads  |  files containing "password"')

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower()))
        if not words & SEARCH_WORDS or words & OTHER_JOBS:
            return None
        operation = "content" if parse_query(text).get("contains") else "find"
        return self.extract(operation, text)

    def extract(self, operation: str, text: str) -> Intent:
        filters = parse_query(text)
        if operation == "content":
            return Intent("content", filters, [] if filters.get("contains") else ["text to look for"])
        # The brain may pick "find" for a sentence that also names text inside; keep that filter.
        what = {"name", "exts", "after", "before", "min_size", "max_size", "contains"}
        return Intent("find", filters, [] if what & filters.keys() else ["what to look for"])

    def handle(self, intent: Intent) -> Result:
        return ops.find(**intent.args)
