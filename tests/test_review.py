from maverick.brain.review import review, to_review

KNOWN = ["files.copy", "hardware.battery", "unknown"]


def write_inbox(tmp_path):
    inbox = tmp_path / "inbox.tsv"
    inbox.write_text("unknown\t0.20\thi\n"
                     "hardware.battery\t0.90\twhats my battery stat ?\n"
                     "files.size\t0.35\tcan u copy dune 1 movie to d drive\n"
                     "unknown\t0.20\thi\n", encoding="utf-8")   # duplicate is shown once
    return inbox


def test_least_confident_first_and_no_duplicates(tmp_path):
    pending = to_review(write_inbox(tmp_path), tmp_path / "learned.tsv")
    assert [s for _, _, s in pending] == ["hi", "can u copy dune 1 movie to d drive", "whats my battery stat ?"]


def test_accept_correct_skip_and_retry_a_typo(tmp_path):
    inbox, learned = write_inbox(tmp_path), tmp_path / "learned.tsv"
    before = inbox.read_text(encoding="utf-8")
    answers = iter(["s", "copy", "files.copy", ""])   # skip "hi"; "copy" is not a label -> retry; accept battery
    saved = review(lambda prompt: next(answers), inbox, learned, KNOWN)
    assert saved == 2
    assert learned.read_text(encoding="utf-8") == ("files.copy\tcan u copy dune 1 movie to d drive\n"
                                                    "hardware.battery\twhats my battery stat ?\n")
    assert inbox.read_text(encoding="utf-8") == before  # inbox.tsv is never changed
    # Next time only the skipped one is left.
    assert [s for _, _, s in to_review(inbox, learned)] == ["hi"]


def test_quit_stops_early(tmp_path):
    inbox, learned = write_inbox(tmp_path), tmp_path / "learned.tsv"
    assert review(lambda prompt: "q", inbox, learned, KNOWN) == 0
    assert not learned.exists()
