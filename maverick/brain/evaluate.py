"""Grade the brain honestly.  Run:  python -m maverick.brain.evaluate"""
from collections import Counter

from maverick.agents.files.agent import FileAgent
from maverick.brain.dataset import HARD_CASES_PATH, INTENTS_PATH, load_examples, split
from maverick.brain.text import tokenize
from maverick.brain.train import train


def keyword_rules(sentence: str) -> tuple[str, float]:
    """Baseline: today's keyword parse(). The brain must beat this to earn its place."""
    intent = FileAgent().parse(sentence)
    return (f"files.{intent.operation}" if intent else "unknown"), 1.0


def grade(predict, examples) -> list[tuple[str, str, float]]:
    """Returns (real label, predicted label, confidence) for every example."""
    return [(label, *predict(sentence)) for label, sentence in examples]


def accuracy(results) -> float:
    return sum(real == guess for real, guess, _ in results) / len(results)


def print_report(name: str, results) -> None:
    labels = sorted({real for real, _, _ in results} | {guess for _, guess, _ in results})
    print(f"\n=== {name}: accuracy {accuracy(results):.0%} ({len(results)} sentences) ===")

    print("Per label:")
    for label in labels:
        mine = [r for r in results if r[0] == label]
        if mine:
            print(f"  {label:<14} {accuracy(mine):.0%}  ({len(mine)})")

    print("Confusion matrix (rows = real, columns = predicted):")
    short = [label.split(".")[-1][:7] for label in labels]
    print(" " * 16 + " ".join(f"{s:>7}" for s in short))
    pairs = Counter((real, guess) for real, guess, _ in results)
    for label in labels:
        print(f"  {label:<14}" + " ".join(f"{pairs[(label, g)]:>7}" for g in labels))


def print_thresholds(results) -> None:
    print("\nConfidence threshold: accepted predictions, and how many of those are wrong")
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        accepted = [r for r in results if r[2] >= t]
        wrong = sum(real != guess for real, guess, _ in accepted)
        print(f"  >= {t:.1f}: {len(accepted):>3}/{len(results)} accepted, {wrong} wrong")


def main() -> None:
    train_set, test_set = split(load_examples(INTENTS_PATH))
    hard = load_examples(HARD_CASES_PATH)
    model = train(train_set)
    brain = lambda s: model.predict(tokenize(s))

    print(f"Trained on {len(train_set)}, testing on {len(test_set)} unseen + {len(hard)} hard cases.")
    print_report("Brain, test set", grade(brain, test_set))
    print_report("Brain, hard cases", grade(brain, hard))
    print_report("Keyword rules, test set", grade(keyword_rules, test_set))
    print_report("Keyword rules, hard cases", grade(keyword_rules, hard))
    print_thresholds(grade(brain, test_set + hard))

    misses = [(r, s) for r, s in zip(grade(brain, hard), hard) if r[0] != r[1]]
    if misses:
        print("\nHard cases the brain got wrong:")
        for (real, guess, conf), (_, sentence) in misses:
            print(f"  {sentence!r}: said {guess} ({conf:.2f}), should be {real}")


if __name__ == "__main__":
    main()
