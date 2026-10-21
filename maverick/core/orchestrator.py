from maverick.core.agent_base import Result, SubAgent
from maverick.core.safety import SafetyError

EXIT_WORDS = {"exit", "quit", "bye", "goodbye"}


class Orchestrator:
    """The central agent: finds the sub-agent that owns a request and runs it."""

    def __init__(self, agents: list[SubAgent]):
        self.agents = agents

    def handle(self, text: str) -> Result:
        text = text.strip()
        if not text:
            return Result(False, "Please type a request.")
        if text.lower() in EXIT_WORDS:
            return Result(True, "Goodbye.", {"exit": True})
        if text.lower() == "help":
            return self.help()

        for agent in self.agents:
            intent = agent.parse(text)
            if intent is None:
                continue
            if intent.missing:
                return Result(False, f"[{agent.name}] I need: " + ", ".join(intent.missing))
            try:
                return agent.handle(intent)
            except SafetyError as exc:
                return Result(False, f"Blocked for safety: {exc}")
            except OSError as exc:
                return Result(False, f"Windows refused the operation: {exc}")

        return Result(False, "No MAVERICK agent handles that yet. Type 'help' to see what I can do.")

    def help(self) -> Result:
        lines = [f"- {a.name}: {a.description}" for a in self.agents]
        return Result(True, "Available agents:\n" + "\n".join(lines))
