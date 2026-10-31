"""Turning tokens into numbers a model can learn from (Stage 8.1).

n-grams: besides single words, also count word pairs, so word ORDER shows up:
    "what started chrome"   -> started, chrome, what_started, started_chrome ...
    "what did chrome start" -> chrome, start, chrome_start ...

TF-IDF: a word's weight = how often it is in THIS sentence (TF)
        x how rare it is across all sentences (IDF).
"the" is everywhere, so it weighs almost nothing; "rename" is rare, so it weighs a lot.
"""
import math
from collections import Counter

import numpy as np


def ngrams(tokens: list[str]) -> list[str]:
    """Words plus word pairs. <s> and </s> mark the start and end, so "kill ..." differs from "... kill"."""
    padded = ["<s>", *tokens, "</s>"]
    return tokens + [f"{a}_{b}" for a, b in zip(padded, padded[1:])]


class TfidfVectorizer:
    def __init__(self):
        self.index: dict[str, int] = {}   # feature -> column number
        self.idf: np.ndarray = np.zeros(0)

    def fit(self, documents: list[list[str]]) -> "TfidfVectorizer":
        df = Counter(feature for doc in documents for feature in set(ngrams(doc)))
        self.index = {feature: i for i, feature in enumerate(sorted(df))}
        n = len(documents)
        # +1 smoothing keeps a word that is in every sentence above zero.
        self.idf = np.array([math.log((1 + n) / (1 + df[f])) + 1 for f in sorted(df)])
        return self

    def transform(self, documents: list[list[str]]) -> np.ndarray:
        matrix = np.zeros((len(documents), len(self.index)))
        for row, doc in enumerate(documents):
            for feature, count in Counter(ngrams(doc)).items():
                col = self.index.get(feature)
                if col is not None:  # never-seen words are ignored
                    matrix[row, col] = count * self.idf[col]
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        return matrix / np.where(norms == 0, 1, norms)  # same length for short and long sentences

    def to_dict(self) -> dict:
        return {"features": sorted(self.index, key=self.index.get), "idf": self.idf.tolist()}

    @classmethod
    def from_dict(cls, data: dict) -> "TfidfVectorizer":
        vec = cls()
        vec.index = {f: i for i, f in enumerate(data["features"])}
        vec.idf = np.array(data["idf"])
        return vec
