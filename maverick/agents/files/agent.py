import re

from maverick.agents.files import ops
from maverick.brain.text import looks_like_path
from maverick.core.agent_base import Intent, Result, SubAgent

# A token is either "a quoted path with spaces" or a run of non-space characters.
TOKEN_RE = re.compile(r'"([^"]+)"|(\S+)')

RENAME_WORDS = {"rename"}
MOVE_WORDS = {"move", "cut", "transfer"}
COPY_WORDS = {"copy", "paste", "copy-paste", "duplicate"}
SIZE_WORDS = {"size", "big", "large", "space"}
FILLER_WORDS = {
    "the", "a", "an", "of", "to", "into", "from", "and", "is", "it", "me", "my",
    "how", "what", "whats", "what's", "retrieve", "get", "show", "check", "find",
    "please", "file", "folder", "directory", "this", "does", "take", "takes", "up",
}
KEYWORDS = RENAME_WORDS | MOVE_WORDS | COPY_WORDS | SIZE_WORDS | FILLER_WORDS


def split_words_and_paths(text: str) -> tuple[set[str], list[str], list[str]]:
    """Splits text into known words, sure paths, and possible paths.

    sure paths:     quoted, or path-shaped (D:\\x, notes.txt)
    possible paths: every token that is not a known word, e.g. "photos" in "size of photos"
    """
    words, sure, possible = set(), [], []
    for quoted, plain in TOKEN_RE.findall(text):
        if quoted:
            sure.append(quoted)
            possible.append(quoted)
            continue
        cleaned = plain.rstrip("?!.,;")
        if cleaned.lower() in KEYWORDS:
            words.add(cleaned.lower())
        elif cleaned:
            possible.append(cleaned)
            if looks_like_path(cleaned):
                sure.append(cleaned)
    return words, sure, possible


class FileAgent(SubAgent):
    name = "files"
    description = 'copy, move, rename, and get the size of files/folders. e.g. copy notes.txt to D:\\backup  |  rename a.txt to b.txt'
    # Copy never overwrites and size only reads, so only these two ask first.
    risky = {"move", "rename"}

    def parse(self, text: str) -> Intent | None:
        words, _, _ = split_words_and_paths(text)

        if words & RENAME_WORDS:
            operation = "rename"
        elif words & MOVE_WORDS:
            operation = "move"
        elif words & COPY_WORDS:
            operation = "copy"
        elif words & SIZE_WORDS:
            operation = "size"
        else:
            return None
        return self.extract(operation, text)

    def extract(self, operation: str, text: str) -> Intent:
        _, sure, possible = split_words_and_paths(text)
        # Prefer path-shaped tokens; they survive chatty sentences like "make a duplicate of notes.txt in D:\x".
        needed = 1 if operation == "size" else 2
        paths = sure if len(sure) >= needed else possible

        if operation == "size":
            return Intent("size", {"path": paths[0] if paths else ""}, [] if paths else ["path"])

        second = "new_name" if operation == "rename" else "destination"
        args = {"source": paths[0] if paths else "", second: paths[1] if len(paths) > 1 else ""}
        return Intent(operation, args, [k for k, v in args.items() if not v])

    def describe(self, intent: Intent) -> str:
        if intent.operation == "move":
            src, dest = ops.plan_move(**intent.args)
            return f"Move {src} -> {dest}?"
        src, target = ops.plan_rename(**intent.args)
        return f"Rename {src} -> {target.name}?"

    def handle(self, intent: Intent) -> Result:
        operation = {"copy": ops.copy, "move": ops.move, "rename": ops.rename, "size": ops.size}[intent.operation]
        return operation(**intent.args)
