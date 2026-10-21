from maverick.agents.files.agent import FileAgent
from maverick.main import build


def test_parse_copy_with_to():
    intent = FileAgent().parse(r"copy notes.txt to D:\backup")
    assert intent.operation == "copy"
    assert intent.args == {"source": "notes.txt", "destination": r"D:\backup"}


def test_parse_quoted_paths_with_spaces():
    intent = FileAgent().parse(r'move "C:\My Docs\a b.txt" into "E:\New Folder"')
    assert intent.operation == "move"
    assert intent.args == {"source": r"C:\My Docs\a b.txt", "destination": r"E:\New Folder"}


def test_parse_size_question():
    intent = FileAgent().parse(r"how big is D:\Games?")
    assert intent.operation == "size"
    assert intent.args == {"path": r"D:\Games"}


def test_parse_missing_destination():
    intent = FileAgent().parse("copy notes.txt")
    assert intent.missing == ["destination"]


def test_unrelated_request_is_not_claimed():
    assert FileAgent().parse("open chrome") is None
    assert build().handle("open chrome").success is False


def test_copy_file_into_folder(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("hello")
    (tmp_path / "out").mkdir()
    result = build().handle(f'copy "{src}" to "{tmp_path / "out"}"')
    assert result.success, result.message
    assert (tmp_path / "out" / "a.txt").read_text() == "hello"
    assert src.exists()


def test_move_folder(tmp_path):
    folder = tmp_path / "data"
    folder.mkdir()
    (folder / "x.txt").write_text("x")
    result = build().handle(f'move "{folder}" to "{tmp_path / "moved"}"')
    assert result.success, result.message
    assert not folder.exists()
    assert (tmp_path / "moved" / "x.txt").exists()


def test_never_overwrites(tmp_path):
    (tmp_path / "a.txt").write_text("new")
    (tmp_path / "b.txt").write_text("keep me")
    result = build().handle(f'copy "{tmp_path / "a.txt"}" to "{tmp_path / "b.txt"}"')
    assert not result.success
    assert (tmp_path / "b.txt").read_text() == "keep me"


def test_folder_cannot_go_inside_itself(tmp_path):
    folder = tmp_path / "data"
    folder.mkdir()
    result = build().handle(f'copy "{folder}" to "{folder / "inner"}"')
    assert not result.success
    assert "inside itself" in result.message


def test_protected_folder_blocked(tmp_path):
    src = tmp_path / "a.txt"
    src.write_text("x")
    result = build().handle(rf'copy "{src}" to C:\Windows')
    assert not result.success
    assert "protected" in result.message


def test_size_of_folder(tmp_path):
    (tmp_path / "a.bin").write_bytes(b"0" * 1000)
    (tmp_path / "b.bin").write_bytes(b"0" * 24)
    result = build().handle(f'size of "{tmp_path}"')
    assert result.success
    assert result.data == {"bytes": 1024, "files": 2, "skipped": 0}
    assert "1.00 KB" in result.message
