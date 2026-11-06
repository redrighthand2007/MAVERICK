"""The LLM agent loop (Stage 8.21): think -> act -> look at the result -> repeat.

8.18 let the LLM pick ONE action. Some requests need the answer of one step to choose the next:
  "how big is notes.txt, and zip it if it's over 1 MB"
  "which is bigger, D:\\a or D:\\b?"
So the conversation with the model keeps going:

  user:      how big is notes.txt and zip it
  model:     {"action": "files.size", "args": {"path": "notes.txt"}}
  MAVERICK:  runs it  ->  "Result: notes.txt: 3.0 MB"
  model:     {"action": "archive.create", "args": {"source": "notes.txt"}}
  MAVERICK:  runs it  ->  "Result: Created notes.zip ..."
  model:     {"action": "done", "answer": "notes.txt was 3 MB, so I zipped it."}

This is the core of every "AI agent": a model in a loop with tools. The safety rules stay with MAVERICK:
  - every action goes through tools.check() and the orchestrator's run() (safety checks, y/n questions)
  - a risky action ends the loop: its y/n question goes to the user, the model never answers it
  - a failed step ends the loop, like the 8.16 chain
  - at most MAX_STEPS actions, and the same action twice ends it (a small model can go round in circles)
Values may now come from the request OR from an earlier result: "zip the biggest one" can only
name a file that a result actually showed.
"""
import json

from maverick.core.agent_base import Result
from maverick.llm.ollama import LLMError
from maverick.llm.tools import EXAMPLES, SYSTEM_PROMPT, call_json, check, first_json_object

MAX_STEPS = 4
DONE = "done"

LOOP_PROMPT = SYSTEM_PROMPT + "\n" + "\n".join([
    "",
    "After each action you get its Result. Then answer with the next action the request still needs,",
    f'or, when nothing is left to do: {{"action": "{DONE}", "answer": "<one short sentence for the user>"}}.',
    "Never repeat an action. Only use values from the request or from a Result.",
])

# Few-shot conversations that END: a model only shown single answers never learns to say "done".
LOOP_EXAMPLES = [
    (r"how big is a.txt, then zip it", call_json("files.size", path="a.txt")),
    (r"Result: a.txt: 3.0 KB", call_json("archive.create", source="a.txt")),
    (r"Result: Created C:\a.zip (1 files, 3.0 KB -> 1.2 KB).",
     json.dumps({"action": DONE, "answer": r"a.txt is 3 KB; I zipped it to C:\a.zip."})),
    ("what processor do i have", call_json("hardware.cpu")),
    ("Result: CPU: Intel Core i5-1135G7, 4 cores / 8 threads",
     json.dumps({"action": DONE, "answer": "You have an Intel Core i5-1135G7 with 4 cores."})),
]


def result_line(result: Result) -> str:
    # The reminder matters: without it the 3B model sized two files and then sized one of them again,
    # instead of answering "which is bigger".
    return ("Result: " + result.message.replace("\n", " | ")
            + f'\n(If the request is now answered, reply {{"action": "{DONE}", "answer": ...}}.)')


class AgentLoop:
    def __init__(self, llm, examples=EXAMPLES + LOOP_EXAMPLES, max_steps: int = MAX_STEPS):
        self.llm = llm  # anything with ask(question, system=..., json_only=..., examples=...) -> str
        self.examples = examples
        self.max_steps = max_steps

    def solve(self, text: str, run) -> Result | None:
        """run(agent name, intent) -> Result is the orchestrator's. None = the model had no usable first action."""
        turns: list[tuple[str, str]] = []  # (what MAVERICK said, what the model answered), oldest first
        said, seen, done, answer = text, text, [], ""
        tried = set()
        while len(done) < self.max_steps:
            try:
                reply = self.llm.ask(said, system=LOOP_PROMPT, json_only=True, examples=self.examples + turns)
            except LLMError:
                break
            parsed = first_json_object(reply) or {}
            if parsed.get("action") == DONE:
                answer = str(parsed.get("answer") or "").strip()
                break
            call = check(reply, seen)  # values must come from the request or an earlier result
            key = None if call is None else (call[0], call[1].operation, json.dumps(call[1].args, sort_keys=True))
            if call is None or key in tried:
                break
            tried.add(key)
            result = run(*call)
            if result is None:
                break
            done.append(result)
            if not result.success or result.data.get("confirm"):
                break  # a failure stops here; a y/n question goes to the user, never to the model
            turns.append((said, reply))
            said = result_line(result)
            seen += "\n" + said
        if not done:
            return None
        last = done[-1]
        lines = [r.message for r in done]
        if answer and last.success:
            lines.append(answer)
        return Result(last.success, "\n".join(lines), last.data)
