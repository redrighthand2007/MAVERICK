"""Three more classic classifiers, written from scratch with NumPy (Stage 8.3), to compare with the brain.

Same input as logistic regression: each sentence becomes TF-IDF numbers over its words and word pairs.

Linear SVM (support vector machine): like logistic regression, one weight per (feature, label), but a
  different goal. Logistic regression wants the right label to be PROBABLE; the SVM only wants it to win
  by a MARGIN of at least 1 ("hinge loss"), and stops caring about sentences already won by that much.
  So only the hard, borderline sentences (the "support vectors") shape the weights.

k-nearest neighbours: no training at all. To label a new sentence, find the k most similar training
  sentences (cosine similarity of their TF-IDF vectors) and let them vote. "Lazy": all work at question time.

Decision tree: a flowchart learned from the data. At each step it asks the yes/no question
  "does the sentence contain feature X?" that best separates the labels (lowest Gini impurity), then
  repeats on each side. Easy to read, but it learns by heart: one tree is jumpy on small data.
"""
import json
from pathlib import Path

import numpy as np

from maverick.brain.features import TfidfVectorizer
from maverick.brain.logistic_regression import softmax


def one_hot(examples, labels) -> np.ndarray:
    y = np.zeros((len(examples), len(labels)))
    for row, (label, _) in enumerate(examples):
        y[row, labels.index(label)] = 1
    return y


class LinearSVM:
    kind = "linear_svm"
    threshold = 0.4  # its "confidence" is a softmax over margins, spread over ~45 labels like logistic regression

    def __init__(self, epochs: int = 600, learning_rate: float = 2.0, l2: float = 1e-4):
        self.epochs, self.learning_rate, self.l2 = epochs, learning_rate, l2
        self.vectorizer = TfidfVectorizer()
        self.labels: list[str] = []
        self.weights = np.zeros((0, 0))
        self.bias = np.zeros(0)

    def fit(self, examples) -> "LinearSVM":
        docs = [tokens for _, tokens in examples]
        self.labels = sorted({label for label, _ in examples})
        x = self.vectorizer.fit(docs).transform(docs)
        y = one_hot(examples, self.labels) * 2 - 1           # +1 for the right label, -1 for every other
        self.weights = np.zeros((x.shape[1], len(self.labels)))
        self.bias = np.zeros(len(self.labels))
        for _ in range(self.epochs):
            margins = y * (x @ self.weights + self.bias)
            missed = (margins < 1).astype(float) * y          # only sentences NOT yet won by a margin of 1 count
            self.weights += self.learning_rate * (x.T @ missed / len(x) - self.l2 * self.weights)
            self.bias += self.learning_rate * missed.mean(axis=0)
        return self

    def predict_proba(self, tokens) -> dict[str, float]:
        scores = self.vectorizer.transform([tokens]) @ self.weights + self.bias
        return dict(zip(self.labels, softmax(scores * 3)[0].tolist()))  # x3: margins are small numbers

    def predict(self, tokens) -> tuple[str, float]:
        probs = self.predict_proba(tokens)
        label = max(probs, key=probs.get)
        return label, probs[label]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"kind": self.kind, "labels": self.labels, "vectorizer": self.vectorizer.to_dict(),
                                    "weights": np.round(self.weights, 6).tolist(), "bias": self.bias.tolist()}),
                        encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "LinearSVM":
        data = json.loads(path.read_text(encoding="utf-8"))
        model = cls()
        model.labels, model.vectorizer = data["labels"], TfidfVectorizer.from_dict(data["vectorizer"])
        model.weights, model.bias = np.array(data["weights"]), np.array(data["bias"])
        return model


class KNearest:
    kind = "k_nearest"
    threshold = 0.6  # confidence = share of the (similarity-weighted) neighbour votes

    def __init__(self, k: int = 5):
        self.k = k
        self.examples: list[tuple[str, list[str]]] = []

    def fit(self, examples) -> "KNearest":
        self.examples = list(examples)
        self.vectorizer = TfidfVectorizer().fit([tokens for _, tokens in examples])
        self.matrix = self.vectorizer.transform([tokens for _, tokens in examples])  # rows already length 1
        self.labels = sorted({label for label, _ in examples})
        return self

    def predict_proba(self, tokens) -> dict[str, float]:
        similarity = self.matrix @ self.vectorizer.transform([tokens])[0]  # cosine, since rows are length 1
        nearest = np.argsort(-similarity)[:self.k]
        votes = {label: 0.0 for label in self.labels}
        for i in nearest:
            votes[self.examples[i][0]] += max(similarity[i], 1e-6)          # closer neighbours count more
        total = sum(votes.values())
        return {label: v / total for label, v in votes.items()}

    def predict(self, tokens) -> tuple[str, float]:
        probs = self.predict_proba(tokens)
        label = max(probs, key=probs.get)
        return label, probs[label]

    def save(self, path: Path) -> None:
        """Nothing was learned, so the model IS its training sentences."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"kind": self.kind, "k": self.k, "examples": self.examples}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "KNearest":
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls(data["k"]).fit([(label, tokens) for label, tokens in data["examples"]])


class DecisionTree:
    kind = "decision_tree"
    threshold = 0.6  # confidence = how pure the leaf is (with a little smoothing)

    def __init__(self, max_depth: int = 40, min_split: int = 2):
        self.max_depth, self.min_split = max_depth, min_split
        self.vectorizer = TfidfVectorizer()
        self.labels: list[str] = []
        self.tree = None

    def fit(self, examples) -> "DecisionTree":
        docs = [tokens for _, tokens in examples]
        self.labels = sorted({label for label, _ in examples})
        x = self.vectorizer.fit(docs).transform(docs) > 0      # yes/no: does the sentence have this feature?
        y = one_hot(examples, self.labels)
        self.features = sorted(self.vectorizer.index, key=self.vectorizer.index.get)
        self.tree = self.grow(x, y, np.arange(len(x)), 0)
        return self

    @staticmethod
    def gini(counts: np.ndarray) -> np.ndarray:
        """Impurity of a group: 0 = all one label, near 1 = many labels mixed. counts: (..., labels)."""
        n = counts.sum(axis=-1, keepdims=True)
        p = counts / np.where(n == 0, 1, n)
        return 1 - (p ** 2).sum(axis=-1)

    def grow(self, x, y, rows, depth):
        counts = y[rows].sum(axis=0)
        if depth >= self.max_depth or len(rows) < self.min_split or counts.max() == len(rows):
            return {"leaf": counts.tolist()}
        with_f = x[rows].T.astype(float) @ y[rows]              # label counts among sentences WITH each feature
        without_f = counts - with_f
        n_with = with_f.sum(axis=1)
        # Weighted impurity after splitting on each feature; features that don't split anything are skipped.
        cost = (n_with * self.gini(with_f) + (len(rows) - n_with) * self.gini(without_f)) / len(rows)
        cost[(n_with == 0) | (n_with == len(rows))] = np.inf
        best = int(np.argmin(cost))
        if not np.isfinite(cost[best]) or cost[best] >= self.gini(counts):
            return {"leaf": counts.tolist()}
        has = x[rows, best]
        return {"feature": self.features[best], "yes": self.grow(x, y, rows[has], depth + 1),
                "no": self.grow(x, y, rows[~has], depth + 1)}

    def predict_proba(self, tokens) -> dict[str, float]:
        present = {f for f, v in zip(self.features, self.vectorizer.transform([tokens])[0]) if v > 0}
        node = self.tree
        while "leaf" not in node:
            node = node["yes"] if node["feature"] in present else node["no"]
        counts = np.array(node["leaf"]) + 0.1                    # a 1-sentence leaf isn't 100% sure
        return dict(zip(self.labels, (counts / counts.sum()).tolist()))

    def predict(self, tokens) -> tuple[str, float]:
        probs = self.predict_proba(tokens)
        label = max(probs, key=probs.get)
        return label, probs[label]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"kind": self.kind, "labels": self.labels, "vectorizer": self.vectorizer.to_dict(),
                                    "tree": self.tree}), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "DecisionTree":
        data = json.loads(path.read_text(encoding="utf-8"))
        model = cls()
        model.labels, model.tree = data["labels"], data["tree"]
        model.vectorizer = TfidfVectorizer.from_dict(data["vectorizer"])
        model.features = sorted(model.vectorizer.index, key=model.vectorizer.index.get)
        return model
