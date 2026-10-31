"""Grade the brain honestly.  Run:  python -m maverick.brain.evaluate   (or ... evaluate naive_bayes)"""
import sys
from collections import Counter

from maverick.brain import DEFAULT_KIND, MODELS
from maverick.brain.dataset import HARD_CASES_PATH, INTENTS_PATH, folds, load_examples, split
from maverick.brain.text import tokenize
from maverick.brain.train import train
from maverick.core.orchestrator import CONFIDENCE_THRESHOLD
from maverick.main import build

# The very same agents, in the same order, as MAVERICK really runs with.
AGENTS = build().agents


def keyword_rules(sentence: str) -> tuple[str, float]:
    """Baseline: every agent's keyword parse(), first match wins. The brain must beat this to earn its place."""
    for agent in AGENTS:
        intent = agent.parse(sentence)
        if intent is not None:
            return f"{agent.name}.{intent.operation}", 1.0
    return "unknown", 1.0


def as_maverick_runs(model):
    """What you actually get: the brain when it is confident, keyword rules otherwise."""
    def predict(sentence):
        guess, confidence = model.predict(tokenize(sentence))
        if confidence >= getattr(model, "threshold", CONFIDENCE_THRESHOLD) and guess != "unknown":
            return guess, confidence
        return keyword_rules(sentence)
    return predict


def grade(predict, examples) -> list[tuple[str, str, float]]:
    """Returns (real label, predicted label, confidence) for every example."""
    return [(label, *predict(sentence)) for label, sentence in examples]


def accuracy(results) -> float:
    return sum(real == guess for real, guess, _ in results) / len(results)


def per_label(results) -> dict[str, tuple[float, float, float, int]]:
    """label -> (precision, recall, F1, how many real examples).

    precision: of the times the brain SAID this label, how often was it right?
    recall:    of the sentences that really ARE this label, how many did it catch?
    F1:        one number that is high only when both are high (their harmonic mean).
    """
    scores = {}
    for label in sorted({real for real, _, _ in results} | {guess for _, guess, _ in results}):
        tp = sum(real == label and guess == label for real, guess, _ in results)
        said = sum(guess == label for _, guess, _ in results)
        real = sum(r == label for r, _, _ in results)
        precision = tp / said if said else 0.0
        recall = tp / real if real else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        scores[label] = (precision, recall, f1, real)
    return scores


def macro_f1(results) -> float:
    """Average F1 over labels: every label counts the same, however few examples it has."""
    scores = [f1 for _, _, f1, n in per_label(results).values() if n]
    return sum(scores) / len(scores)


def cross_validate(make_predict, examples, k: int = 5) -> tuple[float, float]:
    """Train on k-1 folds, test on the last one, k times. Returns (mean accuracy, mean macro F1).

    make_predict(train_examples) must return a function sentence -> (label, confidence).
    """
    accs, f1s = [], []
    for train_part, test_part in folds(examples, k):
        results = grade(make_predict(train_part), test_part)
        accs.append(accuracy(results))
        f1s.append(macro_f1(results))
    return sum(accs) / k, sum(f1s) / k


def print_report(name: str, results) -> None:
    labels = sorted({real for real, _, _ in results} | {guess for _, guess, _ in results})
    print(f"\n=== {name}: accuracy {accuracy(results):.0%}, macro F1 {macro_f1(results):.2f} "
          f"({len(results)} sentences) ===")

    print("Per label:          precision recall   F1  (examples)")
    for label, (precision, recall, f1, n) in per_label(results).items():
        if n:
            print(f"  {label:<18} {precision:>6.0%} {recall:>6.0%} {f1:>6.2f}  ({n})")

    print("Confusion matrix (rows = real, columns = predicted):")
    short = [label.split(".")[-1][:7] for label in labels]
    print(" " * 20 + " ".join(f"{s:>7}" for s in short))
    pairs = Counter((real, guess) for real, guess, _ in results)
    for label in labels:
        print(f"  {label:<18}" + " ".join(f"{pairs[(label, g)]:>7}" for g in labels))


def print_thresholds(results) -> None:
    print("\nConfidence threshold: accepted predictions, and how many of those are wrong")
    for t in (0.5, 0.6, 0.7, 0.8, 0.9):
        accepted = [r for r in results if r[2] >= t]
        wrong = sum(real != guess for real, guess, _ in accepted)
        print(f"  >= {t:.1f}: {len(accepted):>3}/{len(results)} accepted, {wrong} wrong")


def compare(examples, hard, k: int = 5) -> None:
    """Every kind of brain side by side. A new brain must beat the current one here before it replaces it."""
    print(f"{k}-fold cross-validation, every sentence tested once (hard cases: trained on everything):")
    for kind in MODELS:
        brain_scores, maverick_scores = [], []
        for train_part, test_part in folds(examples, k):
            model = train(train_part, kind)
            brain_scores.append(accuracy(grade(lambda s: model.predict(tokenize(s)), test_part)))
            maverick_scores.append(accuracy(grade(as_maverick_runs(model), test_part)))
        full = train(examples, kind)
        hard_brain = accuracy(grade(lambda s: full.predict(tokenize(s)), hard))
        hard_maverick = accuracy(grade(as_maverick_runs(full), hard))
        mark = "  <- default" if kind == DEFAULT_KIND else ""
        print(f"  {kind:<20} brain {sum(brain_scores) / k:.1%}  as MAVERICK runs {sum(maverick_scores) / k:.1%}"
              f"  | hard: brain {hard_brain:.0%}, as MAVERICK runs {hard_maverick:.0%}{mark}")


def main() -> None:
    examples = load_examples(INTENTS_PATH)
    hard = load_examples(HARD_CASES_PATH)
    compare(examples, hard)

    kind = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_KIND
    train_set, test_set = split(examples)
    model = train(train_set, kind)
    print(f"\nDetails for the {kind} brain:")
    brain = lambda s: model.predict(tokenize(s))

    print(f"Trained on {len(train_set)}, testing on {len(test_set)} unseen + {len(hard)} hard cases.")
    print_report("Brain, test set", grade(brain, test_set))
    print_report("Brain, hard cases", grade(brain, hard))
    print_report("Keyword rules, test set", grade(keyword_rules, test_set))
    print_report("Keyword rules, hard cases", grade(keyword_rules, hard))
    combined = as_maverick_runs(model)
    print(f"\n=== As MAVERICK runs (brain >= {model.threshold}, else rules): "
          f"test {accuracy(grade(combined, test_set)):.0%}, hard cases {accuracy(grade(combined, hard)):.0%} ===")
    print_thresholds(grade(brain, test_set + hard))

    misses = [(r, s) for r, s in zip(grade(brain, hard), hard) if r[0] != r[1]]
    if misses:
        print("\nHard cases the brain got wrong:")
        for (real, guess, conf), (_, sentence) in misses:
            print(f"  {sentence!r}: said {guess} ({conf:.2f}), should be {real}")


if __name__ == "__main__":
    main()
