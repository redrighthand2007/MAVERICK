"""Teach the brain from your real requests (Stages 8.13 online learning + 8.14 active learning).

Run:  python -m maverick.brain.review

Every request you type is logged in inbox.tsv with the brain's guess and confidence. This tool shows
them LEAST confident first (active learning: the brain asks about what it's most unsure of), you confirm
or correct the label, and the answers go into learned.tsv. Training then uses intents.tsv + learned.tsv.

inbox.tsv itself is never changed. Both files stay on your PC only (gitignored: they hold your real paths).
"""
from pathlib import Path

from maverick.brain import INBOX_PATH
from maverick.brain.dataset import DATA_DIR, INTENTS_PATH, load_examples

LEARNED_PATH = DATA_DIR / "learned.tsv"
SKIP = "s"


def labels() -> list[str]:
    return sorted({label for label, _ in load_examples(INTENTS_PATH)})


def read_inbox(path: Path = INBOX_PATH) -> list[tuple[str, float, str]]:
    """(guess, confidence, sentence) for each logged request, oldest duplicates dropped."""
    if not path.exists():
        return []
    seen, rows = set(), []
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) != 3 or parts[2].strip().lower() in seen:
            continue
        seen.add(parts[2].strip().lower())
        try:
            rows.append((parts[0], float(parts[1]), parts[2].strip()))
        except ValueError:
            continue
    return rows


def already_learned(path: Path = LEARNED_PATH) -> set[str]:
    if not path.exists():
        return set()
    return {line.split("\t", 1)[1].strip().lower() for line in path.read_text(encoding="utf-8").splitlines()
            if "\t" in line and not line.startswith("#")}


def to_review(inbox: Path = INBOX_PATH, learned: Path = LEARNED_PATH) -> list[tuple[str, float, str]]:
    """Not yet reviewed, least confident first."""
    done = already_learned(learned)
    return sorted((r for r in read_inbox(inbox) if r[2].lower() not in done), key=lambda r: r[1])


def review(ask=input, inbox: Path = INBOX_PATH, learned: Path = LEARNED_PATH, known: list[str] | None = None) -> int:
    """Ask about each pending request; returns how many were saved. `ask` is swapped out in tests."""
    known = known or labels()
    pending = to_review(inbox, learned)
    if not pending:
        print("Nothing new in inbox.tsv to review.")
        return 0
    print(f"{len(pending)} requests to review, least confident first.")
    print("Enter = the guess is right, a label (e.g. files.copy) = correct it, s = skip, q = stop.\n")
    saved = 0
    for guess, confidence, sentence in pending:
        answer = ask(f"{sentence!r}\n  brain said {guess} ({confidence:.0%}) > ").strip()
        if answer == "q":
            break
        if answer == SKIP:
            continue
        label = answer or guess
        while label not in known:
            matches = [k for k in known if label in k]
            hint = f" Did you mean: {', '.join(matches[:6])}?" if matches else ""
            label = ask(f"  '{label}' is not a label.{hint} Type a label (or s to skip) > ").strip()
            if label == SKIP:
                break
        if label == SKIP:
            continue
        with open(learned, "a", encoding="utf-8") as f:
            f.write(f"{label}\t{sentence}\n")
        saved += 1
    print(f"\nSaved {saved} to {learned.name}. Retrain to use them: python -m maverick.brain.train")
    return saved


if __name__ == "__main__":
    review(known=labels())
