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
    """
    name = "base"
    description = ""

    def parse(self, text: str) -> Intent | None:
        raise NotImplementedError

    def extract(self, operation: str, text: str) -> Intent:
        """The brain already chose the operation; just pull its arguments out of the text."""
        raise NotImplementedError

    def handle(self, intent: Intent) -> Result:
        raise NotImplementedError
