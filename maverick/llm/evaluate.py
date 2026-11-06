"""Which prompt makes the local LLM pick the right action? (Stage 8.19)

Prompts are tuned like any other model setting: by measuring, on sentences the model never saw.
  zero-shot: only the menu and the rules (what 8.18 used)
  few-shot:  the same, plus a handful of worked examples (tools.EXAMPLES)

Scores on data/llm_eval.tsv:
  action right:       the chosen action ("none" included)
  fully right:        the action AND exactly the expected arguments, after check() dropped invented ones
Arguments are judged AFTER check(), because that's what MAVERICK actually runs.

Run:  python -m maverick.llm.evaluate     (needs Ollama running; about 3 s per sentence per prompt)
"""
import re
import time

from maverick.brain.dataset import DATA_DIR, load_examples
from maverick.llm.ollama import Ollama
from maverick.llm.tools import EXAMPLES, NONE, TOOLS, ToolCaller, bare

EVAL_PATH = DATA_DIR / "llm_eval.tsv"
SLOT_RE = re.compile(r"\[(\w+) ([^\]]+)\]")


def parse_case(line: str) -> tuple[str, dict]:
    """'copy [source a.txt] to [destination D:\\x]' -> ('copy a.txt to D:\\x', {'source': 'a.txt', ...})"""
    return SLOT_RE.sub(lambda m: m.group(2), line), dict(SLOT_RE.findall(line))


def load_cases() -> list[tuple[str, str, dict]]:
    return [(action, *parse_case(line)) for action, line in load_examples(EVAL_PATH)]


def same(value: str) -> str:
    """'D:' and 'd', '"E:\\x"' and 'E:\\x' count as the same value."""
    return bare(value).rstrip(":\\/")


def judge(action: str, args: dict, got) -> tuple[bool, bool]:
    """(action right, fully right) for one ToolCaller.call() result."""
    got_action, got_args = NONE, {}
    if got is not None:
        agent, intent = got
        got_action = f"{agent}.{intent.operation}"
        tool = TOOLS[got_action]
        got_args = {k: v for k, v in intent.args.items() if k in (*tool.required, *tool.optional) and v}
    action_right = got_action == action
    args_right = {k: same(v) for k, v in got_args.items()} == {k: same(v) for k, v in args.items()}
    return action_right, action_right and args_right


def score(caller: ToolCaller, cases) -> tuple[float, float, float, list[str]]:
    """(action accuracy, full accuracy, seconds per sentence, the mistakes)"""
    actions = full = 0
    mistakes = []
    start = time.time()
    for action, sentence, args in cases:
        got = caller.call(sentence)
        action_right, fully_right = judge(action, args, got)
        actions += action_right
        full += fully_right
        if not fully_right:
            shown = "none" if got is None else f"{got[0]}.{got[1].operation} {got[1].args}"
            mistakes.append(f"{sentence!r}: wanted {action} {args}, got {shown}")
    return actions / len(cases), full / len(cases), (time.time() - start) / len(cases), mistakes


def main() -> None:
    llm = Ollama()
    if not llm.available():
        raise SystemExit(f"Ollama isn't running or {llm.model} isn't downloaded. Run: ollama pull {llm.model}")
    cases = load_cases()
    llm.ask("hi")  # load the model first, so its loading time isn't counted against the first prompt
    print(f"{len(cases)} sentences the model never saw ({llm.model}):")
    for name, examples in [("zero-shot", []), (f"few-shot ({len(EXAMPLES)} examples)", EXAMPLES)]:
        actions, full, seconds, mistakes = score(ToolCaller(llm, examples), cases)
        print(f"\n  {name:24} action right {actions:.1%}, fully right {full:.1%}, {seconds:.1f} s per sentence")
        for mistake in mistakes:
            print(f"    - {mistake}")


if __name__ == "__main__":
    main()
