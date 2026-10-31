import re

from maverick.agents.network import ops
from maverick.core.agent_base import Intent, Result, SubAgent

WORD_RE = re.compile(r"[a-z0-9-]+")
ADAPTER_WORDS = {"wifi", "wi-fi", "wireless", "wlan", "ethernet", "adapter", "adapters", "lan", "network"}
INFO_RE = re.compile(r"\bip\b|\bipv[46]\b|\bip address|\bmac\b|\bssid\b|\bnetwork adapters?\b|\bwhich (?:wifi|network)\b"
                     r"|\bwifi (?:name|signal|strength|speed)\b|\bsignal strength\b|\bam i (?:online|connected)\b"
                     r"|\bconnected to\b|\bnetwork (?:info|details|status)\b|\binternet connection\b")
ON_WORDS = {"on", "enable", "enabled", "activate", "start", "reconnect"}
OFF_WORDS = {"off", "disable", "disabled", "deactivate", "stop", "kill", "cut"}
NAME_FILLER = {"turn", "switch", "the", "my", "please", "pls", "adapter", "network", "card", "connection", "and",
               "it", "for", "now", "a", "while", "can", "you", "u", "put", "to", "of"} | ON_WORDS | OFF_WORDS


class NetworkAgent(SubAgent):
    name = "network"
    description = ("network adapters: IP / MAC addresses, Wi-Fi name and signal; turn Wi-Fi or an adapter on/off "
                   "(needs admin). e.g. what's my ip address  |  turn off wifi")
    risky = {"wifi"}

    def parse(self, text: str) -> Intent | None:
        low = text.lower()
        words = set(WORD_RE.findall(low))
        names_adapter = words & (ADAPTER_WORDS - {"network"}) or words & {"card"}
        switching = words & (ON_WORDS | OFF_WORDS) and names_adapter
        if switching and not words & {"bluetooth", "connect", "password"}:
            return self.extract("wifi", text)
        if INFO_RE.search(low):
            return self.extract("info", text)
        return None

    def extract(self, operation: str, text: str) -> Intent:
        if operation == "info":
            return Intent("info")
        words = WORD_RE.findall(text.lower())
        state = "off" if set(words) & OFF_WORDS else "on"
        name = " ".join(w for w in words if w not in NAME_FILLER)
        if name in ("wi-fi", "wireless", "wlan", "wifi"):
            name = "wifi"
        return Intent("wifi", {"adapter": name, "state": state})

    def describe(self, intent: Intent) -> str:
        return ops.describe(**intent.args)

    def handle(self, intent: Intent) -> Result:
        if intent.operation == "info":
            return ops.info()
        return ops.switch(**intent.args)
