import json

from maverick.llm.loop import DONE, LOOP_PROMPT, AgentLoop
from maverick.llm.ollama import LLMError
from maverick.llm.tools import call_json
from maverick.main import build


class ScriptedLLM:
    """Gives its answers in order, one per ask(), and remembers what it was asked."""
    def __init__(self, *answers):
        self.answers = list(answers)
        self.calls = []

    def ask(self, question, system=None, json_only=False, examples=()):
        self.calls.append({"question": question, "system": system, "examples": list(examples)})
        if not self.answers:
            raise AssertionError("asked more often than the script allows")
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer


def done(answer=""):
    return json.dumps({"action": DONE, "answer": answer})


def files(tmp_path, *names):
    paths = []
    for name in names:
        (tmp_path / name).write_text("hello")
        paths.append(tmp_path / name)
    return paths


def test_two_steps_then_done(tmp_path):
    (notes,) = files(tmp_path, "notes.txt")
    llm = ScriptedLLM(call_json("files.size", path=f'"{notes}"'), call_json("archive.create", source=f'"{notes}"'),
                      done("notes.txt is tiny; I zipped it."))
    result = build(tool_caller=AgentLoop(llm)).handle(f'sort out "{notes}" for me')
    assert result.success, result.message
    assert (tmp_path / "notes.zip").exists()
    lines = result.message.splitlines()
    assert lines[0].startswith(str(notes)) and lines[1].startswith("Created") and lines[-1] == "notes.txt is tiny; I zipped it."
    # The model sees each result as the next message, with its earlier answers kept in the conversation.
    assert llm.calls[1]["question"].startswith("Result: ")
    assert llm.calls[2]["examples"][-1] == (llm.calls[1]["question"], call_json("archive.create", source=f'"{notes}"'))
    assert llm.calls[0]["system"] == LOOP_PROMPT


def test_a_value_from_a_result_counts_as_seen(tmp_path):
    (notes,) = files(tmp_path, "notes.txt")
    zipped = tmp_path / "notes.zip"
    llm = ScriptedLLM(call_json("archive.create", source=f'"{notes}"'), call_json("files.size", path=str(zipped)),
                      done())
    result = build(tool_caller=AgentLoop(llm)).handle(f'sort out "{notes}" for me')
    assert result.success, result.message
    assert result.message.splitlines()[1].startswith(str(zipped))  # the zip's path was only in the first result


def test_an_invented_value_stops_the_loop_with_a_question(tmp_path):
    (notes,) = files(tmp_path, "notes.txt")
    llm = ScriptedLLM(call_json("files.size", path=f'"{notes}"'), call_json("files.copy", source=f'"{notes}"',
                                                                             destination=r"D:\made\up"))
    result = build(tool_caller=AgentLoop(llm)).handle(f'check "{notes}" and back it up')
    assert not result.success
    assert result.message.endswith("I need: destination")


def test_a_risky_step_goes_to_the_user_and_ends_the_loop(tmp_path):
    notes, old = files(tmp_path, "notes.txt", "old.txt")
    (tmp_path / "keep").mkdir()
    llm = ScriptedLLM(call_json("files.size", path=f'"{notes}"'),
                      call_json("files.move", source=f'"{notes}"', destination=f'"{tmp_path / "keep"}"'))
    maverick = build(tool_caller=AgentLoop(llm))
    question = maverick.handle(f'sort out "{notes}" with "{tmp_path / "keep"}"')
    assert question.data.get("confirm") and question.message.splitlines()[-1].startswith("Move")
    assert notes.exists() and llm.answers == []  # nothing moved yet, and the model wasn't asked again
    assert maverick.confirm(True).success
    assert (tmp_path / "keep" / "notes.txt").exists()


def test_a_failed_step_ends_the_loop(tmp_path):
    missing = tmp_path / "missing.txt"
    llm = ScriptedLLM(call_json("files.size", path=f'"{missing}"'), done("never asked"))
    result = build(tool_caller=AgentLoop(llm)).handle(f'weigh "{missing}" please')
    assert not result.success and len(llm.calls) == 1


def test_the_same_action_twice_ends_the_loop(tmp_path):
    (notes,) = files(tmp_path, "notes.txt")
    again = call_json("files.size", path=f'"{notes}"')
    llm = ScriptedLLM(again, again)
    result = build(tool_caller=AgentLoop(llm)).handle(f'weigh "{notes}" please')
    assert result.success and len(result.message.splitlines()) == 1


def test_at_most_max_steps(tmp_path):
    paths = files(tmp_path, "a.txt", "b.txt", "c.txt")
    llm = ScriptedLLM(*(call_json("files.size", path=f'"{p}"') for p in paths))
    text = "weigh " + " ".join(f'"{p}"' for p in paths)
    result = build(tool_caller=AgentLoop(llm, max_steps=2)).handle(text)
    assert len(result.message.splitlines()) == 2 and len(llm.answers) == 1


def test_no_usable_first_action_means_the_old_answer():
    llm = ScriptedLLM(call_json("none"))
    assert "No MAVERICK agent" in build(tool_caller=AgentLoop(llm)).handle("banana bread").message


def test_ollama_dying_mid_loop_keeps_what_was_done(tmp_path):
    (notes,) = files(tmp_path, "notes.txt")
    llm = ScriptedLLM(call_json("files.size", path=f'"{notes}"'), LLMError("gone"))
    result = build(tool_caller=AgentLoop(llm)).handle(f'weigh "{notes}" please')
    assert result.success and result.message.startswith(str(notes))
