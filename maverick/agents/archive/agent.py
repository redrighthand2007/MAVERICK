import getpass
import re
from pathlib import Path

from maverick.agents.archive import ops
from maverick.agents.files.agent import TOKEN_RE
from maverick.brain.text import looks_like_path
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z.]+")
CREATE_WORDS = {"zip", "compress", "archive", "pack", "encrypt", "tar", "bundle"}
EXTRACT_WORDS = {"unzip", "extract", "unpack", "decompress", "untar", "unarchive"}
LIST_WORDS = {"inside", "contents", "content", "list", "peek", "in"}
LOCK_WORDS = {"password", "encrypt", "encrypted", "lock", "locked", "protect", "protected", "aes", "secure"}
ARCHIVE_RE = re.compile(r"\.(zip|tar|tgz|gz|bz2|xz)$", re.IGNORECASE)
NOT_A_PATH = CREATE_WORDS | EXTRACT_WORDS | LOCK_WORDS | {
    "the", "a", "an", "my", "this", "folder", "file", "files", "to", "into", "in", "as", "with", "and", "please", "pls",
    "of", "it", "up", "everything", "contents", "inside", "list", "show", "what", "whats", "what's", "is", "me",
    "can", "you", "u", "for", "a.zip", "zip.", "tar.gz", "tgz", "using", "here", "make", "create", "put", "out",
}


def split(text: str) -> tuple[set[str], list[str]]:
    """Words outside paths ("D:\\archive" is a path, not the word archive), and the paths themselves."""
    words, paths = set(), []
    for quoted, plain in TOKEN_RE.findall(text):
        if quoted:
            paths.append(quoted)
            continue
        cleaned = plain.rstrip("?!,;")
        low = cleaned.lower().replace("'", "")
        if looks_like_path(cleaned) and low not in NOT_A_PATH:
            paths.append(cleaned)
        else:
            words.update(WORD_RE.findall(low))
    return words, paths


def ask_password(prompt: str) -> str:
    """Typed at a hidden prompt, so passwords never appear in the request (or in inbox.tsv)."""
    return getpass.getpass(f"MAVERICK: {prompt} ")


class ArchiveAgent(SubAgent):
    name = "archive"
    description = ("zip / tar archives: create (optionally AES password), list what's inside, extract safely. "
                   "e.g. zip D:\\work with a password  |  what's inside backup.zip  |  unzip backup.zip")
    ask_password = staticmethod(ask_password)  # tests swap this for a fake

    def parse(self, text: str) -> Intent | None:
        words, paths = split(text)
        if words & EXTRACT_WORDS:
            return self.extract("extract", text)
        if words & LIST_WORDS and any(ARCHIVE_RE.search(p) for p in paths) and not words & CREATE_WORDS - {"zip", "tar"}:
            return self.extract("list", text)
        if words & CREATE_WORDS:
            return self.extract("create", text)
        return None

    def extract(self, operation: str, text: str) -> Intent:
        words, paths = split(text)
        if operation in ("list", "extract"):
            archives = [p for p in paths if ARCHIVE_RE.search(p)] or paths
            if not archives:
                return Intent(operation, {}, ["archive file"])
            args = {"archive": archives[0]}
            if operation == "extract":
                rest = [p for p in paths if p != archives[0]]
                args["destination"] = rest[0] if rest else ""
            return Intent(operation, args)
        low = text.lower()
        fmt = "tar.gz" if re.search(r"tar\.gz|tgz|gzip", low) else "tar" if "tar" in words else "zip"
        args = {"source": paths[0] if paths else "", "output": paths[1] if len(paths) > 1 else "", "fmt": fmt,
                "encrypt": bool(words & LOCK_WORDS)}
        return Intent("create", args, [] if paths else ["file or folder to archive"])

    def handle(self, intent: Intent) -> Result:
        args = dict(intent.args)
        if intent.operation == "list":
            return ops.list_contents(**args)
        if intent.operation == "extract":
            ops.plan_extract(**args)  # check safety before asking for a password
            if ops.is_encrypted(Path(args["archive"].strip('"'))):
                args["password"] = self.ask_password(f"Password for {Path(args['archive']).name}:")
            return ops.extract(**args)
        if args.pop("encrypt"):
            ops.plan_create(**args)
            password = self.ask_password("Choose a password:")
            if not password:
                return Result(False, "No password typed; nothing was created.")
            if self.ask_password("Type it again:") != password:
                return Result(False, "The two passwords don't match; nothing was created.")
            args["password"] = password
        return ops.create(**args)
