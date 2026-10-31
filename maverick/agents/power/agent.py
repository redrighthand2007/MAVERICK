import re

from maverick.agents.power import ops
from maverick.core.agent_base import Intent, Result, SubAgent

PLAN_RE = re.compile(r"\bpower\s+(?:plan|plans|mode|modes|saver|saving|settings?|profile)\b|\bbattery\s+saver\b"
                     r"|\b(?:performance|efficiency|balanced|eco|gaming|turbo|saver)\s+mode\b|\bbest\s+(?:performance|power)\b")
BRIGHT_RE = re.compile(r"\bbright(?:ness|er|en)?\b|\bdim(?:mer)?\b|\bdarker\b|\bscreen\s+light\b")
SHOW_WORDS = {"what", "whats", "which", "show", "current", "list", "is", "am", "check"}
SET_WORDS = {"switch", "set", "turn", "change", "use", "enable", "go", "put", "make", "activate", "on", "to"}
UP_WORDS = {"up", "brighter", "increase", "raise", "more", "higher", "brighten"}
DOWN_WORDS = {"down", "dim", "dimmer", "darker", "lower", "decrease", "reduce", "less"}


class PowerAgent(SubAgent):
    name = "power"
    description = ("power mode / plan and screen brightness. "
                   "e.g. switch to power saver  |  what power mode am i on  |  set brightness to 40")
    # Both change instantly and can be switched straight back, so no y/n question.

    def parse(self, text: str) -> Intent | None:
        low = text.lower()
        if BRIGHT_RE.search(low):
            return self.extract("brightness", text)
        if PLAN_RE.search(low):
            return self.extract("plan", text)
        return None

    def extract(self, operation: str, text: str) -> Intent:
        low = text.lower().replace("'", "")
        words = set(re.findall(r"[a-z]+", low))
        if operation == "brightness":
            number = re.search(r"\b(\d{1,3})\s*%?", low)
            if number:
                level = number.group(1)
            elif words & {"max", "maximum", "full"}:
                level = "100"
            elif words & UP_WORDS:
                level = "+20"
            elif words & DOWN_WORDS:
                level = "-20"
            else:
                level = ""
            return Intent("brightness", {"level": level})
        wants_change = bool(words & SET_WORDS) or not words & SHOW_WORDS
        # The whole request is passed on: ops.plan() matches it against the PC's plan names, then the modes.
        return Intent("plan", {"name": low.strip() if wants_change and (ops.match_mode(low) or "plan" in words) else ""})

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "brightness":
            return ops.brightness(**intent.args)
        return ops.plan(**intent.args)
