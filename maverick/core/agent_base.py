from dataclasses import dataclass, field


@dataclass
class Intent:
    """What the user wants: which operation, with which arguments."""
    operation: str
    args: dict = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


@dataclass
class Result:
    """What happened. Every sub-agent returns this same shape."""
    success: bool
    message: str
    data: dict = field(default_factory=dict)


class SubAgent:
    """Base class every MAVERICK sub-agent follows.

    parse()   -> keyword rules: returns an Intent if this agent owns the request, else None.
    extract() -> used when the brain picked the operation: only finds the arguments.
    handle()  -> actually does the work and returns a Result.

    Operations listed in `risky` change or remove something that already exists.
    For those, the orchestrator first calls describe() and asks the user y/n before handle().
    """
    name = "base"
    description = ""
    risky: set[str] = set()

    def parse(self, text: str) -> Intent | None:
        raise NotImplementedError

    def extract(self, operation: str, text: str) -> Intent:
        """The brain already chose the operation; just pull its arguments out of the text."""
        raise NotImplementedError

    def describe(self, intent: Intent) -> str:
        """Runs the safety checks and returns the question to ask, e.g. "Move a.txt -> D:\\x\\a.txt?"."""
        raise NotImplementedError

    def handle(self, intent: Intent) -> Result:
        raise NotImplementedError
