import sys
import time
from pathlib import Path

# Lets `python maverick/main.py` work from the project root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from maverick.agents.archive.agent import ArchiveAgent
from maverick.agents.cleanup.agent import CleanupAgent
from maverick.agents.devices.agent import DevicesAgent
from maverick.agents.files.agent import FileAgent
from maverick.agents.hardware.agent import HardwareAgent
from maverick.agents.jobs.agent import JobsAgent
from maverick.agents.logs.agent import LogsAgent
from maverick.agents.network.agent import NetworkAgent
from maverick.agents.power.agent import PowerAgent
from maverick.agents.process.agent import ProcessAgent
from maverick.agents.search.agent import SearchAgent
from maverick.agents.services.agent import ServicesAgent
from maverick.agents.watch.agent import WatchAgent
from maverick.brain import Brain
from maverick.core.agent_base import Result
from maverick.core.background import JOBS_PATH, Background
from maverick.core.orchestrator import Orchestrator


LOG_PATH = JOBS_PATH.parent / "background.log"


def build(brain: Brain | None = None, background: Background | None = None) -> Orchestrator:
    # Jobs that keep running in the background (6.1). Without one passed in, jobs live in memory only.
    background = background or Background()
    # Register sub-agents here. Order matters for keyword rules: the first agent that understands a request wins.
    # Process before jobs: process ignores job words, so "stop job 2" falls through to the jobs agent.
    # Jobs before cleanup: "remove the downloads watcher" stops a job; it doesn't delete a file.
    # Jobs before watch: "stop watching downloads" ends a watcher instead of starting one.
    # Watch before files: "move every new pdf in downloads to documents" is a watcher, not a one-off move.
    # Services after process: process ignores "service", so "stop the spooler service" reaches services.
    # Logs before cleanup and archive: "empty / compress server.log" rotates a log, it doesn't delete or zip it.
    # Process before hardware: "which programs use the most memory" is about programs, not RAM size.
    # Power before hardware: "turn on battery saver" is a power mode, not a battery reading.
    # Cleanup before hardware: "free up space on D:" wants space back, not "how much is free".
    # Hardware before files: "space left on D:" means free space, not the size of everything on D:.
    # Search before files: "find big files" is a search, not "size of big".
    # Search before archive: "find zip files" is a search, not "make a zip".
    agents = [
        ProcessAgent(), JobsAgent(background), WatchAgent(background), LogsAgent(background), ServicesAgent(),
        NetworkAgent(), DevicesAgent(), PowerAgent(), CleanupAgent(), HardwareAgent(), SearchAgent(), ArchiveAgent(),
        FileAgent(),
    ]
    maverick = Orchestrator(agents, brain)
    maverick.background = background
    return maverick


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


def background_only(background: Background) -> None:
    """`python -m maverick.main --background`: no chat, just keep the saved jobs running until Ctrl+C.

    With pythonw.exe there is no window at all; job messages also go to ~/.maverick/background.log.
    """
    def notify(message: str) -> None:
        line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}"
        print(line)
        with open(LOG_PATH, "a", encoding="utf-8") as log:
            log.write(line + "\n")

    background.notify = notify
    if not background.load():
        print("No background jobs saved yet. Start MAVERICK normally and add one, e.g. 'watch downloads for pdfs'.")
        return
    print(f"MAVERICK background mode: {len(background.list())} job(s) running. Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Background mode stopped; the jobs stay saved for next time.")


if __name__ == "__main__":
    background = Background(JOBS_PATH, notify=lambda message: print(f"\nMAVERICK (background): {message}"))
    if sys.argv[1:] == ["--background"]:
        background_only(background)
        sys.exit(0)
    brain = Brain.load()
    if brain is None:
        print("(Brain not trained yet; using keyword rules. Train it with: python -m maverick.brain.train)")
    maverick = build(brain, background)
    if len(sys.argv) > 1:
        # The shell already removed the quotes, so put them back around args with spaces,
        # unless the whole request was passed as one quoted sentence.
        args = sys.argv[1:]
        if len(args) > 1:
            args = [f'"{a}"' if " " in a else a for a in args]
        result = ask_if_needed(maverick, maverick.handle(" ".join(args)))
        print(result.message)
        sys.exit(0 if result.success else 1)
    restored = background.load()
    if restored:
        print(f"({restored} background job(s) restored; say 'show background jobs'.)")
    repl(maverick)
