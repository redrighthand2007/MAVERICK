"""Power mode / plan and screen brightness. Both change instantly and can be switched straight back."""
import ctypes
import re
import subprocess
import uuid

from maverick.core.agent_base import Result

# Windows 11 power modes (Settings > System > Power). They sit on top of the active plan.
MODES = {
    "best power efficiency": uuid.UUID("961cc777-2547-4f9d-8174-7d86181b8a7a"),
    "balanced": uuid.UUID("00000000-0000-0000-0000-000000000000"),
    "best performance": uuid.UUID("ded574b5-45a0-4f42-8737-46345c09c238"),
}
MODE_WORDS = {
    "best power efficiency": {"saver", "saving", "efficiency", "efficient", "eco", "battery", "save", "low", "quiet"},
    "balanced": {"balanced", "balance", "normal", "default"},
    "best performance": {"performance", "fast", "faster", "max", "maximum", "high", "turbo", "gaming", "speed"},
}
PLAN_RE = re.compile(r"([0-9a-f]{8}-[0-9a-f-]{27})\s+\((.+?)\)\s*(\*)?", re.IGNORECASE)


class GUID(ctypes.Structure):
    _fields_ = [("bytes", ctypes.c_ubyte * 16)]

    @classmethod
    def of(cls, value: uuid.UUID) -> "GUID":
        guid = cls()
        ctypes.memmove(guid.bytes, value.bytes_le, 16)
        return guid


def current_mode() -> str:
    guid = GUID()
    if ctypes.windll.powrprof.PowerGetEffectiveOverlayScheme(ctypes.byref(guid)):
        return "unknown"
    value = uuid.UUID(bytes_le=bytes(guid.bytes))
    return next((name for name, g in MODES.items() if g == value), "unknown")


def set_mode(name: str) -> None:
    code = ctypes.windll.powrprof.PowerSetActiveOverlayScheme(ctypes.byref(GUID.of(MODES[name])))
    if code:
        raise OSError(f"Windows refused to change the power mode (code {code})")


def run(args: list[str]) -> str:
    return subprocess.run(args, capture_output=True, text=True, shell=False, timeout=15,
                          stdin=subprocess.DEVNULL).stdout


def plans() -> list[dict]:
    """Classic power plans from `powercfg /list`: [{"guid", "name", "active"}]."""
    return [{"guid": g, "name": n, "active": bool(star)} for g, n, star in PLAN_RE.findall(run(["powercfg", "/list"]))]


def match_mode(text: str) -> str:
    words = set(re.findall(r"[a-z]+", text.lower()))
    return next((mode for mode, keys in MODE_WORDS.items() if words & keys), "")


def plan(name: str = "") -> Result:
    """Show the power mode and plans, or switch to `name` ("power saver", "performance", or a plan's name)."""
    if not name:
        lines = [f"Power mode: {current_mode()}  (choices: {', '.join(MODES)})", "Power plans:"]
        lines += [f"  - {p['name']}{'  (active)' if p['active'] else ''}" for p in plans()]
        return Result(True, "\n".join(lines), {"mode": current_mode(), "plans": plans()})
    # A plan named in the request ("ultimate performance") wins; Balanced is left to the mode of the same name.
    exact = next((p for p in plans() if p["name"].lower() in name.lower() and p["name"].lower() != "balanced"), None)
    if exact:
        run(["powercfg", "/setactive", exact["guid"]])
        return Result(True, f"Switched to the {exact['name']} power plan.", {"plan": exact["name"]})
    mode = match_mode(name)
    if not mode:
        names = [p["name"] for p in plans()]
        return Result(False, f"Which one? Power modes: {', '.join(MODES)}. Plans on this PC: {', '.join(names)}.")
    before = current_mode()
    set_mode(mode)
    return Result(True, f"Power mode: {before} -> {mode}.", {"mode": mode})


def powershell(script: str) -> str:
    done = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True,
                          shell=False, timeout=20, stdin=subprocess.DEVNULL)
    return done.stdout.strip()


def get_brightness() -> int | None:
    out = powershell("(Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightness "
                     "-ErrorAction SilentlyContinue | Select-Object -First 1).CurrentBrightness")
    return int(out) if out.isdigit() else None


def brightness(level: str = "") -> Result:
    """level: "" to read, "50" to set, "+20" / "-20" to change."""
    now = get_brightness()
    if now is None:
        return Result(False, "This screen doesn't let Windows set its brightness "
                             "(usually an external monitor; use its own buttons).")
    if not level:
        return Result(True, f"Screen brightness: {now}%", {"brightness": now})
    target = now + int(level) if level[0] in "+-" else int(level)
    target = max(0, min(100, target))
    powershell("Get-CimInstance -Namespace root/wmi -ClassName WmiMonitorBrightnessMethods | "
               f"Invoke-CimMethod -MethodName WmiSetBrightness -Arguments @{{Timeout=1; Brightness={target}}} | Out-Null")
    return Result(True, f"Screen brightness: {now}% -> {target}%", {"brightness": target})

