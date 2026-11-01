import re

from maverick.core.agent_base import Intent, Result, SubAgent
from maverick.core.safety import SafetyError

EXIT_WORDS = {"exit", "quit", "bye", "goodbye"}
# Below this, the brain is not trusted and keyword rules decide instead (chosen from `python -m maverick.brain.evaluate`).
# A brain can bring its own (brain.threshold); this is the fallback.
CONFIDENCE_THRESHOLD = 0.6
# Between this and the threshold, MAVERICK suggests its guess; below it, the guess is too weak to mention.
SUGGEST_THRESHOLD = 0.5
# "zip it" after "copy notes.txt to D:\backup": "it" means what the step before produced (8.16).
PRONOUN_RE = re.compile(r"(?<![\w'])(it|them)(?![\w'])", re.IGNORECASE)


def fill_in(text: str, previous_output: str | None) -> str:
    """'zip it' + 'D:\\backup\\notes.txt' -> 'zip "D:\\backup\\notes.txt"'"""
    if not previous_output:
        return text
    # A function, not a string: re.sub would read the backslashes in a Windows path as escape codes.
    return PRONOUN_RE.sub(lambda _: f'"{previous_output}"', text, count=1)


class Orchestrator:
    """The central agent: finds the sub-agent that owns a request and runs it.

    1. The brain (if trained) guesses "agent.operation" with a confidence.
    2. Confident and a real operation -> that agent extracts the arguments and runs.
    3. Otherwise -> fall back to each agent's keyword rules, like before the brain existed.

    Risky operations are not run straight away: handle() returns a question with
    data["confirm"] = True, and the caller answers it with confirm(yes).

    Several actions in one request (8.16): the splitter cuts "copy a.txt to D:\\x and zip it" into pieces.
    Every piece must be understood BEFORE the first one runs; otherwise it's treated as one request.
    The pieces then run in order, and a failed piece stops the rest.
    """

    def __init__(self, agents: list[SubAgent], brain=None, splitter=None):
        self.agents = agents
        self.by_name = {agent.name: agent for agent in agents}
        self.brain = brain
        self.splitter = splitter
        self.pending: tuple[SubAgent, Intent] | None = None  # a risky action waiting for y/n
        self.queue: list[str] = []  # pieces of a multi-action request still to run
        self.done: list[str] = []   # what the earlier pieces reported

    def handle(self, text: str) -> Result:
        self.pending = None  # a new request drops any unanswered question
        self.queue, self.done = [], []
        text = text.strip()
        if not text:
            return Result(False, "Please type a request.")
        if text.lower() in EXIT_WORDS:
            return Result(True, "Goodbye.", {"exit": True})
        if text.lower() == "help":
            return self.help()

        pieces = self.splitter.split(text) if self.splitter else [text]
        if len(pieces) > 1:
            guesses = [self.guess(piece) for piece in pieces]
            if all(self.understands(piece, guess) for piece, guess in zip(pieces, guesses)):
                self.queue = pieces[1:]
                return self.chain(self.handle_one(pieces[0], guesses[0]))
        return self.handle_one(text)

    def guess(self, text: str) -> tuple[str, float]:
        return self.brain.predict(text) if self.brain else ("unknown", 0.0)

    def trusted(self, guess: str, confidence: float) -> bool:
        return confidence >= getattr(self.brain, "threshold", CONFIDENCE_THRESHOLD) and guess != "unknown"

    def understands(self, text: str, guess: tuple[str, float]) -> bool:
        """Would some agent take this piece on its own?"""
        if self.trusted(*guess) and guess[0].split(".", 1)[0] in self.by_name:
            return True
        return any(agent.parse(text) is not None for agent in self.agents)

    def chain(self, result: Result) -> Result:
        """After one piece: run the next ones until a piece fails or asks a y/n question."""
        while self.queue and result.success and not result.data.get("confirm"):
            self.done.append(result.message)
            result = self.handle_one(fill_in(self.queue.pop(0), result.data.get("output")))
        if self.queue and not result.success and not result.data.get("confirm"):
            result = Result(False, f"{result.message}\nStopped there, so I did not: " + "; ".join(self.queue))
            self.queue = []
        if self.done:
            result = Result(result.success, "\n".join([*self.done, result.message]), result.data)
            self.done = []
        return result

    def handle_one(self, text: str, guess: tuple[str, float] | None = None) -> Result:
        guess, confidence = guess or self.guess(text)
        if self.trusted(guess, confidence):
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
        if agent.is_risky(intent):
            # describe() runs the safety checks first, so a blocked action is never even asked about.
            question = self.safely(lambda: Result(False, agent.describe(intent), {"confirm": True}))
            if question.data.get("confirm"):
                self.pending = (agent, intent)
            return question
        return self.safely(lambda: agent.handle(intent))

    def confirm(self, yes: bool) -> Result:
        """The user's answer to the last question: run the pending action, or cancel it."""
        if self.pending is None:
            return Result(False, "Nothing is waiting for confirmation.")
        agent, intent = self.pending
        self.pending = None
        if not yes:
            return self.chain(Result(False, "Cancelled. Nothing was changed."))
        return self.chain(self.safely(lambda: agent.handle(intent)))

    @staticmethod
    def safely(action) -> Result:
        try:
            return action()
        except SafetyError as exc:
            return Result(False, f"Blocked for safety: {exc}")
        except OSError as exc:
            return Result(False, f"Windows refused the operation: {exc}")

    def help(self) -> Result:
        lines = [f"- {a.name}: {a.description}" for a in self.agents]
        brain = "on" if self.brain else "off (run: python -m maverick.brain.train)"
        return Result(True, "Available agents:\n" + "\n".join(lines) + f"\nBrain: {brain}")
