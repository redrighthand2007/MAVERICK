"""Small helpers shared by the admin-level agents (Stage 7)."""
import ctypes
import subprocess

ADMIN_HINT = ("This needs Administrator rights. Close MAVERICK, right-click Terminal or PowerShell, "
              "choose 'Run as administrator', and start MAVERICK there.")


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except OSError:
        return False


def powershell(script: str, timeout: int = 30) -> subprocess.CompletedProcess:
    """Run a PowerShell command without a profile; returns the finished process (stdout, stderr, returncode)."""
    return subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
                          capture_output=True, text=True, shell=False, timeout=timeout, stdin=subprocess.DEVNULL)


def quote(value: str) -> str:
    """A safe single-quoted PowerShell string: user text can never break out into a command."""
    return "'" + value.replace("'", "''") + "'"
