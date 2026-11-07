"""Word embeddings (Stage 8.10): GloVe word vectors, so "duplicate" can count as "copy" without an example.

Every model so far treats words as unrelated IDs: "copy" and "duplicate" are as different as "copy" and
"banana". GloVe (Stanford, 2014) learned 50 numbers per word from 6 billion words of Wikipedia + news,
by how often words appear near each other. Words used the same way end up close together:
  cosine("copy", "duplicate") is high,  cosine("copy", "banana") is low.
We don't train anything here: it's a pretrained, offline lookup table (models/glove.6B.50d.txt, 171 MB).

Two ways to use it, both measured by 5-fold cross-validation against the plain brain:
  1. unknown-word swap: a word the brain never saw in training is replaced by the most similar word it
     DID see (if similar enough). "duplicate notes.txt" -> "copy notes.txt"
  2. meaning features: the sentence's average word vector (50 numbers) added to its TF-IDF numbers

Setup: download glove.6B.zip (Stanford NLP, also on huggingface.co/stanfordnlp/glove) and keep glove.6B.50d.txt
Run:   python -m maverick.brain.embeddings
"""
from pathlib import Path

import numpy as np

from maverick.brain.logistic_regression import LogisticRegression

GLOVE_PATH = Path(__file__).parent / "models" / "glove.6B.50d.txt"
MIN_SIMILARITY = 0.75  # below this a "nearest known word" is more likely a different meaning


def load_glove(path: Path = GLOVE_PATH, keep: set[str] | None = None) -> dict[str, np.ndarray]:
    """word -> unit-length vector. `keep` limits it to the words you need (400,000 lines otherwise)."""
    vectors = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            word, _, rest = line.partition(" ")
            if keep is None or word in keep:
                v = np.array(rest.split(), dtype=float)
                vectors[word] = v / (np.linalg.norm(v) or 1)
    return vectors


def similar(glove, word: str, among: list[str], n: int = 3) -> list[tuple[str, float]]:
    if word not in glove:
        return []
    known = [w for w in among if w in glove and w != word]
    sims = np.array([glove[w] for w in known]) @ glove[word]
    return [(known[i], float(sims[i])) for i in np.argsort(-sims)[:n]]


class SynonymSwap:
    """Wraps a trained brain model: unseen words are swapped for their nearest seen word before predicting."""

    def __init__(self, model, glove, known: set[str], min_similarity: float = MIN_SIMILARITY):
        self.model, self.glove, self.min_similarity = model, glove, min_similarity
        self.threshold = model.threshold
        self.known_set = set(known)
        self.known = sorted(w for w in known if w in glove)
        self.matrix = np.array([glove[w] for w in self.known])
        self.cache: dict[str, str] = {}

    def swap(self, word: str) -> str:
        if word in self.cache:
            return self.cache[word]
        best = word
        if word in self.glove:
            sims = self.matrix @ self.glove[word]
            i = int(np.argmax(sims))
            if sims[i] >= self.min_similarity:
                best = self.known[i]
        self.cache[word] = best
        return best

    def translate(self, tokens: list[str]) -> list[str]:
        return [t if t in self.known_set else self.swap(t) for t in tokens]

    def predict(self, tokens):
        return self.model.predict(self.translate(tokens))


class MeaningLR(LogisticRegression):
    """Logistic regression on TF-IDF numbers PLUS the sentence's average GloVe vector (50 more numbers)."""

    def __init__(self, glove, **kw):
        super().__init__(**kw)
        self.glove = glove

    def features(self, docs):
        means = np.array([np.mean([self.glove[w] for w in d if w in self.glove] or [np.zeros(50)], axis=0)
                          for d in docs])
        return np.hstack([super().features(docs), means])


def main() -> None:
    from maverick.brain.dataset import HARD_CASES_PATH, INTENTS_PATH, folds, load_examples
    from maverick.brain.evaluate import accuracy, as_maverick_runs, grade
    from maverick.brain.text import tokenize

    examples, hard = load_examples(INTENTS_PATH), load_examples(HARD_CASES_PATH)
    words = {w for _, s in examples + hard for w in tokenize(s)} | {"duplicate", "copy", "terminate", "kill",
                                                                   "relocate", "move", "shrink", "compress"}
    glove = load_glove(keep=words)
    print(f"GloVe vectors for {len(glove)} of the {len(words)} words MAVERICK's sentences use.")
    for w in ["duplicate", "terminate", "relocate", "shrink"]:
        print(f"  nearest to {w!r}: " + ", ".join(f"{n} {s:.2f}" for n, s in similar(glove, w, sorted(glove))))

    def variants(train_tok):
        plain = LogisticRegression().fit(train_tok)
        seen = {w for _, tokens in train_tok for w in tokens}
        return {"plain brain": plain, "+ unknown-word swap": SynonymSwap(plain, glove, seen),
                "+ meaning features": MeaningLR(glove).fit(train_tok)}

    results: dict[str, tuple[list, list]] = {}
    for train_part, test_part in folds(examples):
        for name, m in variants([(label, tokenize(s)) for label, s in train_part]).items():
            brain, maverick = results.setdefault(name, ([], []))
            brain.append(accuracy(grade(lambda s, m=m: m.predict(tokenize(s)), test_part)))
            maverick.append(accuracy(grade(as_maverick_runs(m), test_part)))
    full = variants([(label, tokenize(s)) for label, s in examples])
    print("\n5-fold cross-validation (test words the training folds never had are where the swap can help):")
    for name, (brain, maverick) in results.items():
        print(f"  {name:22} brain {np.mean(brain):.1%}  as MAVERICK runs {np.mean(maverick):.1%}  "
              f"hard cases {accuracy(grade(lambda s, m=full[name]: m.predict(tokenize(s)), hard)):.0%}")
    swap = full["+ unknown-word swap"]
    changed = [(s, " ".join(swap.translate(tokenize(s)))) for _, s in hard if swap.translate(tokenize(s)) != tokenize(s)]
    print(f"\nHard cases with a swapped word ({len(changed)}):")
    for before, after in changed[:12]:
        print(f"  {before!r}\n      -> {after!r}")


if __name__ == "__main__":
    main()
