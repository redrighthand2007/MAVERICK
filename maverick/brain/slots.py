"""Slot filling: the brain finds the ARGUMENTS in a sentence, not just the operation (Stage 8.15).

The intent brain answers "what do you want?" (files.copy). Slot filling answers "with what?":

    copy   my    thesis     to  the  usb  drive  F:\
    O      O     B-source   O   O    O    O      B-destination

Every word gets a tag. B- marks the first word of an argument, I- a word that continues it
("B-source I-source" for a two-word name), O means "not an argument". This is called BIO tagging,
and turning a sentence into tags is SEQUENCE LABELLING: one decision per word instead of one per sentence.

How it decides each word's tag:
  1. features: the word itself, its neighbours, its shape (drive letter? file extension?) and the operation
  2. softmax regression (same maths as logistic_regression.py) scores every tag for that word
  3. Viterbi: picks the best tag SEQUENCE, never allowing a broken one like O then I-source

Run:  python -m maverick.brain.slots     (cross-validates against the old regex, then trains and saves)
"""
import json
import re
from pathlib import Path

import numpy as np

from maverick.brain.dataset import DATA_DIR, folds, load_examples
from maverick.brain.logistic_regression import softmax
from maverick.brain.text import looks_like_path

SLOTS_DATA_PATH = DATA_DIR / "slots.tsv"
SLOTS_MODEL_PATH = Path(__file__).parent / "models" / "slots.json"
OUTSIDE = "O"

# A token is "a quoted path with spaces" or a run of non-space characters (same as the file agent).
TOKEN_RE = re.compile(r'"[^"]*"|\S+')
# In slots.tsv an argument is written as [slot words].
TAGGED_RE = re.compile(r'\[(\w+) ([^\]]+)\]|"[^"]*"|\S+')
TO_WORDS = {"to", "into", "in", "on", "as", "called"}


def tokens_of(sentence: str) -> list[str]:
    return TOKEN_RE.findall(sentence)


def clean(token: str) -> str:
    """The value a token stands for: quotes and trailing punctuation removed."""
    return token[1:-1] if token.startswith('"') and len(token) > 1 else token.rstrip("?!.,;")


def parse_tagged(line: str) -> tuple[list[str], list[str]]:
    """'copy [source a.txt] to [destination D:\\x]' -> tokens and their BIO tags."""
    tokens, tags = [], []
    for match in TAGGED_RE.finditer(line):
        slot, inner = match.group(1), match.group(2)
        if slot is None:
            tokens.append(match.group(0))
            tags.append(OUTSIDE)
            continue
        for i, token in enumerate(tokens_of(inner)):
            tokens.append(token)
            tags.append(("B-" if i == 0 else "I-") + slot)
    return tokens, tags


def load_tagged(path: Path = SLOTS_DATA_PATH) -> list[tuple[str, list[str], list[str]]]:
    return [(label, *parse_tagged(line)) for label, line in load_examples(path)]


def shape(token: str) -> str:
    if token.startswith('"'):
        return "quoted"
    word = clean(token)
    if re.match(r"^[a-zA-Z]:", word):
        return "drive"
    if "\\" in word or "/" in word:
        return "slashed"
    if re.search(r"\.[A-Za-z0-9]{1,6}$", word):
        return "file"
    if word.isdigit():
        return "number"
    return "word"


def features(label: str, tokens: list[str], i: int) -> list[str]:
    """Everything the tagger may look at to decide word i's tag. Each is just a string, like 'w=to'."""
    words = [clean(t).lower() if shape(t) == "word" else f"<{shape(t)}>" for t in tokens]
    padded = ["<s>", "<s>", *words, "</s>", "</s>"]
    j = i + 2  # position of word i inside `padded`
    op = label.split(".")[-1]
    seen_to = any(w in TO_WORDS for w in words[:i])
    return [
        "bias", f"op={op}", f"w={words[i]}", f"shape={shape(tokens[i])}",
        f"path={looks_like_path(clean(tokens[i]))}",
        f"prev={padded[j - 1]}", f"prev2={padded[j - 2]}", f"next={padded[j + 1]}", f"next2={padded[j + 2]}",
        f"prev+w={padded[j - 1]}|{words[i]}", f"op+prev={op}|{padded[j - 1]}",
        f"seen_to={seen_to}", f"op+seen_to={op}|{seen_to}",
    ]


def allowed_after(previous: str, tag: str) -> bool:
    """I-x may only continue an x: 'O I-source' is a broken sequence."""
    return not tag.startswith("I-") or previous in (f"B-{tag[2:]}", tag)


class SlotTagger:
    def __init__(self, epochs: int = 300, learning_rate: float = 2.0, l2: float = 1e-4):
        self.epochs, self.learning_rate, self.l2 = epochs, learning_rate, l2
        self.index: dict[str, int] = {}
        self.tags: list[str] = []
        self.weights = np.zeros((0, 0))

    def _matrix(self, rows: list[list[str]]) -> np.ndarray:
        x = np.zeros((len(rows), len(self.index)))
        for r, feats in enumerate(rows):
            for f in feats:
                if f in self.index:
                    x[r, self.index[f]] = 1
        return x

    def fit(self, examples: list[tuple[str, list[str], list[str]]]) -> "SlotTagger":
        # One training row per WORD (not per sentence): its features and its tag.
        rows, answers = [], []
        for label, tokens, tags in examples:
            for i, tag in enumerate(tags):
                rows.append(features(label, tokens, i))
                answers.append(tag)
        self.index = {f: n for n, f in enumerate(sorted({f for feats in rows for f in feats}))}
        self.tags = sorted(set(answers))
        x = self._matrix(rows)
        y = np.zeros((len(rows), len(self.tags)))
        y[np.arange(len(rows)), [self.tags.index(t) for t in answers]] = 1

        self.weights = np.zeros((len(self.index), len(self.tags)))
        velocity = np.zeros_like(self.weights)
        for _ in range(self.epochs):
            error = (softmax(x @ self.weights) - y) / len(rows)
            velocity = 0.9 * velocity - self.learning_rate * (x.T @ error + self.l2 * self.weights)
            self.weights += velocity
        return self

    def tag(self, label: str, tokens: list[str], slots: tuple[str, ...] | None = None) -> list[str]:
        """Best tag sequence (Viterbi). `slots` limits which arguments may appear, e.g. rename has no destination."""
        if not tokens:
            return []
        x = self._matrix([features(label, tokens, i) for i in range(len(tokens))])
        log_p = np.log(softmax(x @ self.weights) + 1e-12)
        usable = [t == OUTSIDE or slots is None or t[2:] in slots for t in self.tags]
        log_p[:, [n for n, ok in enumerate(usable) if not ok]] = -np.inf

        # best[i][t] = score of the best sequence for words 0..i that ends in tag t; back[] remembers the path.
        best = [{t: log_p[0, n] if allowed_after(OUTSIDE, t) else -np.inf for n, t in enumerate(self.tags)}]
        back = []
        for i in range(1, len(tokens)):
            scores, pointers = {}, {}
            for n, t in enumerate(self.tags):
                prev = max((p for p in self.tags if allowed_after(p, t)), key=lambda p: best[-1][p])
                scores[t], pointers[t] = best[-1][prev] + log_p[i, n], prev
            best.append(scores)
            back.append(pointers)
        tags = [max(best[-1], key=best[-1].get)]
        for pointers in reversed(back):
            tags.append(pointers[tags[-1]])
        return tags[::-1]

    def fill(self, label: str, sentence: str, slots: tuple[str, ...] | None = None) -> dict[str, str]:
        """'files.copy', 'copy my thesis to F:\\' -> {'source': 'thesis', 'destination': 'F:\\'}"""
        tokens = tokens_of(sentence)
        return spans(tokens, self.tag(label, tokens, slots))

    def save(self, path: Path = SLOTS_MODEL_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"tags": self.tags, "features": sorted(self.index, key=self.index.get),
                "weights": np.round(self.weights, 6).tolist()}
        path.write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = SLOTS_MODEL_PATH) -> "SlotTagger | None":
        """None until trained, so the agents keep using their regex rules."""
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        tagger = cls()
        tagger.tags = data["tags"]
        tagger.index = {f: n for n, f in enumerate(data["features"])}
        tagger.weights = np.array(data["weights"])
        return tagger


def spans(tokens: list[str], tags: list[str]) -> dict[str, str]:
    """Tags back to values. The first span of each slot wins."""
    found: dict[str, list[str]] = {}
    current = None
    for token, tag in zip(tokens, tags):
        if tag.startswith("B-"):
            current = tag[2:] if tag[2:] not in found else None
            if current:
                found[current] = [clean(token)]
        elif tag.startswith("I-") and current == tag[2:]:
            found[current].append(clean(token))
        else:
            current = None
    return {slot: " ".join(words) for slot, words in found.items()}


def score(predict, examples) -> tuple[float, float]:
    """(sentences with EVERY argument right, single arguments right). `predict(label, tokens) -> dict`."""
    whole = right = total = 0
    for label, tokens, tags in examples:
        truth, guess = spans(tokens, tags), predict(label, tokens)
        whole += truth == guess
        keys = set(truth) | set(guess)
        right += sum(truth.get(k) == guess.get(k) for k in keys)
        total += len(keys)
    return whole / len(examples), right / max(total, 1)


def main() -> None:
    from maverick.agents.files.agent import FileAgent, SLOTS  # here, not at the top: the agent imports this file

    lines = load_examples(SLOTS_DATA_PATH)
    regex = FileAgent()

    def by_regex(label, tokens):
        intent = regex.extract(label.split(".")[1], " ".join(tokens))
        return {k: v for k, v in intent.args.items() if v}

    cv_tagger = cv_regex = (0.0, 0.0)
    for train_lines, test_lines in folds(lines):
        tagger = SlotTagger().fit([(label, *parse_tagged(s)) for label, s in train_lines])
        test = [(label, *parse_tagged(s)) for label, s in test_lines]
        a = score(lambda label, tokens: spans(tokens, tagger.tag(label, tokens, SLOTS[label.split(".")[1]])), test)
        b = score(by_regex, test)
        cv_tagger = tuple(c + v / 5 for c, v in zip(cv_tagger, a))
        cv_regex = tuple(c + v / 5 for c, v in zip(cv_regex, b))
    print("5-fold cross-validation on slots.tsv (sentences never seen in training):")
    print(f"  old regex rules: {cv_regex[0]:.1%} of sentences fully right, {cv_regex[1]:.1%} of arguments right")
    print(f"  slot tagger:     {cv_tagger[0]:.1%} of sentences fully right, {cv_tagger[1]:.1%} of arguments right")

    tagger = SlotTagger().fit(load_tagged())
    tagger.save()
    print(f"Trained on all {len(lines)} sentences. Saved to {SLOTS_MODEL_PATH}")


if __name__ == "__main__":
    main()
