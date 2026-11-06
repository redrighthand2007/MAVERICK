import json

from maverick.llm.ollama import LLMError
from maverick.llm.evaluate import judge, load_cases
from maverick.llm.tools import EXAMPLES, SYSTEM_PROMPT, TOOLS, ToolCaller, check, first_json_object
from maverick.main import build


class FakeLLM:
    """Answers with a fixed string, so the tests check OUR code, not what the real model happens to say."""
    def __init__(self, answer: str | Exception):
        self.answer = answer
        self.calls = []

    def ask(self, question, system=None, json_only=False, examples=()):
        self.calls.append({"question": question, "system": system, "json_only": json_only, "examples": examples})
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


def answer(action: str, **args) -> str:
    return json.dumps({"action": action, "args": args})


def test_the_menu_lists_every_tool():
    for name in TOOLS:
        assert f"- {name}(" in SYSTEM_PROMPT
    assert "hardware.disks(drive?)" in SYSTEM_PROMPT


def test_first_json_object_survives_fences_and_chat():
    assert first_json_object('Sure! ```json\n{"action": "none", "args": {}}\n``` hope that helps') == \
        {"action": "none", "args": {}}
    assert first_json_object("no json here") is None
    assert first_json_object("{broken") is None


def test_check_turns_a_good_answer_into_an_intent():
    text = r"pls back up notes.txt onto E:\x"
    agent, intent = check(answer("files.copy", source="notes.txt", destination=r"E:\x"), text)
    assert agent == "files"
    assert intent.operation == "copy"
    assert intent.args == {"source": "notes.txt", "destination": r"E:\x"}
    assert intent.missing == []


def test_made_up_actions_and_none_are_ignored():
    assert check(answer("files.delete_everything", path="C:"), "wipe C:") is None
    assert check(answer("none"), "banana bread") is None
    assert check("not json at all", "banana bread") is None


def test_an_invented_value_is_dropped_and_asked_for():
    _, intent = check(answer("files.copy", source="notes.txt", destination=r"D:\Backups"), "back up notes.txt")
    assert intent.args["destination"] == ""
    assert intent.missing == ["destination"]


def test_unknown_arguments_and_non_text_values_are_dropped():
    _, intent = check(answer("files.size", path="notes.txt", force="yes"), "how heavy is notes.txt")
    assert intent.args == {"path": "notes.txt"}
    _, intent = check(json.dumps({"action": "files.size", "args": {"path": 42}}), "how heavy is 42")
    assert intent.missing == ["path"]


def test_defaults_fill_what_the_llm_is_never_asked_for():
    _, intent = check(answer("archive.create", source="photos"), "squash photos down")
    assert intent.args == {"source": "photos", "output": "", "fmt": "zip", "encrypt": False}


def test_a_drive_letter_is_tidied():
    _, intent = check(answer("hardware.disks", drive="d"), "room left on d")
    assert intent.args == {"drive": "D:"}


def test_a_letter_inside_a_word_is_not_a_drive():
    # Found by `python -m maverick.llm.evaluate`: the "c" in "much" let the model's guess "C" through.
    _, intent = check(answer("hardware.disks", drive="C"), "how much storage do i have left")
    assert intent.args == {}
    _, intent = check(answer("files.size", path="note"), "how big is notes.txt")
    assert intent.missing == ["path"]


def test_the_caller_asks_for_json_with_the_menu():
    llm = FakeLLM(answer("hardware.ram"))
    assert ToolCaller(llm).call("memory?")[0] == "hardware"
    assert llm.calls[0]["system"] == SYSTEM_PROMPT and llm.calls[0]["json_only"]


def test_the_caller_sends_the_few_shot_examples():
    llm = FakeLLM(answer("hardware.ram"))
    ToolCaller(llm).call("memory?")
    assert llm.calls[0]["examples"] == EXAMPLES
    ToolCaller(llm, examples=[]).call("memory?")
    assert llm.calls[1]["examples"] == []


def test_every_example_answer_passes_its_own_check():
    """An example that check() would cut down would teach the model the wrong thing."""
    for question, example in EXAMPLES:
        expected = json.loads(example)
        assert judge(expected["action"], expected["args"], check(example, question)) == (True, True), question


def test_examples_are_not_in_the_test_set():
    sentences = {sentence.lower() for _, sentence, _ in load_cases()}
    assert not sentences & {question.lower() for question, _ in EXAMPLES}


def test_eval_cases_parse_and_name_real_actions():
    cases = load_cases()
    assert ("files.copy", r"clone budget.xlsx over to D:\work", {"source": "budget.xlsx", "destination": r"D:\work"}) \
        in cases
    for action, sentence, args in cases:
        assert action == "none" or action in TOOLS
        assert "[" not in sentence


def test_judge_counts_dropped_inventions_as_right():
    text = "put a backup of thesis.docx somewhere safe"
    got = check(answer("files.copy", source="thesis.docx", destination=r"D:\safe"), text)  # destination invented
    assert judge("files.copy", {"source": "thesis.docx"}, got) == (True, True)
    assert judge("files.move", {"source": "thesis.docx"}, got) == (False, False)
    assert judge("none", {}, None) == (True, True)


def test_the_caller_gives_up_quietly_when_ollama_is_down():
    assert ToolCaller(FakeLLM(LLMError("not running"))).call("memory?") is None


def test_maverick_uses_the_llm_when_nothing_else_understands(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "safe").mkdir()
    source, dest = tmp_path / "notes.txt", tmp_path / "safe"
    llm = FakeLLM(answer("files.copy", source=f'"{source}"', destination=f'"{dest}"'))
    result = build(tool_caller=ToolCaller(llm)).handle(f'pls back up "{source}" onto "{dest}"')
    assert result.success, result.message
    assert (dest / "notes.txt").exists()


def test_the_llm_is_not_asked_when_the_rules_already_understand():
    llm = FakeLLM(answer("none"))
    build(tool_caller=ToolCaller(llm)).handle("how much ram do i have")
    assert llm.calls == []


def test_a_risky_llm_action_still_asks_first(tmp_path):
    (tmp_path / "notes.txt").write_text("hi")
    (tmp_path / "old").mkdir()
    source, dest = tmp_path / "notes.txt", tmp_path / "old"
    llm = FakeLLM(answer("files.move", source=f'"{source}"', destination=f'"{dest}"'))
    maverick = build(tool_caller=ToolCaller(llm))
    question = maverick.handle(f'stash "{source}" over in "{dest}"')
    assert question.data.get("confirm")
    assert source.exists()  # nothing moved until the user says yes
    assert maverick.confirm(False).message.startswith("Cancelled")
    assert source.exists()


def test_without_the_llm_unknown_requests_still_get_the_old_answer():
    llm = FakeLLM(answer("none"))
    result = build(tool_caller=ToolCaller(llm)).handle("banana bread")
    assert "No MAVERICK agent" in result.message
