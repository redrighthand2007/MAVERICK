import re

from maverick.agents.services import ops
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z0-9]+")
SERVICE_WORDS = {"service", "services", "spooler"}
ACTION_WORDS = {
    "restart": "restart", "reboot": "restart", "reset": "restart",
    "start": "start", "run": "start", "launch": "start", "begin": "start",
    "stop": "stop", "kill": "stop", "end": "stop", "halt": "stop",
    "disable": "disable", "enable": "enable", "manual": "manual",
}
BOOT_RE = re.compile(r"\b(?:at|on)\s+(?:boot|startup|start up)\b|\bautomatic(?:ally)?\b|\bauto\s*start\b")
FILLER = {
    "the", "a", "my", "service", "services", "please", "pls", "can", "you", "u", "is", "are", "it", "its", "of",
    "show", "list", "all", "running", "status", "what", "which", "whats", "check", "me", "tell", "if", "on", "off",
    "at", "boot", "startup", "up", "automatic", "automatically", "auto", "set", "make", "turn", "to", "now", "and",
    "for", "this", "that", "windows'", "do", "i", "have", "how", "many", "there", "again", "from", "starting",
    "stopped", "started", "type", "when", "pc", "computer", "with",
}


class ServicesAgent(SubAgent):
    name = "services"
    description = ("Windows services: list, check, start, stop, restart, enable at boot, disable (changes need admin). "
                   "e.g. is the print spooler running  |  restart the spooler service")
    risky = {"change"}

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower()))
        if not words & SERVICE_WORDS:
            return None
        has_action = any(w in ACTION_WORDS for w in words) or BOOT_RE.search(text.lower())
        return self.extract("change" if has_action else "list", text)

    def extract(self, operation: str, text: str) -> Intent:
        low = text.lower().replace("'s", "")
        words = WORD_RE.findall(low)
        action = next((ACTION_WORDS[w] for w in words if w in ACTION_WORDS), "")
        if BOOT_RE.search(low) and action in ("", "start"):
            action = "enable"
        if "spooler" in words and "print" not in words:
            words.append("print")  # "the spooler" is the Print Spooler
        name = " ".join(w for w in words if w not in FILLER and w not in ACTION_WORDS)
        if operation == "list" or not action:
            return Intent("list", {"query": name})
        return Intent("change", {"name": name, "action": action}, [] if name else ["service name"])

    def describe(self, intent: Intent) -> str:
        return ops.describe(**intent.args)

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "list":
            return ops.list_services(**intent.args)
        return ops.change(**intent.args)
