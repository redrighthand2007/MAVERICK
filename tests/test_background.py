import time

import pytest

from maverick.agents.jobs.agent import JobsAgent
from maverick.core.background import Background, Job
from maverick.main import build


class CountJob(Job):
    kind = "count"
    interval = 10

    def __init__(self, label="downloads"):
        super().__init__()
        self.label, self.ticks = label, 0

    def describe(self):
        return f"count things in {self.label}"

    def tick(self):
        self.ticks += 1
        return [f"tick {self.ticks}"]

    def to_dict(self):
        return {"label": self.label}


Background.register("count", lambda saved: CountJob(saved["label"]))


@pytest.fixture
def background():
    messages = []
    bg = Background(notify=messages.append)
    bg.messages = messages
    yield bg
    bg.stop()


def test_jobs_run_on_their_interval(background):
    job = CountJob()
    background.add(job)
    background.stop()  # drive it by hand instead of the 1-second thread
    background.run_due(now=1000)
    background.run_due(now=1005)   # too soon: interval is 10 s
    background.run_due(now=1010)
    assert job.ticks == 2
    assert background.messages == ["[job 1] tick 1", "[job 1] tick 2"]


def test_a_broken_job_does_not_stop_the_others(background):
    class Broken(CountJob):
        def tick(self):
            raise RuntimeError("disk unplugged")
    good = CountJob()
    background.add(Broken())
    background.add(good)
    background.stop()
    background.run_due(now=1000)
    assert good.ticks == 1
    assert "[job 1] job 1 hit a problem: disk unplugged" in background.messages


def test_the_thread_really_runs_jobs(background):
    job = CountJob()
    job.interval = 0
    background.add(job)
    deadline = time.time() + 5
    while job.ticks == 0 and time.time() < deadline:
        time.sleep(0.1)
    assert job.ticks >= 1


def test_jobs_are_saved_and_restored(tmp_path):
    path = tmp_path / "jobs.json"
    first = Background(path, notify=lambda m: None)
    first.add(CountJob("documents"))
    first.stop()
    second = Background(path, notify=lambda m: None)
    assert second.load() == 1
    assert second.list()[0].describe() == "count things in documents"
    second.stop()


@pytest.mark.parametrize("sentence, operation, args", [
    ("show background jobs", "list", {}),
    ("stop job 2", "stop", {"which": "2"}),
    ("stop watching downloads", "stop", {"which": "downloads"}),
    ("cancel all background jobs", "stop", {"which": "all"}),
])
def test_parse_jobs_requests(sentence, operation, args):
    intent = JobsAgent(Background()).parse(sentence)
    assert (intent.operation, intent.args) == (operation, args)


@pytest.mark.parametrize("sentence", ["watch downloads for pdfs", "kill chrome", "delete notes.txt"])
def test_parse_leaves_other_requests_alone(sentence):
    assert JobsAgent(Background()).parse(sentence) is None


def test_list_and_stop_through_maverick(background):
    background.add(CountJob("downloads"))
    background.add(CountJob("desktop"))
    maverick = build(background=background)
    assert "2. count things in desktop" in maverick.handle("show background jobs").message
    stopped = maverick.handle("stop watching downloads")
    assert stopped.success and stopped.data["stopped"] == [1]
    assert [job.id for job in background.list()] == [2]
    assert not maverick.handle("stop job 9").success


def test_stop_job_is_not_mistaken_for_ending_a_program():
    assert build().handle("stop job 1").message.startswith("No background job")
