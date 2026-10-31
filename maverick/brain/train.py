"""Train the brain on intents.tsv and save it.

Run:  python -m maverick.brain.train                       (the default brain)
      python -m maverick.brain.train naive_bayes           (or any kind in maverick.brain.MODELS)
"""
import sys
from collections import Counter

from maverick.brain import DEFAULT_KIND, MODEL_PATH, MODELS
from maverick.brain.dataset import INTENTS_PATH, load_examples
from maverick.brain.text import tokenize


def train(examples, kind: str = DEFAULT_KIND):
    return MODELS[kind]().fit([(label, tokenize(sentence)) for label, sentence in examples])


def main() -> None:
    kind = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_KIND
    if kind not in MODELS:
        sys.exit(f"Unknown brain '{kind}'. Choose one of: {', '.join(MODELS)}")
    examples = load_examples(INTENTS_PATH)
    model = train(examples, kind)
    model.save(MODEL_PATH)
    print(f"Trained a {kind} brain on {len(examples)} examples.")
    for label, n in sorted(Counter(label for label, _ in examples).items()):
        print(f"  {label:<14} {n}")
    print(f"Saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
