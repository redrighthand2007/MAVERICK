import os
import time
from datetime import datetime
from pathlib import Path

import pytest

from maverick.agents.search import ops
from maverick.agents.search.agent import SearchAgent
from maverick.agents.search.filters import BIG_DEFAULT, parse_query
from maverick.main import build

NOW = datetime(2026, 10, 31, 12, 0)  # a Saturday
MB = 1024 ** 2


@pytest.mark.parametrize("sentence, expected", [
    ("find dune 1 movie in e drive", {"root": "E:\\", "name": "dune 1", "exts": ["avi", "mkv", "mov", "mp4", "webm", "wmv"]}),
    ("where is notes.txt", {"name": "notes.txt"}),
    ("find *.py in E:\\MAVERICK", {"root": "E:\\MAVERICK", "exts": ["py"]}),
    ("find big files on d drive", {"root": "D:\\", "min_size": BIG_DEFAULT}),
    ("find documents smaller than 2 mb", {"max_size": 2 * MB, "exts": ["csv", "doc", "docx", "md", "pdf", "ppt", "pptx", "txt", "xls", "xlsx"]}),
    ('search for files containing "api key" in E:\\x', {"contains": "api key", "root": "E:\\x"}),
    ("find the word maverick in my desktop", {"contains": "maverick", "root": str(Path.home() / "Desktop")}),
])
def test_parse_query(sentence, expected):
    assert parse_query(sentence, NOW) == expected


def test_parse_dates():
    midnight = datetime(2026, 10, 31).timestamp()
    assert parse_query("files edited today", NOW) == {"after": midnight}
    assert parse_query("photos from yesterday", NOW)["before"] == midnight
    assert parse_query("files i changed this week", NOW)["after"] == datetime(2026, 10, 26).timestamp()
    assert parse_query("files modified in the last 3 days", NOW)["after"] == datetime(2026, 10, 28, 12).timestamp()
    assert "before" in parse_query("find files older than 2 years", NOW)


@pytest.mark.parametrize("sentence, operation", [
    ("find dune movie in e drive", "find"),
    ("where is notes.txt", "find"),
    ("find files containing password", "content"),
])
def test_parse_search_questions(sentence, operation):
    assert SearchAgent().parse(sentence).operation == operation


@pytest.mark.parametrize("sentence", [
    "find size of D:\\games",          # files agent
    "find notes.txt and copy it to D:\\",
    "how much ram do i have",
])
def test_parse_leaves_other_requests_alone(sentence):
    assert SearchAgent().parse(sentence) is None


def test_search_needs_something_to_look_for():
    assert SearchAgent().parse("find").missing == ["what to look for"]


@pytest.fixture
def tree(tmp_path):
    (tmp_path / "movies").mkdir()
    (tmp_path / "movies" / "Dune-2021.mkv").write_bytes(b"0" * 3000)
    (tmp_path / "movies" / "Topgun.mkv").write_bytes(b"0" * 100)
    (tmp_path / "notes.txt").write_text("my wifi password is hunter2\n", encoding="utf-8")
    (tmp_path / "todo.md").write_text("nothing secret here\n", encoding="utf-8")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "dune-lib.mkv").write_bytes(b"0")  # inside a skipped folder
    old = time.time() - 10 * 86400
    os.utime(tmp_path / "todo.md", (old, old))
    return tmp_path


def test_find_by_name_and_kind(tree):
    result = ops.find(str(tree), name="dune", exts=["mkv"])
    assert result.data["files"] == [str(tree / "movies" / "Dune-2021.mkv")]


def test_find_by_size_biggest_first(tree):
    result = ops.find(str(tree), min_size=50)
    assert result.data["files"][0].endswith("Dune-2021.mkv")


def test_find_by_date(tree):
    result = ops.find(str(tree), after=time.time() - 86400)
    assert str(tree / "todo.md") not in result.data["files"]
    assert str(tree / "notes.txt") in result.data["files"]


def test_find_inside_text_shows_the_line(tree):
    result = ops.find(str(tree), contains="PASSWORD")
    assert result.data["files"] == [str(tree / "notes.txt")]
    assert '"my wifi password is hunter2"' in result.message


def test_nothing_found(tree):
    result = ops.find(str(tree), name="no-such-thing")
    assert result.success and result.data["count"] == 0


def test_end_to_end_through_maverick(tree):
    result = build().handle(f'find files containing "hunter2" in "{tree}"')
    assert result.success and result.data["count"] == 1


def test_search_never_asks_for_confirmation():
    assert SearchAgent.risky == set()
