import gzip

import pytest

from maverick.agents.logs import ops
from maverick.agents.logs.agent import LogsAgent
from maverick.core.background import Background
from maverick.main import build

MB = 1024 ** 2


@pytest.mark.parametrize("sentence, args", [
    ("rotate D:\\app\\server.log", {"path": "D:\\app\\server.log", "max_size": 0}),
    ("rotate server.log when it gets bigger than 50 mb", {"path": "server.log", "max_size": 50 * MB}),
    ('truncate "D:\\my app\\debug.log"', {"path": "D:\\my app\\debug.log", "max_size": 0}),
    ("empty the log app.log", {"path": "app.log", "max_size": 0}),
])
def test_parse_rotate_requests(sentence, args):
    assert LogsAgent(Background()).parse(sentence).args == args


@pytest.mark.parametrize("sentence", ["compress D:\\logs as tar.gz", "clear temp files", "show background jobs"])
def test_parse_leaves_other_requests_alone(sentence):
    assert LogsAgent(Background()).parse(sentence) is None


def test_stop_rotating_goes_to_the_jobs_agent():
    assert build().handle("stop rotating app.log").message.startswith("No background job")


@pytest.fixture
def log(tmp_path):
    path = tmp_path / "server.log"
    path.write_bytes(b"line\n" * 1000)  # bytes: Windows text mode would turn \n into \r\n
    return path


def test_rotate_asks_first_then_saves_and_empties(log):
    maverick = build()
    question = maverick.handle(f'rotate "{log}"')
    assert question.data.get("confirm") and question.message.startswith(f"Rotate {log}")
    result = maverick.confirm(True)
    assert result.success, result.message
    assert log.read_text() == ""
    archive = next(log.parent.glob("server-*.log.gz"))
    assert gzip.decompress(archive.read_bytes()) == b"line\n" * 1000


def test_saying_no_keeps_the_log(log):
    maverick = build()
    maverick.handle(f'rotate "{log}"')
    maverick.confirm(False)
    assert log.stat().st_size == 5000 and not list(log.parent.glob("*.gz"))


def test_two_rotations_in_the_same_second_both_survive(log):
    ops.rotate(str(log))
    log.write_text("more")
    ops.rotate(str(log))
    assert len(list(log.parent.glob("server-*.log.gz"))) == 2


def test_writer_can_keep_writing_after_rotation(log):
    with open(log, "a") as writer:  # like a running program holding its log open
        ops.rotate(str(log))
        writer.write("after\n")
    assert log.read_text().endswith("after\n")


def test_background_job_rotates_only_when_too_big(log):
    job = ops.RotateJob(str(log), max_size=10_000)
    assert job.tick() == []                # 5000 bytes: still small
    log.write_text("x" * 20_000)
    assert job.tick()[0].startswith("rotated server.log")
    assert log.stat().st_size == 0


def test_size_limit_starts_a_background_job(log):
    background = Background(notify=lambda m: None)
    maverick = build(background=background)
    question = maverick.handle(f'rotate "{log}" when it gets bigger than 50 mb')
    assert question.message.startswith("Start a background job")
    assert maverick.confirm(True).success
    assert background.list()[0].describe() == f"rotating {log} when bigger than 50.00 MB"
    assert log.stat().st_size == 5000      # nothing rotated yet
    background.stop()


def test_folders_are_refused(tmp_path):
    assert build().handle(f'rotate "{tmp_path}"').message.startswith("Blocked for safety")
