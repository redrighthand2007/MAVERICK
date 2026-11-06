import random

from maverick.llm.lora import batches, encode, prompt


class FakeTokenizer:
    """One token per character, so lengths are easy to check without downloading the real tokenizer."""
    eos_token_id = 0

    def __call__(self, text, add_special_tokens=True):
        return type("Encoded", (), {"input_ids": [ord(c) for c in text]})()


def test_prompt_ends_where_the_answer_starts():
    assert prompt("how much ram") == "Request: how much ram\nAction:"


def test_only_the_answer_is_graded():
    ids, targets = encode(FakeTokenizer(), "hi", "hardware.ram")
    asked = len(prompt("hi"))
    assert len(ids) == len(targets) == asked + len(" hardware.ram") + 1
    assert targets[:asked] == [-100] * asked          # the request itself: not graded
    assert targets[asked:] == ids[asked:]             # the label (and the end token): graded
    assert ids[-1] == FakeTokenizer.eos_token_id      # the model learns to STOP after the label


def test_batches_cover_every_row_once():
    rows = list(range(10))
    got = list(batches(rows, 4, random.Random(1)))
    assert [len(b) for b in got] == [4, 4, 2]
    assert sorted(x for b in got for x in b) == rows
    assert rows == list(range(10))  # the caller's list isn't shuffled in place
