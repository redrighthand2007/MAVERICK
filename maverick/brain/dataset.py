import random
from collections import defaultdict
from pathlib import Path

DATA_DIR = Path(__file__).parent / "data"
INTENTS_PATH = DATA_DIR / "intents.tsv"
HARD_CASES_PATH = DATA_DIR / "hard_cases.tsv"

Example = tuple[str, str]  # (label, sentence)


def load_examples(path: Path) -> list[Example]:
    examples = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.startswith("#"):
            continue
        label, sentence = line.split("\t", 1)
        examples.append((label.strip(), sentence.strip()))
    return examples


def folds(examples: list[Example], k: int = 5, seed: int = 42) -> list[tuple[list[Example], list[Example]]]:
    """Stratified k-fold cross-validation: k (train, test) pairs; every sentence is tested exactly once.

    One 80/20 split can be lucky or unlucky; the average over k folds is a fairer score for small data.
    """
    by_label = defaultdict(list)
    for example in examples:
        by_label[example[0]].append(example)
    rng = random.Random(seed)
    buckets = [[] for _ in range(k)]
    for label in sorted(by_label):
        group = by_label[label][:]
        rng.shuffle(group)
        for i, example in enumerate(group):
            buckets[i % k].append(example)
    return [([e for j, b in enumerate(buckets) if j != i for e in b], buckets[i]) for i in range(k)]


def split(examples: list[Example], test_ratio: float = 0.2, seed: int = 42) -> tuple[list[Example], list[Example]]:
    """Stratified split: every label keeps the same share in train and test."""
    by_label = defaultdict(list)
    for example in examples:
        by_label[example[0]].append(example)

    rng = random.Random(seed)  # fixed seed so results repeat
    train, test = [], []
    for label in sorted(by_label):
        group = by_label[label][:]
        rng.shuffle(group)
        n_test = max(1, round(len(group) * test_ratio))
        test += group[:n_test]
        train += group[n_test:]
    return train, test
