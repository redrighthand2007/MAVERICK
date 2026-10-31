from collections import Counter

from maverick.brain.dataset import INTENTS_PATH, folds, load_examples
from maverick.brain.evaluate import accuracy, cross_validate, macro_f1, per_label


def test_folds_test_every_sentence_exactly_once():
    examples = load_examples(INTENTS_PATH)
    parts = folds(examples, k=5)
    tested = [e for _, test in parts for e in test]
    assert sorted(tested) == sorted(examples)
    for train, test in parts:
        assert len(train) + len(test) == len(examples)
        assert not set(train) & set(test)


def test_folds_are_stratified():
    examples = load_examples(INTENTS_PATH)
    for _, test in folds(examples, k=5):
        assert set(Counter(l for l, _ in test)) == set(Counter(l for l, _ in examples))


def test_precision_recall_f1_by_hand():
    # real, predicted, confidence
    results = [("a", "a", 1), ("a", "a", 1), ("a", "b", 1), ("b", "b", 1), ("b", "a", 1)]
    scores = per_label(results)
    # a: said 3 times, right 2 -> precision 2/3; really 3, caught 2 -> recall 2/3
    assert [round(x, 3) for x in scores["a"][:3]] == [0.667, 0.667, 0.667]
    # b: said 2 times, right 1 -> 1/2; really 2, caught 1 -> 1/2
    assert scores["b"][:3] == (0.5, 0.5, 0.5)
    assert round(macro_f1(results), 3) == round((2 / 3 + 0.5) / 2, 3)
    assert accuracy(results) == 0.6


def test_cross_validate_a_perfect_and_a_useless_model():
    examples = [("x", f"x{i}") for i in range(10)] + [("y", f"y{i}") for i in range(10)]
    perfect = cross_validate(lambda part: (lambda s: (s[0], 1.0)), examples)
    always_x = cross_validate(lambda part: (lambda s: ("x", 1.0)), examples)
    assert perfect == (1.0, 1.0)
    assert always_x[0] == 0.5 and always_x[1] < 0.5
