"""A small neural network (multi-layer perceptron), written from scratch with NumPy (Stage 8.9).

Logistic regression maps features straight to labels. A neural network puts a HIDDEN LAYER in between:

    features (TF-IDF word pairs)                       ~4000 numbers
      -> hidden layer: 128 neurons, each = ReLU(weighted sum of features)
      -> output layer: one score per label -> softmax -> probabilities

The hidden neurons learn their own in-between ideas ("this is about files", "this is a question") that
the output layer then combines. Training is backpropagation: run a batch forward, measure the loss,
pass the error backwards through each layer to get every weight's gradient, take a small step.

Tricks that matter on small data:
  - dropout: randomly switch off 30% of hidden neurons while training, so no single one is relied on
  - mini-batches + Adam: update after every 32 sentences, with a step size per weight that adapts itself
  - early stopping by epochs: we stop after a fixed number of passes chosen by cross-validation
"""
import json
from pathlib import Path

import numpy as np

from maverick.brain.features import TfidfVectorizer
from maverick.brain.logistic_regression import softmax


class MLP:
    kind = "mlp"
    threshold = 0.4  # chosen by the same cut-off sweep as logistic regression

    def __init__(self, hidden: int = 128, epochs: int = 40, learning_rate: float = 0.005, dropout: float = 0.3,
                 batch_size: int = 32, l2: float = 1e-5, seed: int = 0):
        self.hidden, self.epochs, self.learning_rate = hidden, epochs, learning_rate
        self.dropout, self.batch_size, self.l2, self.seed = dropout, batch_size, l2, seed
        self.vectorizer = TfidfVectorizer()
        self.labels: list[str] = []
        self.params: dict[str, np.ndarray] = {}

    def forward(self, x: np.ndarray, rng=None) -> tuple[np.ndarray, dict]:
        """Returns probabilities, plus what backprop needs. With rng given, dropout is on (training)."""
        z1 = x @ self.params["w1"] + self.params["b1"]
        h = np.maximum(z1, 0)                                   # ReLU: negative -> 0
        mask = None
        if rng is not None and self.dropout:
            mask = (rng.random(h.shape) >= self.dropout) / (1 - self.dropout)  # keep the average the same
            h = h * mask
        probs = softmax(h @ self.params["w2"] + self.params["b2"])
        return probs, {"x": x, "z1": z1, "h": h, "mask": mask}

    def backward(self, probs: np.ndarray, y: np.ndarray, cache: dict) -> dict[str, np.ndarray]:
        """Backpropagation: the chain rule, layer by layer from the output back to the input."""
        n = len(y)
        d_scores = (probs - y) / n                              # softmax + cross-entropy, combined
        grads = {"w2": cache["h"].T @ d_scores + self.l2 * self.params["w2"], "b2": d_scores.sum(axis=0)}
        d_h = d_scores @ self.params["w2"].T
        if cache["mask"] is not None:
            d_h = d_h * cache["mask"]
        d_z1 = d_h * (cache["z1"] > 0)                          # ReLU only passes gradient where it was active
        grads["w1"] = cache["x"].T @ d_z1 + self.l2 * self.params["w1"]
        grads["b1"] = d_z1.sum(axis=0)
        return grads

    def fit(self, examples: list[tuple[str, list[str]]]) -> "MLP":
        docs = [tokens for _, tokens in examples]
        self.labels = sorted({label for label, _ in examples})
        x = self.vectorizer.fit(docs).transform(docs)
        y = np.zeros((len(examples), len(self.labels)))
        for row, (label, _) in enumerate(examples):
            y[row, self.labels.index(label)] = 1

        rng = np.random.default_rng(self.seed)
        n_in, n_out = x.shape[1], len(self.labels)
        # He initialisation: start weights at a size that suits ReLU, so signals neither die nor explode.
        self.params = {"w1": rng.normal(0, np.sqrt(2 / n_in), (n_in, self.hidden)), "b1": np.zeros(self.hidden),
                       "w2": rng.normal(0, np.sqrt(2 / self.hidden), (self.hidden, n_out)), "b2": np.zeros(n_out)}
        # Adam keeps a running average of each gradient (m) and of its square (v).
        m = {k: np.zeros_like(v) for k, v in self.params.items()}
        v = {k: np.zeros_like(v) for k, v in self.params.items()}
        step = 0
        for _ in range(self.epochs):
            order = rng.permutation(len(x))                     # shuffle every epoch
            for start in range(0, len(x), self.batch_size):
                batch = order[start:start + self.batch_size]
                probs, cache = self.forward(x[batch], rng)
                grads = self.backward(probs, y[batch], cache)
                step += 1
                for k in self.params:
                    m[k] = 0.9 * m[k] + 0.1 * grads[k]
                    v[k] = 0.999 * v[k] + 0.001 * grads[k] ** 2
                    m_hat, v_hat = m[k] / (1 - 0.9 ** step), v[k] / (1 - 0.999 ** step)
                    self.params[k] -= self.learning_rate * m_hat / (np.sqrt(v_hat) + 1e-8)
        return self

    def predict_proba(self, tokens: list[str]) -> dict[str, float]:
        probs, _ = self.forward(self.vectorizer.transform([tokens]))   # no rng: dropout off
        return dict(zip(self.labels, probs[0].tolist()))

    def predict(self, tokens: list[str]) -> tuple[str, float]:
        probs = self.predict_proba(tokens)
        label = max(probs, key=probs.get)
        return label, probs[label]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {"kind": self.kind, "labels": self.labels, "vectorizer": self.vectorizer.to_dict(),
                "params": {k: np.round(v, 6).tolist() for k, v in self.params.items()}}
        path.write_text(json.dumps(data), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "MLP":
        data = json.loads(path.read_text(encoding="utf-8"))
        model = cls()
        model.labels = data["labels"]
        model.vectorizer = TfidfVectorizer.from_dict(data["vectorizer"])
        model.params = {k: np.array(v) for k, v in data["params"].items()}
        return model
