import re

from maverick.agents.devices import ops
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z0-9]+")
DEVICE_WORDS = {"device", "devices", "driver", "drivers", "webcam", "camera", "cam", "touchpad", "trackpad",
                "microphone", "mic", "fingerprint", "gpu", "graphics", "usb"}
RESTART_WORDS = {"restart", "reset", "reload", "reboot", "fix", "unstick", "reinitialize"}
FILLER = {
    "the", "a", "my", "device", "devices", "driver", "drivers", "please", "pls", "can", "you", "u", "is", "are",
    "it", "its", "show", "list", "all", "what", "which", "check", "me", "working", "work", "not", "isnt", "doesnt",
    "of", "on", "this", "pc", "laptop", "computer", "status", "with", "problems", "problem", "broken", "any",
    "have", "do", "i", "connected", "installed", "and", "again", "now", "for", "that", "stuck", "frozen", "card",
} | RESTART_WORDS


class DevicesAgent(SubAgent):
    name = "devices"
    description = ("devices and drivers: list them, spot problems, restart one (e.g. a stuck webcam; needs admin). "
                   "e.g. show devices with problems  |  restart the webcam")
    risky = {"restart"}

    def parse(self, text: str) -> Intent | None:
        words = set(WORD_RE.findall(text.lower().replace("'", "")))
        if not words & DEVICE_WORDS:
            return None
        return self.extract("restart" if words & RESTART_WORDS else "list", text)

    def extract(self, operation: str, text: str) -> Intent:
        words = WORD_RE.findall(text.lower().replace("'", ""))
        query = " ".join(w for w in words if w not in FILLER)
        if operation == "list":
            return Intent("list", {"query": query})
        return Intent("restart", {"name": query}, [] if query else ["which device"])

    def describe(self, intent: Intent) -> str:
        return ops.describe(**intent.args)

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "list":
            return ops.list_devices(**intent.args)
        return ops.restart(**intent.args)
