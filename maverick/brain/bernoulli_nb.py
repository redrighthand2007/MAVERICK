"""Bernoulli Naive Bayes (Stage 8.4): the brain's first model, made to listen to what's MISSING too.

The original (multinomial) Naive Bayes counts how often each word appears with each label, and only looks
at the words that ARE in the sentence. Bernoulli Naive Bayes asks a yes/no question per vocabulary word:
"is it in the sentence?", and every NO counts as evidence too:
  score(label) = log P(label) + sum over ALL known words of
                   log P(word present | label)       if the word is in the sentence
                   log (1 - P(word present | label))  if it isn't
So "kill chrome" without the word "file" is a little less likely to be a files request.
Repeats don't matter (present is present), which suits short commands where words rarely repeat.
"""
import json
from pathlib import Path

import numpy as np


class BernoulliNB:
    kind = "bernoulli_nb"
    threshold = 0.6  # Naive Bayes confidences run high, like the multinomial one

    def __init__(self, alpha: float = 0.1):
        # Smoothing: pretend every word was seen `alpha` extra times present and absent. With the usual +1, the
        # 71-sentence "unknown" label paid far less for all the words a sentence DOESN'T have than the 30-sentence
        # labels, and won almost every time: 5.8% (5-fold). alpha 0.3: 63.0%, 0.1: 77.6%, 0.01: 76.1%.
        self.alpha = alpha
        self.labels: list[str] = []
        self.vocab: dict[str, int] = {}
        self.log_prior = np.zeros(0)
        self.log_yes = np.zeros((0, 0))   # log P(word present | label), shape (labels, words)
        self.log_no = np.zeros((0, 0))    # log P(word absent  | label)

    def fit(self, examples) -> "BernoulliNB":
        self.labels = sorted({label for label, _ in examples})
        self.vocab = {w: i for i, w in enumerate(sorted({w for _, tokens in examples for w in tokens}))}
        present = np.zeros((len(self.labels), len(self.vocab)))
        per_label = np.zeros(len(self.labels))
        for label, tokens in examples:
            row = self.labels.index(label)
            per_label[row] += 1
            for w in set(tokens):
                present[row, self.vocab[w]] += 1
        p = (present + self.alpha) / (per_label[:, None] + 2 * self.alpha)  # smoothing for a yes/no count
        self.log_yes, self.log_no = np.log(p), np.log(1 - p)
        self.log_prior = np.log(per_label / per_label.sum())
        return self

    def predict_proba(self, tokens) -> dict[str, float]:
        x = np.zeros(len(self.vocab))
        for w in tokens:
            if w in self.vocab:
                x[self.vocab[w]] = 1
        scores = self.log_prior + self.log_yes @ x + self.log_no @ (1 - x)
        scores = np.exp(scores - scores.max())
        return dict(zip(self.labels, (scores / scores.sum()).tolist()))

    def predict(self, tokens) -> tuple[str, float]:
        probs = self.predict_proba(tokens)
        label = max(probs, key=probs.get)
        return label, probs[label]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"kind": self.kind, "labels": self.labels, "vocab": sorted(self.vocab, key=self.vocab.get),
                                    "log_prior": self.log_prior.tolist(), "log_yes": self.log_yes.tolist()}),
                        encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "BernoulliNB":
        data = json.loads(path.read_text(encoding="utf-8"))
        model = cls()
        model.labels = data["labels"]
        model.vocab = {w: i for i, w in enumerate(data["vocab"])}
        model.log_prior, model.log_yes = np.array(data["log_prior"]), np.array(data["log_yes"])
        model.log_no = np.log(1 - np.exp(model.log_yes))
        return model
