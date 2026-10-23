"""Train the brain on intents.tsv and save it.  Run:  python -m maverick.brain.train"""
from collections import Counter

from maverick.brain import MODEL_PATH
from maverick.brain.dataset import INTENTS_PATH, load_examples
from maverick.brain.naive_bayes import NaiveBayes
from maverick.brain.text import tokenize


def train(examples) -> NaiveBayes:
    return NaiveBayes().fit([(label, tokenize(sentence)) for label, sentence in examples])


def main() -> None:
    examples = load_examples(INTENTS_PATH)
    model = train(examples)
    model.save(MODEL_PATH)
    print(f"Trained on {len(examples)} examples, {len(model.vocab)} distinct words.")
    for label, n in sorted(Counter(label for label, _ in examples).items()):
        print(f"  {label:<14} {n}")
    print(f"Saved to {MODEL_PATH}")


if __name__ == "__main__":
    main()
