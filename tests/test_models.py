import numpy as np

from maverick.brain.features import TfidfVectorizer, ngrams
from maverick.brain.logistic_regression import LogisticRegression, softmax


def test_ngrams_keep_word_order():
    assert ngrams(["what", "started", "chrome"]) == [
        "what", "started", "chrome", "<s>_what", "what_started", "started_chrome", "chrome_</s>"]
    assert "chrome_start" in ngrams(["what", "did", "chrome", "start"])
    assert "chrome_start" not in ngrams(["what", "started", "chrome"])


def test_tfidf_weighs_rare_words_more():
    docs = [["copy", "the", "file"], ["move", "the", "file"], ["rename", "the", "file"]]
    vec = TfidfVectorizer().fit(docs)
    row = vec.transform([["rename", "the", "file"]])[0]
    assert row[vec.index["rename"]] > row[vec.index["the"]]          # "the" is in every sentence
    assert np.isclose(np.linalg.norm(row), 1.0)                      # every sentence has length 1
    assert not vec.transform([["never", "seen"]]).any()              # unknown words are ignored


def test_softmax_is_a_probability_and_overflow_safe():
    probs = softmax(np.array([[1000.0, 1000.0, 999.0]]))
    assert np.isclose(probs.sum(), 1.0) and probs[0, 0] == probs[0, 1] > probs[0, 2]


def test_logistic_regression_learns_and_is_confident():
    examples = [("copy", ["copy", "a", "to", "b"]), ("copy", ["duplicate", "a"]), ("copy", ["copy", "this"]),
                ("move", ["move", "a", "to", "b"]), ("move", ["shift", "a"]), ("move", ["move", "this"])]
    model = LogisticRegression(epochs=200).fit(examples)
    assert model.predict(["copy", "x"])[0] == "copy"
    assert model.predict(["move", "x"])[0] == "move"
    label, confidence = model.predict(["duplicate", "x"])
    assert label == "copy" and confidence > 0.5


def test_word_pairs_tell_apart_same_words_different_order():
    examples = [("origin", ["what", "started", "x"])] * 5 + [("children", ["what", "did", "x", "start"])] * 5
    model = LogisticRegression(epochs=200).fit(examples)
    assert model.predict(["what", "started", "chrome"])[0] == "origin"
    assert model.predict(["what", "did", "chrome", "start"])[0] == "children"


def test_mlp_learns_and_tells_word_order_apart():
    from maverick.brain.mlp import MLP
    examples = ([("origin", ["what", "started", "x"])] * 8 + [("children", ["what", "did", "x", "start"])] * 8
                + [("copy", ["copy", "a", "to", "b"])] * 8)
    model = MLP(hidden=16, epochs=60, learning_rate=0.01).fit(examples)
    assert model.predict(["what", "started", "chrome"])[0] == "origin"
    assert model.predict(["what", "did", "chrome", "start"])[0] == "children"
    assert model.predict(["copy", "it", "to", "d"])[0] == "copy"


def test_mlp_backprop_matches_numeric_gradient():
    """The classic check: nudge one weight by a tiny amount and see the loss change as backprop predicted."""
    from maverick.brain.mlp import MLP
    rng = np.random.default_rng(1)
    model = MLP(hidden=4, dropout=0.0, l2=0.0)
    model.params = {"w1": rng.normal(size=(3, 4)), "b1": np.zeros(4), "w2": rng.normal(size=(4, 2)), "b2": np.zeros(2)}
    x, y = rng.normal(size=(5, 3)), np.eye(2)[[0, 1, 0, 1, 1]]

    def loss():
        probs, _ = model.forward(x)
        return -np.mean(np.log((probs * y).sum(axis=1)))
    probs, cache = model.forward(x)
    grads = model.backward(probs, y, cache)
    for name in ("w1", "w2"):
        eps = 1e-6
        model.params[name][0, 0] += eps
        up = loss()
        model.params[name][0, 0] -= 2 * eps
        down = loss()
        model.params[name][0, 0] += eps
        assert np.isclose(grads[name][0, 0], (up - down) / (2 * eps), atol=1e-6)
