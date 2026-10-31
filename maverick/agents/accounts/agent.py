import re

from maverick.agents.accounts import ops
from maverick.brain.text import looks_like_path
from maverick.core.agent_base import Intent, Result, SubAgent

ADMIN_RE = re.compile(r"\badmins?\b|\badministrators?\b|\badmin (?:rights|access|privileges?)\b|\belevated\b"
                      r"|\bprivileges?\b")
NOT_AUDIT = {"run", "restart", "open", "start", "launch", "make", "create", "add", "remove", "give", "grant"}


class AccountsAgent(SubAgent):
    name = "accounts"
    description = ("admin-rights audit (read-only): who has Administrator rights, and is MAVERICK running as admin. "
                   "e.g. who has admin on this pc  |  am i admin")

    def parse(self, text: str) -> Intent | None:
        # Paths don't count: "C:\Users\Admin\notes.txt" is not a question about admins.
        low = " ".join(t for t in text.lower().split() if not looks_like_path(t.strip('"')) and '"' not in t)
        words = set(re.findall(r"[a-z]+", low))
        # "run as admin" / "give tom admin" are actions MAVERICK doesn't do; only questions are audits.
        if not ADMIN_RE.search(low) or words & NOT_AUDIT:
            return None
        return self.extract("admins", text)

    def extract(self, operation: str, text: str) -> Intent:
        return Intent("admins")

    def handle(self, intent: Intent) -> Result:
        return ops.admins()
