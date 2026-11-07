import numpy as np
import pytest

from maverick.brain import DEFAULT_KIND, MODELS
from maverick.brain.bernoulli_nb import BernoulliNB
from maverick.brain.classic import DecisionTree, KNearest, LinearSVM
from maverick.brain.embeddings import MeaningLR, SynonymSwap, similar
from maverick.brain.ensemble import Ensemble
from maverick.brain.logistic_regression import LogisticRegression

TOY = [("files.copy", ["copy", "<path>", "to", "<path>"]), ("files.copy", ["copy", "this", "file"]),
       ("files.copy", ["please", "copy", "<path>"]), ("process.end", ["kill", "chrome"]),
       ("process.end", ["kill", "the", "app"]), ("process.end", ["please", "kill", "notepad"]),
       ("hardware.ram", ["how", "much", "ram"]), ("hardware.ram", ["ram", "size"]),
       ("hardware.ram", ["show", "my", "ram"])]


@pytest.mark.parametrize("cls", [LinearSVM, KNearest, DecisionTree, BernoulliNB, Ensemble])
def test_each_new_model_learns_the_toy_data(cls):
    model = cls().fit(TOY)
    assert model.predict(["copy", "<path>"])[0] == "files.copy"
    assert model.predict(["kill", "firefox"])[0] == "process.end"
    assert model.predict(["ram", "please"])[0] == "hardware.ram"
    probs = model.predict_proba(["kill", "chrome"])
    assert abs(sum(probs.values()) - 1) < 1e-6


def test_knn_votes_follow_the_nearest_sentences():
    model = KNearest(k=3).fit(TOY)
    label, share = model.predict(["kill", "chrome"])
    assert label == "process.end" and share > 0.5


def test_tree_asks_yes_no_questions():
    tree = DecisionTree().fit(TOY).tree
    assert "feature" in tree and {"yes", "no"} <= tree.keys()


def test_bernoulli_counts_missing_words():
    # Same present words, but one label usually also has "file": its absence counts against that label.
    data = [("a", ["copy", "file"])] * 5 + [("b", ["copy"])] * 5
    model = BernoulliNB().fit(data)
    assert model.predict(["copy"])[0] == "b"
    assert model.predict(["copy", "file"])[0] == "a"


def test_big_smoothing_hands_everything_to_the_biggest_label():
    # The 8.4 bug: with +1 smoothing, a label with many sentences pays least for absent words.
    vocab_filler = [f"w{i}" for i in range(200)]
    data = [("big", [w]) for w in vocab_filler] + [("small", ["kill", "chrome"])] * 3
    assert BernoulliNB(alpha=0.1).fit(data).predict(["kill", "chrome"])[0] == "small"


def test_ensemble_averages_its_members():
    model = Ensemble(("logistic_regression", "bernoulli_nb")).fit(TOY)
    tokens = ["kill", "chrome"]
    expected = {label: (model.members[0].predict_proba(tokens)[label] + model.members[1].predict_proba(tokens)[label]) / 2
                for label in model.members[0].predict_proba(tokens)}
    assert all(abs(model.predict_proba(tokens)[k] - v) < 1e-9 for k, v in expected.items())


def test_ensemble_saves_its_members_next_to_it(tmp_path):
    model = Ensemble().fit(TOY)
    model.save(tmp_path / "brain.json")
    assert (tmp_path / "brain.logistic_regression.json").exists()
    loaded = Ensemble.load(tmp_path / "brain.json")
    (label, confidence), (saved_label, saved_confidence) = model.predict(["kill", "chrome"]), loaded.predict(["kill", "chrome"])
    assert saved_label == label
    assert abs(saved_confidence - confidence) < 1e-6  # weights are saved rounded to 6 decimals


def test_the_default_brain_is_minilm_or_the_ensemble():
    from maverick.brain.minilm import MiniLM
    assert DEFAULT_KIND == ("minilm" if MiniLM.usable() else "ensemble")
    assert set(Ensemble.MEMBERS) <= MODELS.keys()


FAKE_GLOVE = {w: v / np.linalg.norm(v) for w, v in {
    "copy": np.array([1.0, 0.1, 0.0]), "duplicate": np.array([0.95, 0.15, 0.0]),
    "kill": np.array([0.0, 1.0, 0.1]), "banana": np.array([0.0, 0.0, 1.0])}.items()}


def test_similar_words():
    assert similar(FAKE_GLOVE, "duplicate", sorted(FAKE_GLOVE), n=1)[0][0] == "copy"


def test_unknown_word_swap():
    model = LogisticRegression().fit(TOY)
    swap = SynonymSwap(model, FAKE_GLOVE, {w for _, t in TOY for w in t})
    assert swap.translate(["duplicate", "<path>"]) == ["copy", "<path>"]
    assert swap.translate(["banana"]) == ["banana"]  # nothing similar enough among the known words
    assert swap.predict(["duplicate", "<path>"])[0] == "files.copy"


def test_meaning_features_add_the_average_vector():
    glove = {w: np.ones(50) for w in ["copy", "kill"]}
    model = MeaningLR(glove).fit(TOY)
    x = model.features([["copy", "unknown"]])
    assert x.shape[1] == len(model.vectorizer.index) + 50
