import os
import time
from pathlib import Path

import pytest

from maverick.agents.cleanup import ops
from maverick.agents.cleanup.agent import CleanupAgent
from maverick.main import build


@pytest.mark.parametrize("sentence, intent", [
    ("free up space", ("scan", {"root": ""})),
    ("free up space on e drive", ("scan", {"root": "E:\\"})),
    ("what can i delete on d:", ("scan", {"root": "D:\\"})),
    ("clean up my disk", ("scan", {"root": ""})),
    ("clear temp files", ("recycle", {"target": "temp"})),
    ("delete notes.txt", ("recycle", {"target": "notes.txt"})),
    ('delete "D:\\my old\\x.zip"', ("recycle", {"target": "D:\\my old\\x.zip"})),
])
def test_parse_cleanup_requests(sentence, intent):
    got = CleanupAgent().parse(sentence)
    assert (got.operation, got.args) == intent


@pytest.mark.parametrize("sentence", [
    "empty the recycle bin",       # a permanent delete: MAVERICK never does that
    "how much free space on D:",   # hardware
    "copy notes.txt to D:\\x",
])
def test_parse_leaves_other_requests_alone(sentence):
    assert CleanupAgent().parse(sentence) is None


def test_delete_without_a_path_asks_for_it():
    assert CleanupAgent().parse("delete it").missing == ["what to delete"]


@pytest.fixture
def fake_bin(monkeypatch):
    """Records what would go to the Recycle Bin and removes it, so tests don't fill your real bin."""
    sent = []

    def fake(paths):
        for p in paths:
            sent.append(p)
            p.unlink()
    monkeypatch.setattr(ops, "send_to_recycle_bin", fake)
    return sent


def test_delete_asks_first_and_then_recycles(tmp_path, fake_bin):
    target = tmp_path / "old.zip"
    target.write_bytes(b"0" * 2048)
    maverick = build()
    question = maverick.handle(f'delete "{target}"')
    assert question.data.get("confirm")
    assert question.message == f"Send {target} (2.00 KB) to the Recycle Bin? You can restore it from there."
    assert maverick.confirm(True).success
    assert fake_bin == [target] and not target.exists()


def test_saying_no_keeps_the_file(tmp_path, fake_bin):
    target = tmp_path / "keep.txt"
    target.write_text("x")
    maverick = build()
    maverick.handle(f'delete "{target}"')
    maverick.confirm(False)
    assert target.exists() and fake_bin == []


@pytest.mark.parametrize("target", [str(Path.home()), str(Path.home() / "Documents"),
                                    os.environ.get("SystemRoot", r"C:\Windows"), "C:\\"])
def test_important_folders_are_never_deleted(target):
    result = build().handle(f'delete "{target}"')
    assert result.message.startswith("Blocked for safety"), result.message


def test_temp_cleanup_only_takes_old_items(tmp_path, monkeypatch):
    monkeypatch.setattr(ops, "temp_dir", lambda: tmp_path)
    old, new = tmp_path / "old.tmp", tmp_path / "new.tmp"
    old.write_text("x")
    new.write_text("x")
    week_ago = time.time() - 7 * 86400
    os.utime(old, (week_ago, week_ago))
    assert ops.old_temp_items() == [old]


def test_scan_finds_big_files_and_old_downloads(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(ops, "temp_dir", lambda: tmp_path / "Temp")
    monkeypatch.setattr(ops, "BIG_FILE", 1000)
    (tmp_path / "Temp").mkdir()
    (tmp_path / "Downloads").mkdir()
    big = tmp_path / "movie.mkv"
    big.write_bytes(b"0" * 5000)
    forgotten = tmp_path / "Downloads" / "setup.exe"
    forgotten.write_bytes(b"0" * 10)
    long_ago = time.time() - 200 * 86400
    os.utime(forgotten, (long_ago, long_ago))

    result = ops.scan()
    assert result.data["big"] == [str(big)]
    assert result.data["old_downloads"] == [str(forgotten)]


def test_only_deleting_asks_for_confirmation():
    assert CleanupAgent.risky == {"recycle"}
