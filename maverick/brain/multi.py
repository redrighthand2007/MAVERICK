"""Several actions in one sentence (Stage 8.16).

"copy notes.txt to D:\\backup and zip it" is TWO requests. But "cut and paste notes.txt" is ONE,
and so is "cpu name and cores". A rule like "split at every and" breaks those, so the splitter LEARNS it:

  1. candidates: every gap before "and" / "then" / "also" / "plus", or right after a comma
  2. each candidate becomes a small example with features: the connector, the words around it,
     how many words are on each side, whether each side has a path ...
  3. STACKING: the intent brain also reads the words on each side and says what action that piece is
     and how sure it is. "end them" is clearly process.end; "all its windows" is nothing on its own.
  4. a logistic regression (the 8.2 brain, reused) answers: cut here, or keep together?

Cutting is a yes/no question per gap, so this is binary classification, the simplest kind there is.
The pieces then each go through the normal brain + agents, one after another (see orchestrator.py).

Run:  python -m maverick.brain.multi     (cross-validates, then trains and saves)
"""
import random
from pathlib import Path

from maverick.brain.dataset import DATA_DIR, INTENTS_PATH, load_examples
from maverick.brain.logistic_regression import LogisticRegression
from maverick.brain.slots import clean, shape, tokens_of
from maverick.brain.text import tokenize

MULTI_PATH = DATA_DIR / "multi.tsv"
SPLITTER_PATH = Path(__file__).parent / "models" / "splitter.json"
CONNECTORS = {"and", "then", "also", "plus"}
CUT, KEEP = "cut", "keep"


def word(token: str) -> str:
    return clean(token).lower() if shape(token) == "word" else f"<{shape(token)}>"


def candidates(tokens: list[str]) -> list[int]:
    """Gaps where a sentence MIGHT split: i means "between tokens[i-1] and tokens[i]"."""
    return [i for i in range(1, len(tokens))
            if clean(tokens[i]).lower() in CONNECTORS or tokens[i - 1].endswith((",", ";"))]


def bucket(n: int) -> str:
    return str(n) if n < 3 else "3+"


def confidence(level: float) -> str:
    return "high" if level >= 0.6 else "mid" if level >= 0.3 else "low"


def brain_features(brain, tokens: list[str], i: int) -> list[str]:
    """What the intent brain thinks of the piece before the gap and the piece after it."""
    gaps = candidates(tokens)
    start = max([g for g in gaps if g < i], default=0)
    end = min([g for g in gaps if g > i], default=len(tokens))
    (left, left_conf), (right, right_conf) = (brain.predict(tokenize(tidy(piece)))
                                              for piece in (tokens[start:i], tokens[i:end]))
    return [f"left={left}|{confidence(left_conf)}", f"right={right}|{confidence(right_conf)}",
            f"right_agent={right.split('.')[0]}", f"right_sure={confidence(right_conf)}",
            f"left_sure={confidence(left_conf)}", f"same_agent={left.split('.')[0] == right.split('.')[0]}",
            f"same_label={left == right}"]


def features(tokens: list[str], i: int, brain=None) -> list[str]:
    words = [word(t) for t in tokens]
    padded = ["<s>", "<s>", *words, "</s>", "</s>", "</s>"]
    j = i + 2  # tokens[i] inside `padded`
    comma = tokens[i - 1].endswith((",", ";"))
    connector = words[i] if words[i] in CONNECTORS else ","
    return [
        f"conn={connector}", f"comma={comma}", f"prev={padded[j - 1]}", f"prev2={padded[j - 2]}",
        f"next={padded[j + 1]}", f"next2={padded[j + 2]}", f"here={padded[j]}",
        f"conn+next={connector}|{padded[j + 1]}", f"prev+conn={padded[j - 1]}|{connector}",
        f"left={bucket(i)}", f"right={bucket(len(tokens) - i)}",
        f"left_path={any(w.startswith('<') for w in words[:i])}",
        f"right_path={any(w.startswith('<') for w in words[i:])}",
        f"right_it={'it' in words[i:] or 'them' in words[i:]}",
        *(brain_features(brain, tokens, i) if brain else []),
    ]


def parse_marked(line: str) -> tuple[list[str], set[int]]:
    """'copy a.txt to D:\\x | and zip it' -> tokens and the gaps marked with |."""
    tokens, cuts = [], set()
    for token in tokens_of(line):
        if token == "|":
            cuts.add(len(tokens))
        else:
            tokens.append(token)
    return tokens, cuts




def tidy(part: list[str]) -> str:
    """Drop the connector words at the start and a comma at the end of one piece."""
    while len(part) > 1 and clean(part[0]).lower() in CONNECTORS | {"after", "that"}:
        part = part[1:]
    if part:
        part = [*part[:-1], part[-1].rstrip(",;")]
    return " ".join(part)


def load_marked() -> list[tuple[list[str], set[int]]]:
    return [parse_marked(line) for _, line in load_examples(MULTI_PATH)]


def train_brain(examples) -> LogisticRegression:
    """A plain intent brain (no inbox logging) to read each side of a gap."""
    return LogisticRegression().fit([(label, tokenize(sentence)) for label, sentence in examples])


class Splitter:
    def __init__(self, brain, model: LogisticRegression | None = None):
        self.brain = brain  # the intent model: anything with predict(tokens) -> (label, confidence)
        self.model = model or LogisticRegression()

    def fit(self, sentences: list[tuple[list[str], set[int]]]) -> "Splitter":
        """sentences: (tokens, gaps to cut at). One training row per candidate gap."""
        rows = [(CUT if i in cuts else KEEP, features(tokens, i, self.brain))
                for tokens, cuts in sentences for i in candidates(tokens)]
        self.model.fit(rows)
        return self

    def cuts(self, tokens: list[str]) -> set[int]:
        return {i for i in candidates(tokens) if self.model.predict(features(tokens, i, self.brain))[0] == CUT}

    def split(self, sentence: str) -> list[str]:
        """'copy a.txt to D:\\x and zip it' -> ['copy a.txt to D:\\x', 'zip it']"""
        tokens = tokens_of(sentence)
        edges = [0, *sorted(self.cuts(tokens)), len(tokens)]
        parts = [tidy(tokens[a:b]) for a, b in zip(edges, edges[1:])]
        return [p for p in parts if p]

    def save(self, path: Path = SPLITTER_PATH) -> None:
        self.model.save(path)

    @classmethod
    def load(cls, brain, path: Path = SPLITTER_PATH) -> "Splitter | None":
        """None until trained (or without a brain): then every request is one action, like before 8.16."""
        if brain is None or not path.exists():
            return None
        return cls(brain, LogisticRegression.load(path))


def score(splitter: Splitter, sentences) -> tuple[float, float]:
    """(multi-action sentences cut exactly right, one-action sentences WITH an and/then/comma left whole)."""
    multi = [s for s in sentences if s[1]]
    single = [s for s in sentences if not s[1] and candidates(s[0])]
    right_multi = sum(splitter.cuts(tokens) == cuts for tokens, cuts in multi)
    right_single = sum(not splitter.cuts(tokens) for tokens, _ in single)
    return right_multi / max(len(multi), 1), right_single / max(len(single), 1)


def naive_cuts(tokens: list[str]) -> set[int]:
    """The rule we'd write without AI: cut at every candidate (merging "and then" into one cut)."""
    found = candidates(tokens)
    return {i for i in found if i - 1 not in found}


def cross_validate(k: int = 5, use_brain: bool = True) -> tuple[float, float]:
    """Each fold trains its OWN intent brain without the fold's test sentences, so nothing is seen twice."""
    marked, intents = load_marked(), load_examples(INTENTS_PATH)
    rng = random.Random(42)
    rng.shuffle(marked)
    rng.shuffle(intents)
    totals = [0.0, 0.0]
    for f in range(k):
        train_intents = [e for n, e in enumerate(intents) if n % k != f]
        brain = train_brain(train_intents) if use_brain else None
        train = [m for n, m in enumerate(marked) if n % k != f] + [(tokens_of(s), set()) for _, s in train_intents]
        test = marked[f::k] + [(tokens_of(s), set()) for _, s in intents[f::k]]
        for n, value in enumerate(score(Splitter(brain).fit(train), test)):
            totals[n] += value / k
    return totals[0], totals[1]


def main() -> None:
    from maverick.brain import Brain

    marked, intents = load_marked(), load_examples(INTENTS_PATH)
    single = [s for _, s in intents if candidates(tokens_of(s))]
    several = [(t, c) for t, c in marked if c]
    naive = sum(naive_cuts(t) == c for t, c in several) / len(several)
    words_only, stacked = cross_validate(use_brain=False), cross_validate()
    print("5-fold cross-validation (sentences never seen in training):")
    print(f"  cut at every and/then/comma: {naive:.1%} of multi-action sentences right, "
          f"but breaks all {len(single)} one-action sentences that have one")
    print(f"  learned, words only:         {words_only[0]:.1%} multi-action cut right, "
          f"{words_only[1]:.1%} one-action left whole")
    print(f"  learned + brain (stacking):  {stacked[0]:.1%} multi-action cut right, "
          f"{stacked[1]:.1%} one-action left whole")

    brain = Brain.load(log_path=None)
    if brain is None:
        raise SystemExit("Train the intent brain first: python -m maverick.brain.train")
    Splitter(brain.model).fit(marked + [(tokens_of(s), set()) for _, s in intents]).save()
    print(f"Trained on {len(marked)} multi-action + {len(intents)} one-action sentences. Saved to {SPLITTER_PATH}")


if __name__ == "__main__":
    main()
