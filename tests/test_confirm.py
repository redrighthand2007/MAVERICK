import builtins

from maverick.main import ask_if_needed, build


def make_file(tmp_path, name="a.txt"):
    path = tmp_path / name
    path.write_text("x")
    return path


def test_move_asks_first_and_changes_nothing(tmp_path):
    src = make_file(tmp_path)
    result = build().handle(f'move "{src}" to "{tmp_path / "b.txt"}"')
    assert result.data == {"confirm": True}
    assert result.message == f"Move {src} -> {tmp_path / 'b.txt'}?"
    assert src.exists()


def test_rename_question_shows_new_name(tmp_path):
    src = make_file(tmp_path)
    result = build().handle(f'rename "{src}" to b.txt')
    assert result.data == {"confirm": True}
    assert result.message == f"Rename {src} -> b.txt?"


def test_yes_runs_the_action(tmp_path):
    src = make_file(tmp_path)
    maverick = build()
    maverick.handle(f'rename "{src}" to b.txt')
    assert maverick.confirm(True).success
    assert (tmp_path / "b.txt").exists() and not src.exists()


def test_no_cancels(tmp_path):
    src = make_file(tmp_path)
    maverick = build()
    maverick.handle(f'move "{src}" to "{tmp_path / "b.txt"}"')
    result = maverick.confirm(False)
    assert not result.success
    assert "Cancelled" in result.message
    assert src.exists() and not (tmp_path / "b.txt").exists()


def test_each_question_is_answered_only_once(tmp_path):
    src = make_file(tmp_path)
    maverick = build()
    maverick.handle(f'rename "{src}" to b.txt')
    maverick.confirm(True)
    assert maverick.confirm(True).message == "Nothing is waiting for confirmation."


def test_new_request_drops_unanswered_question(tmp_path):
    src = make_file(tmp_path)
    maverick = build()
    maverick.handle(f'rename "{src}" to b.txt')
    maverick.handle(f'size of "{src}"')
    assert maverick.confirm(True).message == "Nothing is waiting for confirmation."
    assert src.exists()


def test_blocked_action_is_never_asked(tmp_path):
    a, b = make_file(tmp_path, "a.txt"), make_file(tmp_path, "b.txt")
    result = build().handle(f'rename "{a}" to b.txt')
    assert "confirm" not in result.data
    assert result.message.startswith("Blocked for safety")


def test_safe_operations_run_without_asking(tmp_path):
    src = make_file(tmp_path)
    maverick = build()
    assert maverick.handle(f'copy "{src}" to "{tmp_path / "c.txt"}"').success
    assert maverick.handle(f'size of "{src}"').success
    assert maverick.pending is None


def test_file_changed_between_question_and_answer(tmp_path):
    src = make_file(tmp_path)
    maverick = build()
    maverick.handle(f'rename "{src}" to b.txt')
    make_file(tmp_path, "b.txt")  # appears while the user is thinking
    result = maverick.confirm(True)
    assert result.message.startswith("Blocked for safety")
    assert (tmp_path / "b.txt").read_text() == "x" and src.exists()


def test_cli_prompt_yes_and_anything_else(tmp_path, monkeypatch):
    src = make_file(tmp_path)
    maverick = build()

    monkeypatch.setattr(builtins, "input", lambda prompt: "nope")
    result = ask_if_needed(maverick, maverick.handle(f'rename "{src}" to b.txt'))
    assert "Cancelled" in result.message and src.exists()

    monkeypatch.setattr(builtins, "input", lambda prompt: " YES ")
    result = ask_if_needed(maverick, maverick.handle(f'rename "{src}" to b.txt'))
    assert result.success and (tmp_path / "b.txt").exists()


def test_cli_prompt_without_keyboard_cancels(tmp_path, monkeypatch):
    src = make_file(tmp_path)
    maverick = build()

    def no_input(prompt):
        raise EOFError

    monkeypatch.setattr(builtins, "input", no_input)
    result = ask_if_needed(maverick, maverick.handle(f'rename "{src}" to b.txt'))
    assert "Cancelled" in result.message and src.exists()
