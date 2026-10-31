"""Windows services: list and check them (anyone), start / stop / restart / enable / disable (Administrator)."""
import psutil

from maverick.core import windows
from maverick.core.agent_base import Result
from maverick.core.safety import SafetyError

# Stopping or disabling these breaks Windows, networking or security. Starting them is always fine.
PROTECTED = {
    "rpcss", "rpceptmapper", "dcomlaunch", "lsm", "samss", "winmgmt", "eventlog", "plugplay", "power", "profsvc",
    "schedule", "cryptsvc", "bfe", "mpssvc", "windefend", "wscsvc", "securityhealthservice", "dhcp", "dnscache",
    "nsi", "gpsvc", "usermanager", "coremessagingregistrar", "brokerinfrastructure", "systemeventsbroker",
    "trustedinstaller", "audiosrv", "audioendpointbuilder", "themes", "sense", "wdnissvc", "netprofm", "nlasvc",
}
ACTIONS = {
    "start": "Start-Service -Name {name}",
    "stop": "Stop-Service -Name {name}",
    "restart": "Restart-Service -Name {name}",
    "enable": "Set-Service -Name {name} -StartupType Automatic",
    "disable": "Set-Service -Name {name} -StartupType Disabled",
    "manual": "Set-Service -Name {name} -StartupType Manual",
}
STARTUP = {"automatic": "starts at boot", "manual": "starts when needed", "disabled": "disabled"}


def all_services() -> list[dict]:
    services = []
    for service in psutil.win_service_iter():
        try:
            info = service.as_dict()
        except (psutil.Error, OSError):
            continue
        services.append({"name": info["name"], "display": info["display_name"], "status": info["status"],
                         "start": info["start_type"]})
    return services


def matches(query: str) -> list[dict]:
    """Exact service name or display name first; otherwise every service whose names contain all the words."""
    query = query.lower().strip()
    services = all_services()
    exact = [s for s in services if query in (s["name"].lower(), s["display"].lower())]
    if exact:
        return exact
    words = query.split()
    return [s for s in services if all(w in f"{s['name']} {s['display']}".lower() for w in words)]


def line(service: dict) -> str:
    start = STARTUP.get(service["start"], service["start"])
    return f"  - {service['display']} ({service['name']}): {service['status']}, {start}"


def list_services(query: str = "") -> Result:
    if query:
        found = matches(query)
        if not found:
            return Result(False, f"No service matches '{query}'.")
        lines = [f"{len(found)} service{'s' if len(found) > 1 else ''} matching '{query}':"]
        lines += [line(s) for s in found[:30]]
        return Result(True, "\n".join(lines), {"services": [s["name"] for s in found]})
    services = all_services()
    running = [s for s in services if s["status"] == "running"]
    lines = [f"{len(running)} of {len(services)} services are running. Running now:"]
    lines += [line(s) for s in sorted(running, key=lambda s: s["display"].lower())[:40]]
    if len(running) > 40:
        lines.append(f"  ... and {len(running) - 40} more (ask about one, e.g. 'is the print spooler running')")
    return Result(True, "\n".join(lines), {"running": len(running), "total": len(services)})


def plan(name: str, action: str) -> dict:
    found = matches(name)
    if not found:
        raise SafetyError(f"No service matches '{name}'.")
    if len(found) > 1:
        names = ", ".join(f"{s['display']} ({s['name']})" for s in found[:8])
        raise SafetyError(f"'{name}' matches {len(found)} services: {names}. Say which one.")
    service = found[0]
    if action in {"stop", "disable", "restart"} and service["name"].lower() in PROTECTED:
        raise SafetyError(f"{service['display']} is a core Windows service; stopping or disabling it would break Windows.")
    return service


def describe(name: str, action: str) -> str:
    service = plan(name, action)
    admin = "" if windows.is_admin() else " (needs Administrator)"
    return f"{action.capitalize()} the {service['display']} service ({service['name']}, now {service['status']}){admin}?"


def change(name: str, action: str) -> Result:
    service = plan(name, action)
    if not windows.is_admin():
        return Result(False, windows.ADMIN_HINT)
    done = windows.powershell(ACTIONS[action].format(name=windows.quote(service["name"])))
    if done.returncode != 0:
        reason = (done.stderr.strip().splitlines() or ["unknown error"])[0]
        return Result(False, f"Windows refused to {action} {service['display']}: {reason}")
    after = next((s for s in all_services() if s["name"] == service["name"]), service)
    return Result(True, f"Done: {action} {service['display']}.\n{line(after)}", {"service": after})
