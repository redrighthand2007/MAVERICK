"""Ranking search results (Stage 8.25): put the file you meant first.

Classification picks a label, regression predicts a number; RANKING puts things in ORDER.
"find report" can match 40 files; the useful answer is the 3 you most likely meant, on top.

Each found file becomes a few numbers (FEATURES): how well its name matches, how recently it changed,
whether it lives in your own folders or in a cache, how deep it is, and whether it's a file people open.
score = w1 * feature1 + w2 * feature2 + ...  and the results are sorted by score.

The weights are LEARNED with pairwise logistic regression ("learning to rank", like RankNet):
for every search we know which file was meant, and every other file gives one training pair
  (meant, other)  ->  we want  score(meant) > score(other)
P(meant above other) = sigmoid(score(meant) - score(other)); gradient descent pushes that towards 1.
Only DIFFERENCES between files matter, which is exactly what ordering needs.

Graded with MRR (mean reciprocal rank): the file you meant at place 1 scores 1, at place 2 scores 1/2,
at place 5 scores 1/5. Averaged over all searches; 1.0 = always on top.

Honest limit: no real searches with "the file I meant" exist yet, so it learns from MADE-UP searches
built on assumptions (people mostly want their own, recent, well-named files; caches rarely).
Logging which result you actually open would be the real data, like inbox.tsv is for the brain.

Run:  python -m maverick.brain.rank     (trains on made-up searches, tests on others, saves models/rank.json)
"""
import json
import math
import random
import re
from pathlib import Path

import numpy as np

RANK_PATH = Path(__file__).parent / "models" / "rank.json"
FEATURES = ["exact name", "starts with query", "whole words", "name coverage", "recent", "own folder",
            "junk folder", "depth", "user file type"]
JUNK_PARTS = {"cache", "caches", "temp", "tmp", "node_modules", "site-packages", ".git", "__pycache__", "appdata",
              "build", "dist", "logs", "programdata", ".venv", "venv", "packages", "windows", "program files"}
OWN_FOLDERS = {"documents", "desktop", "downloads", "pictures", "music", "videos", "onedrive"}
USER_TYPES = {"pdf", "doc", "docx", "txt", "md", "xls", "xlsx", "csv", "ppt", "pptx", "jpg", "jpeg", "png", "mp4",
              "mkv", "mp3", "zip", "rar", "7z", "exe", "msi", "py", "odt"}
# Before learning, a person's guess. Also used when no trained weights are saved.
HAND_WEIGHTS = [3.0, 1.0, 1.5, 1.0, 1.0, 1.0, -2.0, -0.5, 0.5]
WORD_RE = re.compile(r"[a-z0-9]+")


def features(path: Path, query: str, mtime: float, now: float) -> list[float]:
    """One found file -> numbers in FEATURES order (each roughly between 0 and 1)."""
    words = WORD_RE.findall(query.lower())
    stem = path.stem.lower()
    name_words = WORD_RE.findall(stem)
    parts = [p.lower() for p in path.parts[:-1]]
    days = max(0.0, (now - mtime) / 86400)
    joined = " ".join(words)
    return [
        float(" ".join(name_words) == joined),                        # report.docx for "report"
        float(bool(words) and stem.startswith(words[0])),             # report_final.docx
        float(all(w in name_words for w in words)),                   # q3_report.pdf, not reporter.py
        min(1.0, len(joined.replace(" ", "")) / max(len(stem), 1)),   # how much of the name the query covers
        1 - min(1.0, math.log1p(days) / math.log1p(365 * 3)),          # 1 = changed today, 0 = 3+ years ago
        float(any(p in OWN_FOLDERS for p in parts)),
        float(any(p in JUNK_PARTS or p.startswith(".") for p in parts)),
        min(1.0, len(parts) / 12),
        float(path.suffix.lower().lstrip(".") in USER_TYPES),
    ]


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


class Ranker:
    def __init__(self, weights=None):
        self.weights = np.array(weights if weights is not None else HAND_WEIGHTS, dtype=float)

    def scores(self, X) -> np.ndarray:
        return np.asarray(X, dtype=float) @ self.weights

    def order(self, X) -> list[int]:
        """Indexes of the files, best first."""
        return list(np.argsort(-self.scores(X), kind="stable"))

    def fit(self, searches, epochs: int = 300, lr: float = 0.5, l2: float = 1e-3) -> "Ranker":
        """searches: list of (X, meant) = one row of features per found file, and the index of the one meant."""
        diffs = np.array([X[meant] - X[i] for X, meant in ((np.asarray(X, float), m) for X, m in searches)
                          for i in range(len(X)) if i != meant])
        w = np.zeros(diffs.shape[1])
        for _ in range(epochs):
            p = sigmoid(diffs @ w)                   # P(meant file ranked above the other one)
            w += lr * (diffs.T @ (1 - p) / len(diffs) - l2 * w)
        self.weights = w
        return self

    def save(self, path: Path = RANK_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"features": FEATURES, "weights": self.weights.tolist()}, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = RANK_PATH) -> "Ranker":
        """The trained weights if saved (and made for these features), else the hand-set ones."""
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))
            if saved["features"] == FEATURES:
                return cls(saved["weights"])
        except (OSError, ValueError, KeyError):
            pass
        return cls()


def mrr(order_of, searches) -> float:
    """Mean reciprocal rank: 1 / (place of the meant file), averaged."""
    return float(np.mean([1 / (list(order_of(X)).index(meant) + 1) for X, meant in searches]))


# --- Made-up searches (the honest limit above): a meant file and look-alikes that are worse for a reason ---

QUERIES = ["report", "invoice", "resume", "notes", "budget", "thesis", "photo", "setup", "presentation", "todo",
           "lecture", "contract", "ticket", "syllabus", "receipt"]
HOME = Path("C:/Users/me")


def made_up_search(rng: random.Random, now: float) -> tuple[list[Path], list[float], int]:
    q = rng.choice(QUERIES)
    own = HOME / rng.choice(["Documents", "Desktop", "Downloads", "Documents/college", "Pictures"])
    ext = rng.choice(["pdf", "docx", "xlsx", "pptx", "txt", "jpg"])
    meant_name = rng.choice([f"{q}.{ext}", f"{q}_final.{ext}", f"{q} 2026.{ext}", f"my {q}.{ext}"])
    files = [(own / meant_name, now - rng.uniform(0, 60) * 86400)]
    makers = [
        lambda: (HOME / "AppData/Local/app/cache" / f"{q}_{rng.randint(1, 999)}.tmp", now - rng.uniform(0, 3) * 86400),
        lambda: (HOME / f"projects/site/node_modules/{q}er/lib" / f"{q}er.js", now - rng.uniform(0, 400) * 86400),
        lambda: (own / f"old {q} {rng.randint(2015, 2021)}.{ext}", now - rng.uniform(700, 2500) * 86400),
        lambda: (Path("D:/backup/2019/stuff") / f"{q} (1).{ext}", now - rng.uniform(900, 2000) * 86400),
        lambda: (own / f"{q}s_and_other_things_draft_v{rng.randint(2, 9)}.{ext}", now - rng.uniform(30, 300) * 86400),
        lambda: (HOME / f".config/tool/{q}.json", now - rng.uniform(0, 30) * 86400),
        lambda: (Path("C:/Program Files/App/data") / f"{q}.dll", now - rng.uniform(100, 1000) * 86400),
        lambda: (HOME / "Downloads" / f"un{q}able_list.{ext}", now - rng.uniform(10, 200) * 86400),
        # True look-alikes: as good on every signal, so even a perfect ranker guesses between them.
        lambda: (HOME / rng.choice(["Desktop", "Downloads", "OneDrive"]) / f"{q} (1).{ext}", now - rng.uniform(0, 60) * 86400),
        lambda: (own / f"{q} notes.{rng.choice(['txt', 'docx'])}", now - rng.uniform(0, 90) * 86400),
    ]
    for _ in range(rng.randint(4, 12)):
        files.append(rng.choice(makers)())
    rng.shuffle(files)  # the walk order on disk has nothing to do with what you meant
    meant = next(i for i, (p, _) in enumerate(files) if p.name == meant_name and p.parent == own)
    if rng.random() < 0.2:
        meant = rng.randrange(len(files))  # sometimes you really did want the old backup or the odd one
    return [p for p, _ in files], [t for _, t in files], meant


def made_up_searches(n: int, seed: int, now: float = 1_800_000_000.0):
    rng = random.Random(seed)
    out = []
    for _ in range(n):
        paths, mtimes, meant = made_up_search(rng, now)
        query = next(w for p in paths for w in WORD_RE.findall(p.stem.lower()) if w in QUERIES)
        out.append((np.array([features(p, query, t, now) for p, t in zip(paths, mtimes)]), meant))
    return out


def main() -> None:
    train, test = made_up_searches(300, seed=1), made_up_searches(200, seed=2)
    learned = Ranker().fit(train)
    col = FEATURES.index
    print(f"Made-up searches: {len(train)} to learn from, {len(test)} others to test on (4-12 look-alikes each).")
    print("MRR on the test searches (1.0 = the file you meant is always first):")
    for name, order in [
        ("disk order (today's search)", lambda X: list(range(len(X)))),
        ("newest first", lambda X: list(np.argsort(-X[:, col("recent")], kind="stable"))),
        ("shortest name / best coverage", lambda X: list(np.argsort(-X[:, col("name coverage")], kind="stable"))),
        ("hand-set weights", Ranker().order),
        ("learned weights", learned.order),
    ]:
        print(f"  {name:32} {mrr(order, test):.3f}")
    print("\nLearned weights (what each signal is worth):")
    for f, w in sorted(zip(FEATURES, learned.weights), key=lambda fw: -abs(fw[1])):
        print(f"  {f:20} {w:+.2f}")
    learned.save()
    print(f"Saved to {RANK_PATH}")


if __name__ == "__main__":
    main()
