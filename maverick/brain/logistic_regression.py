"""Multinomial logistic regression (softmax regression), written from scratch with NumPy (Stage 8.2).

Naive Bayes COUNTS how often words appear with each label. Logistic regression instead LEARNS a weight
for every (feature, label) pair by trial and error (gradient descent):

    score(label) = sum of weight[feature, label] for the sentence's features + bias[label]
    probabilities = softmax(scores)
    loss = -log(probability of the right label)       <- "how surprised was the model?"
    repeat: nudge every weight a little in the direction that lowers the loss.

Because it learns weights instead of multiplying independent word odds, it can use overlapping
features like "started" and "started_chrome" without double-counting them.
"""
import json
from pathlib import Path

import numpy as np

from maverick.brain.features import TfidfVectorizer


def softmax(scores: np.ndarray) -> np.ndarray:
    scores = scores - scores.max(axis=1, keepdims=True)  # avoid overflow; doesn't change the result
    exps = np.exp(scores)
    return exps / exps.sum(axis=1, keepdims=True)


class LogisticRegression:
    kind = "logistic_regression"
    # Its confidence is spread over ~40 labels, so a lower cut-off than Naive Bayes is best (8.8 sweep).
    threshold = 0.4

    # Settings picked by 5-fold cross-validation (Stage 8.8): more epochs and a bigger step, little L2.
    def __init__(self, epochs: int = 800, learning_rate: float = 4.0, l2: float = 1e-5, seed: int = 0):
        self.epochs, self.learning_rate, self.l2, self.seed = epochs, learning_rate, l2, seed
        self.vectorizer = TfidfVectorizer()
        self.labels: list[str] = []
        self.weights = np.zeros((0, 0))
        self.bias = np.zeros(0)

    def fit(self, examples: list[tuple[str, list[str]]]) -> "LogisticRegression":
        docs = [tokens for _, tokens in examples]
        self.labels = sorted({label for label, _ in examples})
        x = self.vectorizer.fit(docs).transform(docs)
        y = np.zeros((len(examples), len(self.labels)))     # one-hot: a 1 in the right label's column
        for row, (label, _) in enumerate(examples):
            y[row, self.labels.index(label)] = 1

        rng = np.random.default_rng(self.seed)
        self.weights = rng.normal(0, 0.01, (x.shape[1], len(self.labels)))
        self.bias = np.zeros(len(self.labels))
        velocity_w, velocity_b = np.zeros_like(self.weights), np.zeros_like(self.bias)
        for _ in range(self.epochs):
            probs = softmax(x @ self.weights + self.bias)
            error = (probs - y) / len(examples)               # gradient of the loss w.r.t. the scores
            grad_w = x.T @ error + self.l2 * self.weights      # l2: keeps weights small, so it doesn't memorise
            grad_b = error.sum(axis=0)
            # Momentum: keep part of the last step, so learning rolls through flat stretches faster.
            velocity_w = 0.9 * velocity_w - self.learning_rate * grad_w
            velocity_b = 0.9 * velocity_b - self.learning_rate * grad_b
            self.weights += velocity_w
            self.bias += velocity_b
        return self

    def predict_proba(self, tokens: list[str]) -> dict[str, float]:
        probs = softmax(self.vectorizer.transform([tokens]) @ self.weights + self.bias)[0]
        return dict(zip(self.labels, probs.tolist()))

    def predict(self, tokens: list[str]) -> tuple[str, float]:
        probs = self.predict_proba(tokens)
        label = max(probs, key=probs.get)
        return label, probs[label]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"kind": self.kind, "labels": self.labels, "vectorizer": self.vectorizer.to_dict(),
                "weights": np.round(self.weights, 6).tolist(), "bias": self.bias.tolist()}
        path.write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "LogisticRegression":
        data = json.loads(path.read_text(encoding="utf-8"))
        model = cls()
        model.labels = data["labels"]
        model.vectorizer = TfidfVectorizer.from_dict(data["vectorizer"])
        model.weights = np.array(data["weights"])
        model.bias = np.array(data["bias"])
        return model
