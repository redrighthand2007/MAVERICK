"""Admin-rights audit: who is in the Administrators group, and is MAVERICK itself running as admin. Read-only."""
import getpass
import json

from maverick.core import windows
from maverick.core.agent_base import Result

# The Administrators group's SID is the same on every Windows, whatever the language ("Administratoren" ...).
ADMINS_SID = "S-1-5-32-544"
SOURCES = {1: "this PC", 2: "domain", 3: "Microsoft Entra", 4: "Microsoft account"}


def as_list(text: str) -> list[dict]:
    data = json.loads(text or "[]")
    return data if isinstance(data, list) else [data]


def admin_members() -> list[dict]:
    done = windows.powershell(f"Get-LocalGroupMember -SID {ADMINS_SID} | "
                              "Select-Object Name, ObjectClass, PrincipalSource | ConvertTo-Json -Compress")
    return [{"name": m["Name"], "kind": m.get("ObjectClass") or "", "source": SOURCES.get(m.get("PrincipalSource"), "")}
            for m in as_list(done.stdout)]


def enabled_users() -> dict[str, bool]:
    done = windows.powershell("Get-LocalUser | Select-Object Name, Enabled | ConvertTo-Json -Compress")
    return {u["Name"].lower(): bool(u["Enabled"]) for u in as_list(done.stdout)}


def admins() -> Result:
    members = admin_members()
    enabled = enabled_users()
    me = getpass.getuser().lower()
    lines = [f"{len(members)} account{'s' if len(members) != 1 else ''} with Administrator rights on this PC:"]
    active = 0
    for m in members:
        short = m["name"].split("\\")[-1].lower()
        state = enabled.get(short)
        if state is not False:
            active += 1
        notes = [n for n in (m["kind"].lower() if m["kind"] != "User" else "", m["source"],
                             "disabled" if state is False else "", "you" if short == me else "") if n]
        lines.append(f"  - {m['name']}" + (f" ({', '.join(notes)})" if notes else ""))
    elevated = "yes" if windows.is_admin() else "no (changes that need admin will ask you to restart it as admin)"
    lines.append(f"MAVERICK is running as Administrator right now: {elevated}")
    if active > 2:
        lines.append(f"Note: {active} active admin accounts. Fewer admins means less damage if one is hacked.")
    return Result(True, "\n".join(lines), {"admins": [m["name"] for m in members], "active": active,
                                           "elevated": windows.is_admin()})
