"""Ensure the `ffmpeg`/`ffprobe` binaries are discoverable on PATH.

On Windows, tools like `ffmpeg-downloader` update the *persistent* user PATH, but
already-running shells (and therefore the backend process) do not see it until
restarted. This resolves the binaries from the registry PATH and known install
locations, and prepends the directory to the current process PATH.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

_EXE = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"


def _registry_path_dirs() -> list[str]:
    if os.name != "nt":
        return []
    import winreg

    dirs: list[str] = []
    for root, subkey in (
        (winreg.HKEY_CURRENT_USER, "Environment"),
        (
            winreg.HKEY_LOCAL_MACHINE,
            r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment",
        ),
    ):
        try:
            with winreg.OpenKey(root, subkey) as key:
                value, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        dirs.extend(part for part in value.split(os.pathsep) if part)
    return dirs


def _candidate_dirs() -> list[str]:
    dirs = _registry_path_dirs()
    local = os.environ.get("LOCALAPPDATA")
    if local:
        # Default install location used by `ffdl install` (ffmpeg-downloader).
        dirs.append(str(Path(local) / "ffmpegio" / "ffmpeg-downloader" / "ffmpeg" / "bin"))
    return dirs


def ensure_ffmpeg_on_path() -> str | None:
    """Return the directory that provides ffmpeg, adding it to PATH if needed."""
    found = shutil.which("ffmpeg")
    if found:
        return str(Path(found).parent)

    for directory in _candidate_dirs():
        if (Path(directory) / _EXE).exists():
            os.environ["PATH"] = directory + os.pathsep + os.environ.get("PATH", "")
            return directory
    return None
