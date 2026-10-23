import json
import math
from collections import Counter
from pathlib import Path


class NaiveBayes:
    """Multinomial Naive Bayes, written from scratch.

    score(label) = log P(label) + sum of log P(word | label)
    The label with the highest score wins.
    """

    def __init__(self):
        self.label_counts: Counter = Counter()        # how many sentences each label has
        self.word_counts: dict[str, Counter] = {}     # label -> how often each word appears
        self.vocab: set[str] = set()                  # every word seen in training

    def fit(self, examples: list[tuple[str, list[str]]]) -> "NaiveBayes":
        for label, tokens in examples:
            self.label_counts[label] += 1
            self.word_counts.setdefault(label, Counter()).update(tokens)
            self.vocab.update(tokens)
        return self

    def log_scores(self, tokens: list[str]) -> dict[str, float]:
        total_sentences = sum(self.label_counts.values())
        vocab_size = len(self.vocab)
        scores = {}
        for label, n_sentences in self.label_counts.items():
            counts = self.word_counts[label]
            # Laplace smoothing: +1 on every count so an unseen word never gives probability 0.
            denominator = sum(counts.values()) + vocab_size
            score = math.log(n_sentences / total_sentences)
            for token in tokens:
                if token in self.vocab:  # words never seen in training tell us nothing
                    score += math.log((counts[token] + 1) / denominator)
            scores[label] = score
        return scores

    def predict_proba(self, tokens: list[str]) -> dict[str, float]:
        """Softmax: turn log-scores into probabilities that add up to 1."""
        scores = self.log_scores(tokens)
        top = max(scores.values())
        exps = {label: math.exp(s - top) for label, s in scores.items()}  # subtract max to avoid overflow
        total = sum(exps.values())
        return {label: e / total for label, e in exps.items()}

    def predict(self, tokens: list[str]) -> tuple[str, float]:
        probs = self.predict_proba(tokens)
        label = max(probs, key=probs.get)
        return label, probs[label]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "label_counts": self.label_counts,
            "word_counts": self.word_counts,
            "vocab": sorted(self.vocab),
        }
        path.write_text(json.dumps(data, indent=1), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "NaiveBayes":
        data = json.loads(path.read_text(encoding="utf-8"))
        model = cls()
        model.label_counts = Counter(data["label_counts"])
        model.word_counts = {label: Counter(c) for label, c in data["word_counts"].items()}
        model.vocab = set(data["vocab"])
        return model
