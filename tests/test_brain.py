import pytest

from maverick.brain import Brain
from maverick.brain.dataset import HARD_CASES_PATH, INTENTS_PATH, load_examples, split
from maverick.brain.evaluate import accuracy, grade
from maverick.brain.naive_bayes import NaiveBayes
from maverick.brain.text import tokenize
from maverick.brain.train import train
from maverick.main import build

# Raise these as the dataset grows; never lower them silently.
MIN_TEST_ACCURACY = 0.80
MIN_HARD_ACCURACY = 0.75


@pytest.fixture(scope="module")
def trained():
    train_set, test_set = split(load_examples(INTENTS_PATH))
    return train(train_set), test_set


@pytest.fixture(scope="module")
def full_brain():
    return Brain(train(load_examples(INTENTS_PATH)))  # no log_path: tests never write inbox.tsv


class FakeBrain:
    def __init__(self, label, confidence):
        self.answer = (label, confidence)

    def predict(self, text):
        return self.answer


def test_tokenize_replaces_paths():
    assert tokenize(r'Copy notes.txt to "D:\My Stuff"!') == ["copy", "<path>", "to", "<path>"]
    assert tokenize("what's the size of D:\\games?") == ["whats", "the", "size", "of", "<path>"]


def test_dataset_has_enough_examples_per_label():
    labels = [label for label, _ in load_examples(INTENTS_PATH)]
    for label in set(labels):
        assert labels.count(label) >= 30, label


def test_split_is_stratified_and_repeatable():
    examples = load_examples(INTENTS_PATH)
    train_set, test_set = split(examples)
    assert len(train_set) + len(test_set) == len(examples)
    assert {l for l, _ in test_set} == {l for l, _ in examples}
    assert split(examples) == (train_set, test_set)


def test_accuracy_floor_on_unseen_sentences(trained):
    model, test_set = trained
    results = grade(lambda s: model.predict(tokenize(s)), test_set)
    assert accuracy(results) >= MIN_TEST_ACCURACY


def test_accuracy_floor_on_hard_cases(trained):
    model, _ = trained
    results = grade(lambda s: model.predict(tokenize(s)), load_examples(HARD_CASES_PATH))
    assert accuracy(results) >= MIN_HARD_ACCURACY


@pytest.mark.parametrize("sentence, label", [
    ("rename a.txt to b.txt", "files.rename"),
    ("make a duplicate of notes.txt in D:\\backup", "files.copy"),
    ("how much space does D:\\games take up", "files.size"),
    ("transfer D:\\music to E:\\music", "files.move"),
    ("tell me a joke", "unknown"),
])
def test_must_pass_sentences(full_brain, sentence, label):
    assert full_brain.predict(sentence)[0] == label


def test_model_save_and_load_round_trip(tmp_path, trained):
    model, _ = trained
    model.save(tmp_path / "m.json")
    loaded = NaiveBayes.load(tmp_path / "m.json")
    tokens = tokenize("copy notes.txt to D:\\x")
    assert loaded.predict(tokens) == model.predict(tokens)


def test_missing_model_means_no_brain(tmp_path):
    assert Brain.load(tmp_path / "nope.json") is None


def test_brain_logs_requests(tmp_path, trained):
    model, _ = trained
    log = tmp_path / "inbox.tsv"
    Brain(model, log).predict("size of notes.txt")
    assert log.read_text(encoding="utf-8").startswith("files.size\t")


def test_confident_brain_works_without_keywords(tmp_path):
    src = tmp_path / "notes.txt"
    src.write_text("hi")
    result = build(FakeBrain("files.copy", 0.95)).handle(f'make another one of "{src}" in "{tmp_path / "b.txt"}"')
    assert result.success, result.message
    assert (tmp_path / "b.txt").read_text() == "hi"


def test_unsure_brain_falls_back_to_keyword_rules(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("x")
    result = build(FakeBrain("files.move", 0.3)).handle(f'rename "{src}" to b.txt')
    assert result.success, result.message
    assert (tmp_path / "b.txt").exists()


def test_unsure_brain_and_no_keywords_asks_to_rephrase():
    result = build(FakeBrain("files.size", 0.55)).handle("how chunky is my stuff")
    assert not result.success
    assert "files.size" in result.message


def test_weak_guess_is_not_suggested():
    result = build(FakeBrain("files.copy", 0.34)).handle("delete everything on my drive")
    assert not result.success
    assert "files.copy" not in result.message


def test_confident_unknown_is_rejected():
    result = build(FakeBrain("unknown", 0.99)).handle("tell me a joke")
    assert not result.success
    assert "No MAVERICK agent" in result.message


def test_real_brain_end_to_end(tmp_path, full_brain):
    src = tmp_path / "notes.txt"
    src.write_text("hi")
    (tmp_path / "backup").mkdir()
    result = build(full_brain).handle(f'make a duplicate of "{src}" in "{tmp_path / "backup"}"')
    assert result.success, result.message
    assert (tmp_path / "backup" / "notes.txt").exists()
