"""Anomaly detection with an isolation forest (Stage 8.22), written from scratch in NumPy.

Every other model so far was SUPERVISED: it learned from labelled examples ("this sentence = files.copy").
Nobody can label "this program is behaving strangely", so this one is UNSUPERVISED: it only sees the data
and finds the points that don't look like the rest.

The idea: pick a random column (say RAM) and a random cut point between its min and max. Repeat inside each
side, building a random tree, until every point sits alone. A normal program sits in a crowd, so it takes
many cuts to isolate; an odd one (500 network connections when every other program has 0-20) is cut off
after just a few. So: the SHORTER the path to a point, the more unusual it is.

One random tree is noisy, so a forest of 100 trees votes, each built on a random sample (256 points max).
The average path length is turned into a score between 0 and 1:
  score = 2 ** (-average path / c(n))       c(n) = the average path in a random tree of n points
  about 0.5 or less = normal,  close to 1 = clearly unusual
(Liu, Ting & Zhou, "Isolation Forest", 2008.)

Run:  python -m maverick.brain.anomaly     (scores your running programs, with 3 planted fakes to find)
"""
import math

import numpy as np

EULER_GAMMA = 0.5772156649


def average_path(n: int) -> float:
    """c(n): the average number of cuts to isolate one point among n, in a random binary tree."""
    if n <= 1:
        return 0.0
    if n == 2:
        return 1.0
    return 2 * (math.log(n - 1) + EULER_GAMMA) - 2 * (n - 1) / n


class IsolationForest:
    def __init__(self, trees: int = 100, sample_size: int = 256, seed: int = 42):
        self.trees, self.sample_size, self.seed = trees, sample_size, seed
        self.forest: list = []
        self.n = 0

    def fit(self, X) -> "IsolationForest":
        X = np.asarray(X, dtype=float)
        rng = np.random.default_rng(self.seed)
        self.n = min(self.sample_size, len(X))
        limit = math.ceil(math.log2(max(self.n, 2)))  # deeper than this, a point is "normal enough"
        self.forest = [self.grow(X[rng.choice(len(X), self.n, replace=False)], 0, limit, rng)
                       for _ in range(self.trees)]
        return self

    def grow(self, X, depth: int, limit: int, rng):
        """A tree is either ("leaf", size) or ("cut", column, value, left, right)."""
        if depth >= limit or len(X) <= 1:
            return ("leaf", len(X))
        spread = X.max(axis=0) - X.min(axis=0)
        columns = np.flatnonzero(spread > 0)
        if len(columns) == 0:  # all the same: can't cut
            return ("leaf", len(X))
        column = rng.choice(columns)
        value = rng.uniform(X[:, column].min(), X[:, column].max())
        left = X[:, column] < value
        return ("cut", column, value, self.grow(X[left], depth + 1, limit, rng),
                self.grow(X[~left], depth + 1, limit, rng))

    @staticmethod
    def path(tree, x, depth: int = 0) -> float:
        if tree[0] == "leaf":
            # A leaf that still holds several points: add the cuts it WOULD have taken to separate them.
            return depth + average_path(tree[1])
        _, column, value, left, right = tree
        return IsolationForest.path(left if x[column] < value else right, x, depth + 1)

    def scores(self, X) -> np.ndarray:
        """0..1 for every row: about 0.5 or less is normal, close to 1 is unusual."""
        X = np.asarray(X, dtype=float)
        mean_path = np.array([np.mean([self.path(tree, x) for tree in self.forest]) for x in X])
        return 2 ** (-mean_path / average_path(self.n))


def reasons(X, row: int, names: list[str], limit: int = 2) -> list[str]:
    """WHY a row stands out: its columns furthest from the typical value, in median absolute deviations.

    The forest only says "unusual"; this turns it into something a person can check.
    """
    X = np.asarray(X, dtype=float)
    median = np.median(X, axis=0)
    spread = np.median(np.abs(X - median), axis=0)
    spread = np.where(spread > 0, spread, np.std(X, axis=0) + 1e-9)
    distance = np.abs(X[row] - median) / spread
    order = np.argsort(-distance)
    return [names[c] for c in order[:limit] if distance[c] >= 3]


def main() -> None:
    from maverick.agents.process.ops import COLUMNS, featurize, planted_fakes, program_table

    names, rows, raw = program_table(seconds=6)
    fakes = planted_fakes(raw)
    all_names, X = names + [n for n, _ in fakes], np.array(rows + [featurize(v) for _, v in fakes])
    scores = IsolationForest().fit(X).scores(X)
    print(f"{len(names)} running programs + {len(fakes)} planted fakes, {len(COLUMNS)} numbers each.\n")
    print("Isolation forest, most unusual first:")
    for rank, i in enumerate(np.argsort(-scores)[:10], 1):
        why = ", ".join(reasons(X, i, COLUMNS)) or "-"
        print(f"  {rank:2}. {scores[i]:.2f}  {all_names[i]:32} {why}")
    # The baseline anyone would try first: sort by RAM, like Task Manager.
    ram = [v["ram"] for v in raw] + [v["ram"] for _, v in fakes]
    ram_rank = {i: r for r, i in enumerate(np.argsort(-np.array(ram)), 1)}
    forest_rank = {i: r for r, i in enumerate(np.argsort(-scores), 1)}
    print(f"\nWhere the planted fakes landed (out of {len(X)}):")
    print(f"  {'':32}{'forest':>8}{'by RAM':>8}")
    for i in range(len(names), len(X)):
        print(f"  {all_names[i]:32}{forest_rank[i]:>8}{ram_rank[i]:>8}")


if __name__ == "__main__":
    main()
