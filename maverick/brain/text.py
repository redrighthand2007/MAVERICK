import re

PATH = "<path>"
QUOTED_RE = re.compile(r'"[^"]*"')
WORD_RE = re.compile(r"[a-z0-9]+")
# Has a slash, starts with a drive letter (D:), or ends in a file extension (.txt).
PATH_LIKE_RE = re.compile(r"[\\/]|^[a-zA-Z]:|\.[A-Za-z0-9]{1,6}$")


def looks_like_path(token: str) -> bool:
    return bool(PATH_LIKE_RE.search(token))


def tokenize(sentence: str) -> list[str]:
    """Turn a sentence into lowercase words, with every path replaced by <path>.

    "copy notes.txt to D:\\backup"  ->  ["copy", "<path>", "to", "<path>"]
    Paths say nothing about WHICH operation you want, so the brain never sees them.
    """
    sentence = QUOTED_RE.sub(f" {PATH} ", sentence)
    tokens = []
    for raw in sentence.split():
        if raw == PATH:
            tokens.append(PATH)
            continue
        cleaned = raw.rstrip("?!.,;")
        if looks_like_path(cleaned):
            tokens.append(PATH)
        else:
            tokens.extend(WORD_RE.findall(cleaned.lower().replace("'", "")))
    return tokens
