import pytest

from maverick.brain.dataset import INTENTS_PATH, load_examples
from maverick.brain.multi import (Splitter, candidates, cross_validate, load_marked, naive_cuts, parse_marked, tidy,
                                  train_brain)
from maverick.brain.slots import tokens_of
from maverick.core.orchestrator import fill_in
from maverick.main import build

# History: words only 88.9% / 80.5%; with the brain's view of each side (stacking) 97.5% / 86.4%.
MIN_MULTI_CUT = 0.9
MIN_SINGLE_KEPT = 0.8


class SplitAtAnd:
    """A stand-in splitter, so the orchestrator tests don't depend on what the real one learned."""
    def split(self, text):
        return [piece.strip() for piece in text.split(" and ")]


@pytest.fixture(scope="module")
def splitter():
    intents = load_examples(INTENTS_PATH)
    return Splitter(train_brain(intents)).fit(load_marked() + [(tokens_of(s), set()) for _, s in intents])


def test_candidates_are_connectors_and_commas():
    tokens = tokens_of("show my ip, then turn off wifi and also restart it")
    assert [tokens[i] for i in candidates(tokens)] == ["then", "and", "also"]
    assert candidates(tokens_of("show my ip, close chrome")) == [3]


def test_parse_marked_reads_the_cuts():
    tokens, cuts = parse_marked(r"copy a.txt to D:\x | and zip it")
    assert tokens == ["copy", "a.txt", "to", r"D:\x", "and", "zip", "it"]
    assert cuts == {4}


def test_tidy_drops_connectors_and_commas():
    assert tidy(["and", "then", "zip", "it"]) == "zip it"
    assert tidy(["show", "my", "ip,"]) == "show my ip"


def test_cutting_at_every_and_breaks_one_action_sentences():
    tokens = tokens_of(r"cut and paste a.txt into D:\x")
    assert naive_cuts(tokens) == {1}  # why the splitter has to be learned


def test_splitter_cuts_multi_action_sentences(splitter):
    assert splitter.split(r"copy notes.txt to D:\backup and zip it") == [r"copy notes.txt to D:\backup", "zip it"]
    assert splitter.split("show my ip, then turn off wifi") == ["show my ip", "turn off wifi"]


def test_splitter_keeps_one_action_sentences_whole(splitter):
    for sentence in [r"cut and paste a.txt into D:\x", "check battery health and charge", "close chrome and firefox"]:
        assert splitter.split(sentence) == [sentence]


def test_splitter_on_unseen_sentences():
    multi_cut, single_kept = cross_validate()
    assert multi_cut >= MIN_MULTI_CUT
    assert single_kept >= MIN_SINGLE_KEPT


def test_fill_in_replaces_the_first_it_with_the_previous_output():
    assert fill_in("zip it", r"C:\Users\x\notes.txt") == r'zip "C:\Users\x\notes.txt"'
    assert fill_in("move them to D:\\y", r"D:\a") == r'move "D:\a" to D:\y'


def test_fill_in_leaves_text_alone_without_an_output():
    assert fill_in("zip it", None) == "zip it"


def test_fill_in_skips_its():
    assert fill_in("it's big, zip it", "D:\\a") == 'it\'s big, zip "D:\\a"'


def test_steps_run_in_order_and_it_means_the_last_result(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "backup").mkdir()
    maverick = build(splitter=SplitAtAnd())
    result = maverick.handle(f'copy "{tmp_path / "notes.txt"}" to "{tmp_path / "backup"}" and zip it')
    assert result.success, result.message
    assert (tmp_path / "backup" / "notes.zip").exists()
    assert result.message.startswith("Copied") and "Created" in result.message


def test_a_failed_step_stops_the_rest(tmp_path):
    result = build(splitter=SplitAtAnd()).handle(f'copy "{tmp_path / "missing.txt"}" to "{tmp_path}" and zip it')
    assert not result.success
    assert "Stopped there, so I did not: zip it" in result.message
    assert not list(tmp_path.glob("*.zip"))


def test_a_question_pauses_the_chain_until_answered(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "old").mkdir()
    maverick = build(splitter=SplitAtAnd())
    question = maverick.handle(f'move "{tmp_path / "notes.txt"}" to "{tmp_path / "old"}" and how big is it')
    assert question.data.get("confirm")
    result = maverick.confirm(True)
    assert result.success, result.message
    assert "Moved" in result.message and "2 B" in result.message


def test_saying_no_cancels_the_remaining_steps(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    maverick = build(splitter=SplitAtAnd())
    maverick.handle(f'move "{tmp_path / "notes.txt"}" to "{tmp_path / "old"}" and how big is it')
    result = maverick.confirm(False)
    assert "Cancelled" in result.message and "did not: how big is it" in result.message
    assert (tmp_path / "notes.txt").exists()


def test_a_piece_nobody_understands_means_one_request():
    result = build(splitter=SplitAtAnd()).handle("how much ram do i have and banana bread")
    assert "Stopped" not in result.message and "No MAVERICK agent" not in result.message
