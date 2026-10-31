"""Send files to the Windows Recycle Bin, so every delete can be undone from there."""
import ctypes
from ctypes import wintypes
from pathlib import Path

FO_DELETE = 3
FOF_SILENT = 0x0004
FOF_NOCONFIRMATION = 0x0010
FOF_ALLOWUNDO = 0x0040  # this flag is what makes it the Recycle Bin instead of a permanent delete
FOF_NOERRORUI = 0x0400


class SHFILEOPSTRUCTW(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND), ("wFunc", wintypes.UINT), ("pFrom", wintypes.LPCWSTR), ("pTo", wintypes.LPCWSTR),
        ("fFlags", ctypes.c_uint16), ("fAnyOperationsAborted", wintypes.BOOL), ("hNameMappings", ctypes.c_void_p),
        ("lpszProgressTitle", wintypes.LPCWSTR),
    ]


def send_to_recycle_bin(paths: list[Path]) -> None:
    """Raises OSError if Windows refuses (e.g. a file is open in another program)."""
    if not paths:
        return
    # Windows wants every path separated by \0 and the list ended by an extra \0.
    joined = "\0".join(str(p) for p in paths) + "\0\0"
    op = SHFILEOPSTRUCTW(wFunc=FO_DELETE, pFrom=joined,
                         fFlags=FOF_ALLOWUNDO | FOF_NOCONFIRMATION | FOF_SILENT | FOF_NOERRORUI)
    code = ctypes.windll.shell32.SHFileOperationW(ctypes.byref(op))
    if code or op.fAnyOperationsAborted:
        raise OSError(f"the Recycle Bin refused (code {code}); is something still open in another program?")
