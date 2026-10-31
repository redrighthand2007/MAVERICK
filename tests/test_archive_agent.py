import tarfile
import zipfile

import pytest

from maverick.agents.archive import ops
from maverick.agents.archive.agent import ArchiveAgent
from maverick.agents.search.agent import SearchAgent
from maverick.main import build


@pytest.mark.parametrize("sentence, operation, args", [
    ("zip the folder D:\\work", "create", {"source": "D:\\work", "output": "", "fmt": "zip", "encrypt": False}),
    ("zip D:\\work with a password", "create", {"source": "D:\\work", "output": "", "fmt": "zip", "encrypt": True}),
    ("compress D:\\logs as tar.gz", "create", {"source": "D:\\logs", "output": "", "fmt": "tar.gz", "encrypt": False}),
    ("zip D:\\work into E:\\backups", "create", {"source": "D:\\work", "output": "E:\\backups", "fmt": "zip", "encrypt": False}),
    ("what's inside backup.zip", "list", {"archive": "backup.zip"}),
    ("unzip backup.zip to D:\\restore", "extract", {"archive": "backup.zip", "destination": "D:\\restore"}),
])
def test_parse_archive_requests(sentence, operation, args):
    intent = ArchiveAgent().parse(sentence)
    assert (intent.operation, intent.args) == (operation, args)


@pytest.mark.parametrize("sentence", [
    "move notes.txt to D:\\archive",   # "archive" inside a path is not the word archive
    "what's in D:\\movies",            # a folder, not an archive
    "copy notes.txt to D:\\x",
])
def test_parse_leaves_other_requests_alone(sentence):
    assert ArchiveAgent().parse(sentence) is None


def test_find_zip_files_stays_a_search():
    # Both agents understand it, so the registration order in main.build() decides: search comes first.
    assert SearchAgent().parse("find zip files") is not None
    names = [a.name for a in build().agents]
    assert names.index("search") < names.index("archive")


@pytest.fixture
def work(tmp_path):
    (tmp_path / "work" / "sub").mkdir(parents=True)
    (tmp_path / "work" / "a.txt").write_text("hello " * 100)
    (tmp_path / "work" / "sub" / "b.txt").write_text("world")
    return tmp_path


@pytest.mark.parametrize("fmt, name", [("zip", "work.zip"), ("tar", "work.tar"), ("tar.gz", "work.tar.gz")])
def test_create_list_extract_round_trip(work, fmt, name):
    result = ops.create(str(work / "work"), fmt=fmt)
    assert result.success and (work / name).exists()
    assert sorted(ops.list_contents(str(work / name)).data["files"]) == ["work/a.txt", "work/sub/b.txt"]
    ops.extract(str(work / name), str(work / "out"))
    assert (work / "out" / "work" / "sub" / "b.txt").read_text() == "world"


def test_password_zip_through_maverick(work, monkeypatch):
    typed = iter(["s3cret", "s3cret", "s3cret"])
    monkeypatch.setattr(ArchiveAgent, "ask_password", staticmethod(lambda prompt: next(typed)))
    maverick = build()
    created = maverick.handle(f'zip "{work / "work"}" with a password')
    assert created.success and "AES-256" in created.message, created.message
    assert ops.is_encrypted(work / "work.zip")
    with zipfile.ZipFile(work / "work.zip") as zf:  # plain zipfile can't read AES without the password
        with pytest.raises(Exception):
            zf.read("work/a.txt")
    extracted = maverick.handle(f'unzip "{work / "work.zip"}" to "{work / "out"}"')
    assert extracted.success, extracted.message
    assert (work / "out" / "work" / "a.txt").exists()


def test_wrong_password_writes_nothing(work):
    ops.create(str(work / "work"), str(work / "locked.zip"), password="right")
    with pytest.raises(ops.SafetyError, match="wrong password"):
        ops.extract(str(work / "locked.zip"), str(work / "out"), password="wrong")
    assert not (work / "out").exists()


def test_mismatched_passwords_create_nothing(work, monkeypatch):
    typed = iter(["one", "two"])
    monkeypatch.setattr(ArchiveAgent, "ask_password", staticmethod(lambda prompt: next(typed)))
    result = build().handle(f'zip "{work / "work"}" with a password')
    assert not result.success and not (work / "work.zip").exists()


def test_zip_slip_is_blocked(tmp_path):
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("../../escaped.txt", "gotcha")
    result = build().handle(f'unzip "{evil}" to "{tmp_path / "out"}"')
    assert result.message.startswith("Blocked for safety") and "escape" in result.message
    assert not (tmp_path / "escaped.txt").exists() and not (tmp_path / "out").exists()


def test_tar_links_are_refused(tmp_path):
    evil = tmp_path / "evil.tar"
    with tarfile.open(evil, "w") as tf:
        link = tarfile.TarInfo("sneaky")
        link.type, link.linkname = tarfile.SYMTYPE, "C:\\Windows\\System32"
        tf.addfile(link)
    with pytest.raises(Exception):
        ops.extract(str(evil), str(tmp_path / "out"))


def test_never_overwrites(work):
    ops.create(str(work / "work"))
    result = build().handle(f'zip "{work / "work"}"')
    assert "never overwrites" in result.message
    ops.extract(str(work / "work.zip"), str(work / "out"))
    again = build().handle(f'unzip "{work / "work.zip"}" to "{work / "out"}"')
    assert "never overwrites" in again.message


def test_archive_cannot_go_inside_its_own_folder(work):
    result = build().handle(f'zip "{work / "work"}" into "{work / "work"}"')
    assert result.message.startswith("Blocked for safety")
