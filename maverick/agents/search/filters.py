"""Turn a search sentence into filters: where to look, name, file kinds, dates, sizes, and text inside.

"find pdf files bigger than 2 mb edited this week in downloads"
  -> root=~/Downloads, exts=[pdf], min_size=2 MB, after=Monday 00:00
"""
import re
from datetime import datetime, timedelta
from pathlib import Path

from maverick.brain.text import looks_like_path

UNITS = {"b": 1, "kb": 1024, "mb": 1024 ** 2, "gb": 1024 ** 3, "tb": 1024 ** 4}
BIG_DEFAULT = 100 * 1024 ** 2  # "big files" with no number means over 100 MB

IMAGES = ["jpg", "jpeg", "png", "gif", "bmp", "webp", "heic"]
VIDEOS = ["mp4", "mkv", "avi", "mov", "wmv", "webm"]
AUDIO = ["mp3", "wav", "flac", "m4a", "aac", "ogg"]
DOCS = ["pdf", "doc", "docx", "txt", "md", "xls", "xlsx", "csv", "ppt", "pptx"]
ARCHIVES = ["zip", "rar", "7z", "tar", "gz"]
KINDS = {
    "images": IMAGES, "image": IMAGES, "photos": IMAGES, "photo": IMAGES, "pictures": IMAGES, "pics": IMAGES,
    "screenshots": ["png", "jpg"], "videos": VIDEOS, "video": VIDEOS, "movies": VIDEOS, "movie": VIDEOS,
    "films": VIDEOS, "music": AUDIO, "songs": AUDIO, "song": AUDIO, "audio": AUDIO, "documents": DOCS,
    "docs": DOCS, "pdfs": ["pdf"], "spreadsheets": ["xls", "xlsx", "csv"], "excel": ["xls", "xlsx"],
    "word": ["doc", "docx"], "presentations": ["ppt", "pptx"], "zips": ARCHIVES, "archives": ARCHIVES,
    "python": ["py"], "text": ["txt", "md"], "notes": ["txt", "md"], "installers": ["exe", "msi"],
    "code": ["py", "js", "ts", "java", "c", "cpp", "cs", "html", "css"],
}
EXT_WORDS = {"pdf", "docx", "doc", "txt", "md", "xlsx", "csv", "pptx", "mp4", "mkv", "avi", "mov", "mp3",
             "wav", "flac", "jpg", "jpeg", "png", "gif", "zip", "rar", "7z", "iso", "exe", "py", "json", "log"}
FOLDERS = {"downloads": "Downloads", "documents": "Documents", "desktop": "Desktop",
           "pictures": "Pictures", "music": "Music", "videos": "Videos"}
FILLER = {
    "find", "search", "look", "looking", "locate", "where", "is", "are", "my", "the", "a", "an", "all", "any",
    "every", "files", "file", "folder", "folders", "for", "called", "named", "name", "with", "in", "inside",
    "on", "from", "under", "me", "show", "list", "get", "which", "that", "were", "was", "i", "edited",
    "modified", "changed", "saved", "created", "made", "updated", "please", "pls", "can", "you", "u", "could",
    "there", "have", "has", "had", "did", "do", "does", "some", "of", "to", "and", "it", "its", "them",
    "those", "these", "what", "whats", "ones", "big", "large", "huge", "biggest", "largest", "drive", "disk",
    "recently", "recent", "ago", "anything", "something", "somewhere", "kept", "put", "store", "stored",
}

QUOTED_RE = re.compile(r'"([^"]+)"')
SIZE_RE = re.compile(r"\b(bigger|larger|more|over|above|greater|heavier|smaller|less|under|below|lighter)"
                     r"\s+(?:than\s+)?(\d+(?:\.\d+)?)\s*(tb|gb|mb|kb|b)\b")
CONTAINS_RE = re.compile(r"\b(?:containing|contains|contain|mentioning|mentions|mention|saying|that say|that says"
                         r"|with the (?:word|text)|the (?:word|text))\s+(\"[^\"]+\"|\S+)")
DRIVE_RE = re.compile(r"\b([b-z])\s*(?:drive|disk)\b|\bdrive\s+([b-z])\b")
FOLDER_RE = re.compile(r"\b(?:in|inside|from|on|under)\s+(?:my\s+|the\s+)?(" + "|".join(FOLDERS) + r")\b")
RELATIVE_RE = re.compile(r"\b(?:last|past)\s+(\d+)\s+(hours?|days?|weeks?|months?)\b")
OLDER_RE = re.compile(r"\bolder\s+than\s+(\d+)\s+(days?|weeks?|months?|years?)\b")
DAYS = {"hour": 1 / 24, "day": 1, "week": 7, "month": 30, "year": 365}


def parse_query(text: str, now: datetime | None = None) -> dict:
    now = now or datetime.now()
    rest = text
    filters: dict = {}

    def cut(match):  # remove what a filter used, so it isn't mistaken for part of the file name
        nonlocal rest
        rest = rest.replace(match.group(0), " ", 1)

    # Text to look for inside files.
    if m := CONTAINS_RE.search(rest):
        filters["contains"] = m.group(1).strip('"')
        cut(m)

    # Where to look: a typed path, "e drive", or "in downloads".
    for m in QUOTED_RE.finditer(rest):
        if looks_like_path(m.group(1)) and ("\\" in m.group(1) or ":" in m.group(1)):
            filters["root"] = m.group(1)
            cut(m)
            break
    if "root" not in filters:
        for token in rest.split():
            token = token.rstrip("?!.,;")
            if "*" not in token and re.search(r"[\\/]|^[A-Za-z]:", token):
                filters["root"] = token + ("\\" if re.fullmatch(r"[A-Za-z]:", token) else "")
                rest = rest.replace(token, " ", 1)
                break
    low = rest.lower()
    if "root" not in filters and (m := DRIVE_RE.search(low)):
        filters["root"] = f"{(m.group(1) or m.group(2)).upper()}:\\"
        rest = rest[:m.start()] + " " + rest[m.end():]
    low = rest.lower()
    if "root" not in filters and (m := FOLDER_RE.search(low)):
        filters["root"] = str(Path.home() / FOLDERS[m.group(1)])
        rest = rest[:m.start()] + " " + rest[m.end():]

    # Size.
    low = rest.lower()
    if m := SIZE_RE.search(low):
        amount = int(float(m.group(2)) * UNITS[m.group(3)])
        smaller = m.group(1) in {"smaller", "less", "under", "below", "lighter"}
        filters["max_size" if smaller else "min_size"] = amount
        rest = rest[:m.start()] + " " + rest[m.end():]
    elif re.search(r"\b(big|large|huge|biggest|largest)\b", low):
        filters["min_size"] = BIG_DEFAULT

    # Dates (always the "last modified" time).
    low = rest.lower()
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if m := RELATIVE_RE.search(low):
        filters["after"] = (now - timedelta(days=int(m.group(1)) * DAYS[m.group(2).rstrip("s")])).timestamp()
    elif m := OLDER_RE.search(low):
        filters["before"] = (now - timedelta(days=int(m.group(1)) * DAYS[m.group(2).rstrip("s")])).timestamp()
    elif "yesterday" in low:
        filters["after"], filters["before"] = (midnight - timedelta(days=1)).timestamp(), midnight.timestamp()
    elif "today" in low:
        filters["after"] = midnight.timestamp()
    elif "this week" in low:
        filters["after"] = (midnight - timedelta(days=now.weekday())).timestamp()
    elif "this month" in low:
        filters["after"] = midnight.replace(day=1).timestamp()
    elif re.search(r"\b(last week|recently|recent)\b", low):
        filters["after"] = (now - timedelta(days=7)).timestamp()
    elif "last month" in low:
        filters["after"] = (now - timedelta(days=30)).timestamp()
    for phrase in (RELATIVE_RE, OLDER_RE):
        rest = phrase.sub(" ", rest.lower())
    rest = re.sub(r"\b(yesterday|today|this week|this month|last week|last month)\b", " ", rest.lower())

    # File kinds: "*.pdf", "pdf", "videos".
    exts, name_words = [], []
    for word in re.findall(r"[\w.*-]+", rest.lower()):
        if word.startswith("*."):
            exts.append(word[2:])
        elif word in KINDS:
            exts += KINDS[word]
        elif word in EXT_WORDS:
            exts.append(word)
        elif word not in FILLER and word not in {"than", "this", "last", "past", "older", "days", "weeks"}:
            name_words.append(word)
    if exts:
        filters["exts"] = sorted(set(exts))
    if name_words:
        filters["name"] = " ".join(name_words)
    return filters
