import sys
from pathlib import Path

# Lets `python maverick/main.py` work from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maverick.agents.files.agent import FileAgent
from maverick.agents.hardware.agent import HardwareAgent
from maverick.brain import Brain
from maverick.core.agent_base import Result
from maverick.core.orchestrator import Orchestrator


def build(brain: Brain | None = None) -> Orchestrator:
    # Register sub-agents here. Order matters for keyword rules: the first agent that understands a request wins.
    # Hardware goes first so "space left on D:" means free space, not the size of everything on D:.
    return Orchestrator([HardwareAgent(), FileAgent()], brain)


def ask_if_needed(maverick: Orchestrator, result: Result) -> Result:
    """If MAVERICK asked a y/n question, get the answer. Anything but y/yes cancels."""
    if not result.data.get("confirm"):
        return result
    try:
        answer = input(f"MAVERICK: {result.message} (y/n) ")
    except (EOFError, KeyboardInterrupt):
        answer = ""
    return maverick.confirm(answer.strip().lower() in {"y", "yes"})


def repl(maverick: Orchestrator) -> None:
    print("MAVERICK — offline Windows agent. Type 'help' for agents, 'exit' to quit.")
    while True:
        try:
            text = input("\nYou: ")
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return
        result = ask_if_needed(maverick, maverick.handle(text))
        print("MAVERICK:", result.message)
        if result.data.get("exit"):
            return


if __name__ == "__main__":
    brain = Brain.load()
    if brain is None:
        print("(Brain not trained yet; using keyword rules. Train it with: python -m maverick.brain.train)")
    maverick = build(brain)
    if len(sys.argv) > 1:
        # The shell already removed the quotes, so put them back around args with spaces,
        # unless the whole request was passed as one quoted sentence.
        args = sys.argv[1:]
        if len(args) > 1:
            args = [f'"{a}"' if " " in a else a for a in args]
        result = ask_if_needed(maverick, maverick.handle(" ".join(args)))
        print(result.message)
        sys.exit(0 if result.success else 1)
    repl(maverick)
