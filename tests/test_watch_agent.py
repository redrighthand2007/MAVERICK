from pathlib import Path

import pytest

from maverick.agents.watch import ops
from maverick.agents.watch.agent import WatchAgent, find_folders
from maverick.core.background import Background
from maverick.main import build

HOME = Path.home()


@pytest.mark.parametrize("sentence, source, destination, exts", [
    ("move every new pdf in downloads to documents", HOME / "Downloads", HOME / "Documents", ["pdf"]),
    ("move new videos in downloads to videos", HOME / "Downloads", HOME / "Videos",
     ["avi", "mkv", "mov", "mp4", "webm", "wmv"]),
    ("watch D:\\inbox for txt files and copy them to E:\\backup", "D:\\inbox", "E:\\backup", ["txt"]),
    ('monitor "D:\\my stuff" and copy new files to "E:\\safe place"', "D:\\my stuff", "E:\\safe place", []),
])
def test_find_folders(sentence, source, destination, exts):
    assert find_folders(sentence) == (str(source), str(destination), exts)


def test_copy_or_move_and_missing_details():
    agent = WatchAgent(Background())
    assert agent.parse("watch D:\\a and copy new files to E:\\b").args["action"] == "copy"
    assert agent.parse("move every new pdf in downloads to documents").args["action"] == "move"
    assert agent.parse("watch downloads").missing == ["where to put the files"]


@pytest.mark.parametrize("sentence", ["move notes.txt to documents", "stop watching downloads", "find new pdfs"])
def test_parse_leaves_other_requests_alone(sentence):
    assert WatchAgent(Background()).parse(sentence) is None


@pytest.fixture
def folders(tmp_path):
    (tmp_path / "in").mkdir()
    (tmp_path / "in" / "old.pdf").write_text("was here before")
    return tmp_path / "in", tmp_path / "out"


def tick_twice(job):
    """A file must look the same on two ticks before it moves (so half-downloaded files wait)."""
    return job.tick() + job.tick()


def test_only_new_matching_finished_files_move(folders):
    src, dest = folders
    job = ops.plan(str(src), str(dest), ["pdf"])
    (src / "new.pdf").write_text("new")
    (src / "photo.png").write_text("not a pdf")
    (src / "big.pdf.crdownload").write_text("still downloading")
    messages = tick_twice(job)
    assert messages == [f"moved new.pdf -> {dest / 'new.pdf'}"]
    assert (dest / "new.pdf").exists()
    assert (src / "old.pdf").exists()            # was there before watching started
    assert (src / "photo.png").exists() and (src / "big.pdf.crdownload").exists()


def test_never_overwrites(folders):
    src, dest = folders
    dest.mkdir()
    (dest / "a.pdf").write_text("keep me")
    job = ops.plan(str(src), str(dest), ["pdf"])
    (src / "a.pdf").write_text("new one")
    tick_twice(job)
    assert (dest / "a.pdf").read_text() == "keep me"
    assert (dest / "a (2).pdf").read_text() == "new one"


def test_copy_leaves_the_original(folders):
    src, dest = folders
    job = ops.plan(str(src), str(dest), [], action="copy")
    (src / "x.txt").write_text("x")
    tick_twice(job)
    assert (src / "x.txt").exists() and (dest / "x.txt").exists()


def test_start_asks_first_then_runs_in_background(folders):
    src, dest = folders
    background = Background(notify=lambda m: None)
    maverick = build(background=background)
    question = maverick.handle(f'watch "{src}" and move new pdf files to "{dest}"')
    assert question.data.get("confirm") and question.message.startswith("Start watching")
    started = maverick.confirm(True)
    assert started.success and len(background.list()) == 1
    assert "1. watching" in maverick.handle("show background jobs").message
    background.stop()


@pytest.mark.parametrize("dest_inside", [True, False])
def test_folders_inside_each_other_are_refused(folders, dest_inside):
    src, _ = folders
    with pytest.raises(ops.SafetyError):
        if dest_inside:
            ops.plan(str(src), str(src / "sub"), [])
        else:
            ops.plan(str(src), str(src.parent), [])


def test_watcher_survives_a_restart(folders, tmp_path):
    src, dest = folders
    path = tmp_path / "jobs.json"
    first = Background(path, notify=lambda m: None)
    first.add(ops.plan(str(src), str(dest), ["pdf"]))
    first.stop()
    second = Background(path, notify=lambda m: None)
    assert second.load() == 1
    assert second.list()[0].describe() == f"watching {src}: move every new .pdf file to {dest}"
    second.stop()
