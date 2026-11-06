"""LLM tool calling (Stage 8.18).

The local LLM gets a menu of MAVERICK's actions ("tools") and must answer with ONE of them as JSON:
  "pls back up notes.txt onto D:\\safe"  ->  {"action": "files.copy", "args": {"source": "notes.txt", "destination": "D:\\safe"}}

The LLM only SUGGESTS. Before anything runs, check() makes sure that:
  1. the answer is JSON with an action that is on the menu (a made-up action is ignored),
  2. only that action's arguments are kept, and every one is a string,
  3. every value really appears in what the user typed. A small model sometimes invents
     a path that "sounds right"; an invented value is dropped, so MAVERICK asks for it instead.
After that it's a normal Intent: the agent's own safety checks and y/n questions still run.

The orchestrator only asks the LLM when the brain and the keyword rules both failed,
because the LLM is the slowest of the three (about a second per request on the RTX 2050).

Not every action is on the menu yet: these are the ones whose arguments are simple text.
"""
import json
import re
from dataclasses import dataclass, field

from maverick.core.agent_base import Intent
from maverick.llm.ollama import LLMError


@dataclass(frozen=True)
class Tool:
    description: str
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    defaults: dict = field(default_factory=dict)  # arguments the agent needs that the LLM is never asked for


TOOLS = {
    "files.copy": Tool("copy a file or folder into another folder", ("source", "destination")),
    "files.move": Tool("move a file or folder into another folder", ("source", "destination")),
    "files.rename": Tool("give a file or folder a new name", ("source", "new_name")),
    "files.size": Tool("how big a file or folder is", ("path",)),
    "archive.create": Tool("make a zip of a file or folder", ("source",), ("output",),
                           {"output": "", "fmt": "zip", "encrypt": False}),
    "archive.list": Tool("show what is inside a zip file", ("archive",)),
    "archive.extract": Tool("unzip a zip file", ("archive",), ("destination",), {"destination": ""}),
    "hardware.ram": Tool("how much RAM (memory) the PC has and uses"),
    "hardware.cpu": Tool("which processor (CPU) the PC has"),
    "hardware.battery": Tool("battery level and whether it is charging"),
    "hardware.disks": Tool("free space on the drives", optional=("drive",)),
    "hardware.forecast": Tool("when a drive will be full at the current rate", optional=("drive",)),
    "network.info": Tool("IP address and network adapters"),
    "accounts.admins": Tool("which user accounts are administrators"),
    "jobs.list": Tool("list MAVERICK's background jobs"),
    "process.unusual": Tool("programs behaving unlike all the others (odd, suspicious)", defaults={"seconds": 6}),
}
NONE = "none"


def signature(name: str, tool: Tool) -> str:
    """'files.copy(source, destination)' or 'hardware.disks(drive?)'"""
    return f"{name}({', '.join([*tool.required, *(a + '?' for a in tool.optional)])})"


SYSTEM_PROMPT = "\n".join([
    "You turn one request for a Windows PC into ONE action, written as JSON.",
    "Actions (? = optional):",
    *(f"- {signature(name, tool)}: {tool.description}" for name, tool in TOOLS.items()),
    "",
    'Answer with JSON only, like {"action": "files.copy", "args": {"source": "a.txt", "destination": "D:\\\\x"}}.',
    "Copy file names, folders and drives exactly as the user wrote them. Never invent a value:",
    "if the user did not give an argument, leave it out.",
    f'If no action fits, answer {{"action": "{NONE}", "args": {{}}}}.',
])


def call_json(action: str, **args) -> str:
    return json.dumps({"action": action, "args": args})


# Few-shot (8.19): worked examples shown to the model as if it had already answered them.
# A small model copies the PATTERN of examples far more reliably than it follows written rules,
# so each one teaches a rule: copy paths exactly, leave out what wasn't given, "none" for off-menu requests.
# Kept different from llm_eval.tsv, or the test would just measure memory.
EXAMPLES = [
    (r"duplicate a.txt into D:\x", call_json("files.copy", source="a.txt", destination=r"D:\x")),
    ("make a backup of notes.txt", call_json("files.copy", source="notes.txt")),
    (r"how big is my D:\music folder", call_json("files.size", path=r"D:\music")),
    (r"zip up D:\docs", call_json("archive.create", source=r"D:\docs")),
    ("space left on C", call_json("hardware.disks", drive="C")),
    ("what processor do i have", call_json("hardware.cpu")),
    ("close notepad", call_json(NONE)),
    ("tell me a joke", call_json(NONE)),
]


def first_json_object(answer: str) -> dict | None:
    """The first {...} in the answer, even if the model wrapped it in ```json fences or chatted around it."""
    start = answer.find("{")
    if start < 0:
        return None
    try:
        value, _ = json.JSONDecoder().raw_decode(answer[start:])
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def bare(value: str) -> str:
    return value.strip().strip('"').strip("'").lower()


def grounded(value: str, text: str) -> bool:
    """Did the user actually type this, as whole words? 'D:' counts as typed when the user wrote 'D'.

    Whole words matter: the "c" inside "much" is not the user asking about drive C.
    """
    value, text = bare(value), text.lower()
    if not value:
        return False
    if re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text):
        return True
    return value.rstrip(":\\/") in re.findall(r"\b[a-z]\b", text)


def check(answer: str, text: str) -> tuple[str, Intent] | None:
    """The LLM's raw answer -> (agent name, Intent), or None if it is not a usable action."""
    call = first_json_object(answer)
    if call is None:
        return None
    name, args = call.get("action"), call.get("args") or {}
    if name not in TOOLS or not isinstance(args, dict):
        return None  # "none", or an action that doesn't exist
    tool = TOOLS[name]
    kept = {}
    for arg in (*tool.required, *tool.optional):
        value = args.get(arg)
        if isinstance(value, str) and grounded(value, text):
            kept[arg] = value.strip()
    if "drive" in kept:
        kept["drive"] = kept["drive"].rstrip(":\\/").upper() + ":"
    missing = [arg for arg in tool.required if arg not in kept]
    agent, operation = name.split(".", 1)
    full = {**tool.defaults, **{arg: "" for arg in tool.required}, **kept}
    return agent, Intent(operation, full, missing)


class ToolCaller:
    """Asks the LLM which action a request is; anything wrong with the answer means "no idea"."""

    def __init__(self, llm, examples: list[tuple[str, str]] = EXAMPLES):
        self.llm = llm  # anything with ask(question, system=..., json_only=..., examples=...) -> str
        self.examples = examples

    def call(self, text: str) -> tuple[str, Intent] | None:
        try:
            answer = self.llm.ask(text, system=SYSTEM_PROMPT, json_only=True, examples=self.examples)
        except LLMError:
            return None  # Ollama stopped or the model is missing: MAVERICK just works without it
        return check(answer, text)

    def solve(self, text: str, run):
        """One request, one action. run(agent name, intent) -> Result is the orchestrator's (safety checks included)."""
        call = self.call(text)
        return run(*call) if call else None
