from maverick.core.agent_base import Intent, Result, SubAgent
from maverick.core.safety import SafetyError

EXIT_WORDS = {"exit", "quit", "bye", "goodbye"}
# Below this, the brain is not trusted and keyword rules decide instead (chosen from `python -m maverick.brain.evaluate`).
CONFIDENCE_THRESHOLD = 0.6
# Between this and the threshold, MAVERICK suggests its guess; below it, the guess is too weak to mention.
SUGGEST_THRESHOLD = 0.5


class Orchestrator:
    """The central agent: finds the sub-agent that owns a request and runs it.

    1. The brain (if trained) guesses "agent.operation" with a confidence.
    2. Confident and a real operation -> that agent extracts the arguments and runs.
    3. Otherwise -> fall back to each agent's keyword rules, like before the brain existed.
    """

    def __init__(self, agents: list[SubAgent], brain=None):
        self.agents = agents
        self.by_name = {agent.name: agent for agent in agents}
        self.brain = brain

    def handle(self, text: str) -> Result:
        text = text.strip()
        if not text:
            return Result(False, "Please type a request.")
        if text.lower() in EXIT_WORDS:
            return Result(True, "Goodbye.", {"exit": True})
        if text.lower() == "help":
            return self.help()

        guess, confidence = self.brain.predict(text) if self.brain else ("unknown", 0.0)
        if confidence >= CONFIDENCE_THRESHOLD and guess != "unknown":
            agent_name, operation = guess.split(".", 1)
            agent = self.by_name.get(agent_name)
            if agent:
                return self.run(agent, agent.extract(operation, text))

        for agent in self.agents:
            intent = agent.parse(text)
            if intent is not None:
                return self.run(agent, intent)

        if guess != "unknown" and confidence >= SUGGEST_THRESHOLD:
            return Result(False, f"I'm not sure what you mean. Did you want {guess}? Try rephrasing.")
        return Result(False, "No MAVERICK agent handles that yet. Type 'help' to see what I can do.")

    def run(self, agent: SubAgent, intent: Intent) -> Result:
        if intent.missing:
            return Result(False, f"[{agent.name}] I need: " + ", ".join(intent.missing))
        try:
            return agent.handle(intent)
        except SafetyError as exc:
            return Result(False, f"Blocked for safety: {exc}")
        except OSError as exc:
            return Result(False, f"Windows refused the operation: {exc}")

    def help(self) -> Result:
        lines = [f"- {a.name}: {a.description}" for a in self.agents]
        brain = "on" if self.brain else "off (run: python -m maverick.brain.train)"
        return Result(True, "Available agents:\n" + "\n".join(lines) + f"\nBrain: {brain}")
