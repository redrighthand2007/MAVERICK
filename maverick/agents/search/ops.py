"""Read-only file search. Nothing here changes, moves or opens a file."""
import os
import re
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np

from maverick.agents.search.filters import ARCHIVES, AUDIO, DOCS, IMAGES, VIDEOS
from maverick.core.agent_base import Result
from maverick.core.safety import require_existing
from maverick.core.units import human_size

# Folders that are huge, system-owned, or never hold your own files. Skipped below the starting folder.
SKIP_DIRS = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "appdata",
             "system volume information", "node_modules", ".git", "__pycache__", ".venv", "venv", ".pytest_cache"}
TEXT_EXTS = {"txt", "md", "py", "js", "ts", "json", "csv", "tsv", "html", "css", "xml", "yml", "yaml",
             "ini", "cfg", "log", "java", "c", "cpp", "h", "sql", "bat", "ps1", "env", "toml"}
MAX_TEXT_SIZE = 5 * 1024 * 1024  # don't read inside files bigger than 5 MB
OWN_FIRST = {"documents", "desktop", "downloads", "pictures", "music", "videos", "onedrive"}
SHOW = 20


def find(root: str = "", name: str = "", exts: list[str] | None = None, after: float | None = None,
         before: float | None = None, min_size: int | None = None, max_size: int | None = None,
         contains: str = "", time_limit: float = 20.0) -> Result:
    start = require_existing(root) if root else Path.home()
    words = name.lower().split()
    exts = {e.lower().lstrip(".") for e in exts or []}
    if contains:
        exts = exts or TEXT_EXTS  # only text files can be searched inside
    needle = contains.lower()

    found, scanned, stopped = [], 0, False
    began = time.monotonic()
    for folder, dirs, files in os.walk(start):
        # Hidden dot-folders (.cache, .vscode, ...) hold app settings, not your files: they used up the whole
        # time limit before the search ever reached Downloads. Your own folders go first for the same reason.
        dirs[:] = sorted((d for d in dirs if d.lower() not in SKIP_DIRS and not d.startswith(".")),
                         key=lambda d: d.lower() not in OWN_FIRST)
        for filename in files:
            scanned += 1
            low = filename.lower()
            if words and not all(w in low for w in words):
                continue
            if exts and low.rsplit(".", 1)[-1] not in exts:
                continue
            path = Path(folder) / filename
            try:
                info = path.stat()
            except OSError:
                continue
            if (after and info.st_mtime < after) or (before and info.st_mtime >= before):
                continue
            if (min_size is not None and info.st_size <= min_size) or (max_size is not None and info.st_size >= max_size):
                continue
            line = ""
            if needle:
                line = first_matching_line(path, info.st_size, needle)
                if line is None:
                    continue
            found.append((path, info.st_size, info.st_mtime, line))
        if time.monotonic() - began > time_limit:
            stopped = True
            break

    if min_size is not None:
        found.sort(key=lambda f: f[1], reverse=True)  # "bigger than" questions want the biggest first
    elif after is not None:
        found.sort(key=lambda f: f[2], reverse=True)  # date questions want the newest first
    elif len(found) > 1:
        found = rank(found, name)  # 8.25: the file you most likely meant first, not disk order

    took = time.monotonic() - began
    header = f"Found {len(found)} file{'s' if len(found) != 1 else ''} in {start} (looked at {scanned:,} files in {took:.1f} s)"
    if stopped:
        header += f". Stopped after {time_limit:.0f} s, so there may be more; try a smaller folder"
    if not found:
        return Result(True, header + ".", {"count": 0, "scanned": scanned, "stopped": stopped})
    lines = [header + ":"]
    for path, size, mtime, line in found[:SHOW]:
        lines.append(f"  - {path}  {human_size(size)}  {datetime.fromtimestamp(mtime):%Y-%m-%d %H:%M}")
        if line:
            lines.append(f"      \"{line}\"")
    if len(found) > SHOW:
        lines.append(f"  ... and {len(found) - SHOW} more")
    return Result(True, "\n".join(lines), {"count": len(found), "scanned": scanned, "stopped": stopped,
                                           "files": [str(f[0]) for f in found]})


def rank(found: list[tuple], query: str) -> list[tuple]:
    """Sort (path, size, mtime, line) results with the 8.25 ranker: learned weights if trained, else hand-set."""
    from maverick.brain.rank import Ranker, features

    now = time.time()
    X = np.array([features(path, query, mtime, now) for path, _, mtime, _ in found])
    return [found[i] for i in Ranker.load().order(X)]


def first_matching_line(path: Path, size: int, needle: str) -> str | None:
    if size > MAX_TEXT_SIZE:
        return None
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            for line in f:
                if needle in line.lower():
                    text = line.strip()
                    return text if len(text) <= 80 else text[:77] + "..."
    except OSError:
        return None
    return None


# --- Grouping similar files (8.23: k-means clustering) ---

KIND_OF = {ext: kind for kind, exts in [("image", IMAGES), ("video", VIDEOS), ("audio", AUDIO), ("document", DOCS),
                                        ("archive", ARCHIVES), ("installer", ["exe", "msi"])] for ext in exts}
# Letters only: dates and IDs make names of the same kind look different. Keeping 5+ digit numbers was tried
# (a shared ID could tie files together) and scored worse, 96.8% -> 93.9%: screenshot and photo dates split them.
NAME_WORD_RE = re.compile(r"[a-zA-Z]{2,}")
GROUP_LIMIT = 400  # files; k-means and the silhouette compare every pair, so keep it quick
SYSTEM_FILES = {"desktop.ini", "thumbs.db"}  # hidden Windows files, not yours to group
# How much "it's a document / an image" counts next to the name words. Measured with python -m maverick.brain.cluster
# (pair agreement): 1.0 -> 92.4%, 0.5 -> 92.4%, 0.25 -> 94.3%, 0 -> 96.8%. The extension alone says enough;
# the kind is still used to NAME a group ("installers").
KIND_WEIGHT = 0.0


def name_words(name: str) -> list[str]:
    """'Invoice_March-2024.pdf' -> ['invoice', 'march', 'ext:pdf', 'kind:document']"""
    stem, _, ext = name.rpartition(".") if "." in name else (name, "", "")
    stem = re.sub(r"([a-z])([A-Z])", r"\1 \2", stem)  # camelCase -> camel Case
    words = [w.lower() for w in NAME_WORD_RE.findall(stem)]
    ext = ext.lower()
    return words + ([f"ext:{ext}"] if ext else []) + [f"kind:{KIND_OF.get(ext, 'other')}"]


def vectors(names: list[str]) -> tuple[np.ndarray, list[str]]:
    """TF-IDF over the name words (like the 8.2 brain): words shared by FEW files say the most about a group."""
    docs = [name_words(n) for n in names]
    vocab = sorted({w for doc in docs for w in doc})
    index = {w: i for i, w in enumerate(vocab)}
    X = np.zeros((len(docs), len(vocab)))
    for row, doc in enumerate(docs):
        for w in doc:
            X[row, index[w]] += 1
    df = (X > 0).sum(axis=0)
    X *= np.log((1 + len(docs)) / (1 + df)) + 1
    # At full weight, "kind:document" glued invoices, lecture notes and a CV into one big group.
    X[:, [index[w] for w in vocab if w.startswith("kind:")]] *= KIND_WEIGHT
    X /= np.maximum(np.linalg.norm(X, axis=1, keepdims=True), 1e-12)
    return X, vocab


def group_title(members: list[str]) -> str:
    """The words most of the group share, e.g. 'invoice (pdf)'; otherwise just the kind, e.g. 'images'."""
    counts = Counter(w for name in members for w in set(name_words(name)))
    shared = [w for w, c in counts.most_common() if c >= max(2, len(members) / 2)]
    words = [w for w in shared if ":" not in w][:2]
    exts = [w[4:] for w in shared if w.startswith("ext:")][:1]
    kinds = [w[5:] for w in shared if w.startswith("kind:") and counts[w] == len(members)][:1]
    if words:
        return " ".join(words) + (f" ({exts[0]})" if exts else "")
    if kinds and kinds[0] != "other":
        return f"{kinds[0]}s"  # 'installers' for .exe + .msi, rather than '.exe files'
    return f".{exts[0]} files" if exts else "mixed"


def group_files(names: list[str], model, X, vocab) -> list[tuple[str, list[str]]]:
    """(title, members) for every group, biggest first."""
    groups = [[n for n, label in zip(names, model.labels) if label == j] for j in range(model.k)]
    return sorted(((group_title(g), g) for g in groups if g), key=lambda tg: -len(tg[1]))


def group(root: str = "") -> Result:
    """Read-only: which files in a folder belong together. Nothing is moved."""
    from maverick.brain.cluster import best_kmeans

    folder = require_existing(root) if root else Path.home() / "Downloads"
    files = sorted((p for p in folder.iterdir() if p.is_file() and p.name.lower() not in SYSTEM_FILES
                    and not p.name.startswith(".")), key=lambda p: p.stat().st_mtime, reverse=True)
    files = files[:GROUP_LIMIT]
    if len(files) < 4:
        return Result(True, f"Only {len(files)} file(s) in {folder}: nothing to group.", {"groups": []})
    names = [p.name for p in files]
    sizes = {p.name: p.stat().st_size for p in files}
    X, vocab = vectors(names)
    found = group_files(names, best_kmeans(X), X, vocab)
    lines = [f"{len(names)} files in {folder}, grouped by what their names have in common:"]
    alone = [members[0] for _, members in found if len(members) == 1]
    for title, members in found:
        if len(members) == 1:
            continue
        examples = ", ".join(members[:3]) + (", ..." if len(members) > 3 else "")
        lines.append(f"  - {title}: {len(members)} files, {human_size(sum(sizes[m] for m in members))}  ({examples})")
    if alone:
        lines.append(f"  - on their own: {', '.join(alone[:5])}{', ...' if len(alone) > 5 else ''}")
    lines.append("Nothing was moved; this only shows which files belong together.")
    return Result(True, "\n".join(lines), {"groups": [[t, m] for t, m in found]})


# Made-up file names whose true groups we know, to check the clustering honestly (python -m maverick.brain.cluster).
SAMPLE_GROUPS = [
    ("invoices", ["invoice_march_2024.pdf", "Invoice-April-2024.pdf", "invoice_0423_amazon.pdf", "invoice_may.pdf",
                  "electricity_invoice_june.pdf"]),
    ("screenshots", ["Screenshot 2026-10-01 101233.png", "Screenshot 2026-10-03 090112.png",
                     "Screenshot 2026-10-07 181501.png", "Screenshot 2026-10-09 223015.png"]),
    ("installers", ["vlc-3.0.20-win64.exe", "ChromeSetup.exe", "python-3.14.0-amd64.exe", "7z2408-x64.msi",
                    "OllamaSetup.exe"]),
    ("phone photos", ["IMG_20260912_141501.jpg", "IMG_20260912_141533.jpg", "IMG_20260915_090001.jpg",
                      "IMG_20260920_183344.jpg"]),
    ("lecture notes", ["lecture_01_intro.pdf", "lecture_02_linear_algebra.pdf", "lecture_03_probability.pdf",
                       "lecture_04_gradient_descent.pdf"]),
    ("songs", ["Imagine Dragons - Believer.mp3", "Coldplay - Yellow.mp3", "Arijit Singh - Kesariya.mp3",
               "AR Rahman - Jai Ho.mp3"]),
    ("archives", ["project_backup.zip", "photos_2025.zip", "fonts.zip", "old_logs.zip"]),
    # Real folders also hold one-offs that belong nowhere; k-means MUST put each somewhere, so these cost points.
    ("one-offs", ["resume_final.docx", "notes.txt", "budget.xlsx"]),
]
