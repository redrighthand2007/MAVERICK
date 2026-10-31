import pytest

from maverick.agents.files.agent import SLOTS, FileAgent
from maverick.brain.dataset import folds, load_examples
from maverick.brain.slots import (OUTSIDE, SLOTS_DATA_PATH, SlotTagger, allowed_after, load_tagged, parse_tagged,
                                  score, spans)
from maverick.main import build

# History: the first tagger (160 sentences) scored 92.5% vs the regex's 82.5%; 200 sentences: 93.0% vs 79.0%.
MIN_TAGGER_ACCURACY = 0.88


@pytest.fixture(scope="module")
def tagger():
    return SlotTagger().fit(load_tagged())


def test_parse_tagged_gives_bio_tags():
    tokens, tags = parse_tagged(r'copy [source "C:\My Docs\a.txt"] to the [destination usb drive]')
    assert tokens == ["copy", r'"C:\My Docs\a.txt"', "to", "the", "usb", "drive"]
    assert tags == [OUTSIDE, "B-source", OUTSIDE, OUTSIDE, "B-destination", "I-destination"]


def test_spans_turns_tags_back_into_values():
    tokens, tags = parse_tagged(r'copy [source "C:\My Docs\a.txt"] to the [destination usb drive]')
    assert spans(tokens, tags) == {"source": r"C:\My Docs\a.txt", "destination": "usb drive"}


def test_every_sentence_in_the_data_has_known_slots():
    for label, tokens, tags in load_tagged():
        assert set(spans(tokens, tags)) <= set(SLOTS[label.split(".")[1]]), " ".join(tokens)


def test_an_inside_tag_must_continue_its_own_slot():
    assert allowed_after("B-source", "I-source")
    assert allowed_after("I-source", "I-source")
    assert not allowed_after(OUTSIDE, "I-source")
    assert not allowed_after("B-destination", "I-source")


def test_viterbi_never_outputs_a_broken_sequence(tagger):
    for label, tokens, _ in load_tagged():
        tags = tagger.tag(label, tokens)
        assert all(allowed_after(prev, tag) for prev, tag in zip([OUTSIDE, *tags], tags))


def test_operation_limits_the_slots(tagger):
    assert set(tagger.fill("files.rename", r"rename notes.txt to D:\x", SLOTS["rename"])) <= {"source", "new_name"}


def test_finds_plain_word_names_it_never_saw(tagger):
    agent = FileAgent(tagger)
    assert agent.extract("move", r"shift my receipts folder into D:\taxes").args == {
        "source": "receipts", "destination": r"D:\taxes"}
    assert agent.extract("rename", "rename recipes to cooking").args == {"source": "recipes", "new_name": "cooking"}
    assert agent.extract("size", "how big is my receipts folder").args == {"path": "receipts"}


def test_missing_arguments_are_reported(tagger):
    intent = FileAgent(tagger).extract("rename", "rename it")
    assert intent.missing == ["source", "new_name"]


def test_tagger_beats_the_regex_on_unseen_sentences():
    regex = FileAgent()
    tagger_total = regex_total = 0.0
    for train, test in folds(load_examples(SLOTS_DATA_PATH)):
        model = SlotTagger().fit([(label, *parse_tagged(s)) for label, s in train])
        tagged = [(label, *parse_tagged(s)) for label, s in test]
        tagger_total += score(lambda label, tokens: spans(tokens, model.tag(label, tokens, SLOTS[label[6:]])),
                              tagged)[0] / 5
        regex_total += score(lambda label, tokens: {k: v for k, v in regex.extract(
            label[6:], " ".join(tokens)).args.items() if v}, tagged)[0] / 5
    assert tagger_total >= MIN_TAGGER_ACCURACY
    assert tagger_total > regex_total


def test_save_and_load_give_the_same_answers(tagger, tmp_path):
    tagger.save(tmp_path / "slots.json")
    loaded = SlotTagger.load(tmp_path / "slots.json")
    for label, tokens, _ in load_tagged()[:40]:
        assert loaded.tag(label, tokens) == tagger.tag(label, tokens)


def test_load_returns_none_before_training(tmp_path):
    assert SlotTagger.load(tmp_path / "nope.json") is None


def test_maverick_copies_using_the_tagger(tagger, tmp_path):
    (tmp_path / "notes").mkdir()
    (tmp_path / "notes" / "a.txt").write_text("hi")
    result = build(tagger=tagger).handle(f'please copy my "{tmp_path / "notes"}" folder to "{tmp_path / "backup"}"')
    assert result.success, result.message
    assert (tmp_path / "backup" / "a.txt").read_text() == "hi"
