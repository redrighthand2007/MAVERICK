"""Create, list and extract .zip / .tar archives, optionally AES-encrypted. Ported from VIT-OS-SMART-ARCHIVE-AGENT.

Nothing here overwrites: a new archive or extracted file must not exist yet.
"""
import os
import tarfile
import zipfile
from pathlib import Path

import pyzipper

from maverick.core.agent_base import Result
from maverick.core.safety import SafetyError, is_inside, require_existing, require_not_protected, to_path
from maverick.core.units import human_size

TAR_MODES = {".tar": "w", ".tgz": "w:gz", ".gz": "w:gz", ".bz2": "w:bz2", ".xz": "w:xz"}


def default_output(source: Path, fmt: str) -> Path:
    """D:\\work -> D:\\work.zip, notes.txt -> notes.zip (next to the source)."""
    stem = source.name if source.is_dir() else source.stem
    return source.parent / f"{stem}.{fmt}"


def plan_create(source: str, output: str = "", fmt: str = "zip") -> tuple[Path, Path]:
    src = require_existing(source)
    require_not_protected(src)
    out = to_path(output) if output else default_output(src, fmt)
    if out.is_dir():
        out = out / default_output(src, fmt).name
    if not out.parent.exists():
        raise SafetyError(f"Folder does not exist: {out.parent}")
    if out.exists():
        raise SafetyError(f"{out} already exists; MAVERICK never overwrites.")
    if src.is_dir() and is_inside(out, src):
        raise SafetyError("The archive can't be saved inside the folder being archived.")
    require_not_protected(out)
    return src, out


def files_under(src: Path) -> list[tuple[Path, str]]:
    """(file on disk, name inside the archive). A folder keeps its own name as the top level."""
    if src.is_file():
        return [(src, src.name)]
    items = []
    for root, _, names in os.walk(src):
        for name in names:
            path = Path(root, name)
            items.append((path, str(path.relative_to(src.parent)).replace("\\", "/")))
    return items


def create(source: str, output: str = "", fmt: str = "zip", password: str = "") -> Result:
    src, out = plan_create(source, output, fmt)
    items = files_under(src)
    suffix = "".join(out.suffixes[-2:]).lower()
    if out.suffix.lower() == ".zip":
        if password:
            with pyzipper.AESZipFile(out, "w", compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(password.encode())
                for path, name in items:
                    zf.write(path, name)
        else:
            with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
                for path, name in items:
                    zf.write(path, name)
    else:
        if password:
            raise SafetyError("Only .zip archives can have a password.")
        mode = TAR_MODES.get(out.suffix.lower()) if suffix != ".tar.gz" else "w:gz"
        if not mode:
            raise SafetyError(f"Unknown archive type: {out.name} (use .zip, .tar, .tar.gz, .tar.bz2 or .tar.xz)")
        with tarfile.open(out, mode) as tf:
            for path, name in items:
                tf.add(path, name)
    before = sum(p.stat().st_size for p, _ in items)
    after = out.stat().st_size
    lock = ", AES-256 encrypted" if password else ""
    return Result(True, f"Created {out} ({len(items)} files, {human_size(before)} -> {human_size(after)}{lock}).",
                  {"archive": str(out), "files": len(items), "output": str(out)})


def is_encrypted(archive: Path) -> bool:
    if not zipfile.is_zipfile(archive):
        return False
    with zipfile.ZipFile(archive) as zf:
        return any(info.flag_bits & 0x1 for info in zf.infolist())


def entries(archive: Path) -> list[tuple[str, int]]:
    """(name, size) of every file inside, without extracting anything."""
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            return [(i.filename, i.file_size) for i in zf.infolist() if not i.is_dir()]
    if tarfile.is_tarfile(archive):
        with tarfile.open(archive, "r:*") as tf:
            return [(m.name, m.size) for m in tf.getmembers() if m.isfile()]
    raise SafetyError(f"{archive.name} is not a .zip or .tar archive.")


def list_contents(archive: str) -> Result:
    path = require_existing(archive)
    items = entries(path)
    lock = " (password protected)" if is_encrypted(path) else ""
    lines = [f"{path.name}{lock}: {len(items)} files, {human_size(sum(s for _, s in items))} unpacked"]
    lines += [f"  - {name} ({human_size(size)})" for name, size in items[:30]]
    if len(items) > 30:
        lines.append(f"  ... and {len(items) - 30} more")
    return Result(True, "\n".join(lines), {"files": [n for n, _ in items]})


def plan_extract(archive: str, destination: str = "") -> tuple[Path, Path]:
    path = require_existing(archive)
    if not path.is_file():
        raise SafetyError(f"{path} is a folder, not an archive.")
    stem = path.name.split(".")[0]
    dest = to_path(destination) if destination else path.parent / stem
    require_not_protected(dest)
    if dest.exists() and not dest.is_dir():
        raise SafetyError(f"{dest} is a file; extract into a folder.")
    if not dest.parent.exists():
        raise SafetyError(f"Folder does not exist: {dest.parent}")
    root = dest.resolve()
    for name, _ in entries(path):
        # Zip Slip: a name like "..\\..\\Windows\\evil.dll" would land outside the destination.
        target = (root / name).resolve()
        if not is_inside(target, root):
            raise SafetyError(f"The archive contains '{name}', which would escape {root}. Nothing was extracted.")
        if target.exists():
            raise SafetyError(f"{target} already exists; MAVERICK never overwrites.")
    return path, dest


def extract(archive: str, destination: str = "", password: str = "") -> Result:
    path, dest = plan_extract(archive, destination)
    if zipfile.is_zipfile(path):
        with pyzipper.AESZipFile(path) as zf:  # reads plain and AES zips alike
            if password:
                zf.setpassword(password.encode())
            files = [i for i in zf.infolist() if not i.is_dir()]
            try:
                if files:
                    zf.read(files[0])  # check the password before anything is written
            except RuntimeError as exc:
                raise SafetyError(f"Could not open {path.name}: wrong password?") from exc
            dest.mkdir(exist_ok=True)
            zf.extractall(dest)
    else:
        dest.mkdir(exist_ok=True)
        with tarfile.open(path, "r:*") as tf:
            # The "data" filter refuses links, devices and absolute paths: the tar version of the Zip Slip guard.
            tf.extractall(dest, filter="data")
    count = len(entries(path))
    return Result(True, f"Extracted {count} files from {path.name} into {dest}.", {"destination": str(dest), "files": count, "output": str(dest)})
