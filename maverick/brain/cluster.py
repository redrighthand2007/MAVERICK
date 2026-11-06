"""Clustering with k-means (Stage 8.23), written from scratch in NumPy.

Like the isolation forest (8.22) this is UNSUPERVISED: no labels. Instead of "which point is odd?"
it asks "which points belong together?", e.g. the files in Downloads:
  invoice_march.pdf, invoice_april.pdf          -> one group
  Screenshot 2026-10-01.png, Screenshot ...png  -> another
  setup.exe, vlc-installer.msi                  -> another

k-means, for a chosen number of groups k:
  1. pick k starting centres (k-means++: spread out, so two centres don't start in the same crowd)
  2. give every point to its nearest centre
  3. move every centre to the average of its points
  4. repeat 2-3 until nothing changes
Different starts can end differently, so it runs a few times and keeps the tightest result.

But how many groups? k is chosen with the SILHOUETTE score: for each point, compare how close it is to its own
group (a) with how close it is to the nearest other group (b): (b - a) / max(a, b).
Near 1 = clearly in the right group, near 0 = on the border. The k with the best average wins.

Run:  python -m maverick.brain.cluster     (checks it on made-up file names whose true groups we know)
"""
import numpy as np


class KMeans:
    def __init__(self, k: int, restarts: int = 5, max_steps: int = 100, seed: int = 42):
        self.k, self.restarts, self.max_steps, self.seed = k, restarts, max_steps, seed
        self.centres = None
        self.labels = None
        self.inertia = float("inf")  # total squared distance from points to their centre: lower = tighter

    def fit(self, X) -> "KMeans":
        X = np.asarray(X, dtype=float)
        rng = np.random.default_rng(self.seed)
        for _ in range(self.restarts):
            centres = self.start(X, rng)
            for _ in range(self.max_steps):
                labels = self.nearest(X, centres)
                moved = np.array([X[labels == j].mean(axis=0) if np.any(labels == j) else centres[j]
                                  for j in range(self.k)])
                if np.allclose(moved, centres):
                    break
                centres = moved
            labels = self.nearest(X, centres)
            inertia = float(((X - centres[labels]) ** 2).sum())
            if inertia < self.inertia:
                self.centres, self.labels, self.inertia = centres, labels, inertia
        return self

    def start(self, X, rng) -> np.ndarray:
        """k-means++: the first centre at random, then each next one far from the centres so far."""
        centres = [X[rng.integers(len(X))]]
        for _ in range(1, self.k):
            distance = np.min([((X - c) ** 2).sum(axis=1) for c in centres], axis=0)
            if distance.sum() == 0:
                centres.append(X[rng.integers(len(X))])
            else:
                centres.append(X[rng.choice(len(X), p=distance / distance.sum())])
        return np.array(centres)

    @staticmethod
    def nearest(X, centres) -> np.ndarray:
        return np.argmin(((X[:, None, :] - centres[None, :, :]) ** 2).sum(axis=2), axis=1)


def silhouette(X, labels) -> float:
    """Average (b - a) / max(a, b) over all points; 0 when there is only one group."""
    X, labels = np.asarray(X, dtype=float), np.asarray(labels)
    groups = np.unique(labels)
    if len(groups) < 2:
        return 0.0
    distance = np.sqrt(((X[:, None, :] - X[None, :, :]) ** 2).sum(axis=2))
    scores = []
    for i in range(len(X)):
        own = labels == labels[i]
        if own.sum() == 1:
            scores.append(0.0)  # alone in its group: no "a" to measure
            continue
        a = distance[i, own].sum() / (own.sum() - 1)
        b = min(distance[i, labels == g].mean() for g in groups if g != labels[i])
        scores.append((b - a) / max(a, b) if max(a, b) > 0 else 0.0)
    return float(np.mean(scores))


def best_kmeans(X, max_k: int = 10) -> KMeans:
    """Try k = 2 .. max_k and keep the one with the best silhouette."""
    X = np.asarray(X, dtype=float)
    best, best_score = None, -1.0
    for k in range(2, min(max_k, len(X) - 1) + 1):
        model = KMeans(k).fit(X)
        score = silhouette(X, model.labels)
        if score > best_score:
            best, best_score = model, score
    return best or KMeans(1).fit(X)


def pair_agreement(truth, found) -> float:
    """Rand index: of all pairs of files, how often do both groupings agree on "same group" vs "different"?"""
    truth, found = np.asarray(truth), np.asarray(found)
    same_truth = truth[:, None] == truth[None, :]
    same_found = found[:, None] == found[None, :]
    upper = np.triu_indices(len(truth), k=1)
    return float((same_truth == same_found)[upper].mean())


def main() -> None:
    from maverick.agents.search.ops import SAMPLE_GROUPS, group_files, vectors

    names = [name for _, files in SAMPLE_GROUPS for name in files]
    truth = [group for group, files in SAMPLE_GROUPS for _ in files]
    X, words = vectors(names)
    model = best_kmeans(X)
    by_ext = [name.rsplit(".", 1)[-1].lower() for name in names]  # the obvious rule: one group per file type
    print(f"{len(names)} made-up file names in {len(SAMPLE_GROUPS)} true groups.")
    print(f"  k-means picked {model.k} groups (silhouette); pair agreement with the truth: "
          f"{pair_agreement(truth, model.labels):.1%}")
    print(f"  one group per extension:        {len(set(by_ext))} groups; pair agreement: "
          f"{pair_agreement(truth, by_ext):.1%}")
    print("\nThe groups it found:")
    for title, members in group_files(names, model, X, words):
        print(f"  {title} ({len(members)}): {', '.join(members[:4])}{' ...' if len(members) > 4 else ''}")


if __name__ == "__main__":
    main()
