import re

from maverick.agents.files import ops
from maverick.core.agent_base import Intent, Result, SubAgent

# A token is either "a quoted path with spaces" or a run of non-space characters.
TOKEN_RE = re.compile(r'"([^"]+)"|(\S+)')

MOVE_WORDS = {"move", "cut", "transfer"}
COPY_WORDS = {"copy", "paste", "copy-paste", "duplicate"}
SIZE_WORDS = {"size", "big", "large", "space"}
FILLER_WORDS = {
    "the", "a", "an", "of", "to", "into", "from", "and", "is", "it", "me", "my",
    "how", "what", "whats", "what's", "retrieve", "get", "show", "check", "find",
    "please", "file", "folder", "directory", "this", "does", "take", "takes", "up",
}
KEYWORDS = MOVE_WORDS | COPY_WORDS | SIZE_WORDS | FILLER_WORDS


def split_words_and_paths(text: str) -> tuple[set[str], list[str]]:
    """Quoted tokens are always paths; unquoted tokens are paths unless they are known words."""
    words, paths = set(), []
    for quoted, plain in TOKEN_RE.findall(text):
        if quoted:
            paths.append(quoted)
            continue
        cleaned = plain.rstrip("?!.,;")
        if cleaned.lower() in KEYWORDS:
            words.add(cleaned.lower())
        elif cleaned:
            paths.append(cleaned)
    return words, paths


class FileAgent(SubAgent):
    name = "files"
    description = 'copy, move, and get the size of files/folders. e.g. copy notes.txt to D:\\backup  |  size of "C:\\My Folder"'

    def parse(self, text: str) -> Intent | None:
        words, paths = split_words_and_paths(text)

        if words & MOVE_WORDS:
            operation = "move"
        elif words & COPY_WORDS:
            operation = "copy"
        elif words & SIZE_WORDS:
            operation = "size"
        else:
            return None

        if operation == "size":
            return Intent("size", {"path": paths[0] if paths else ""}, [] if paths else ["path"])

        args = {"source": paths[0] if paths else "", "destination": paths[1] if len(paths) > 1 else ""}
        return Intent(operation, args, [k for k, v in args.items() if not v])

    def handle(self, intent: Intent) -> Result:
        operation = {"copy": ops.copy, "move": ops.move, "size": ops.size}[intent.operation]
        return operation(**intent.args)
