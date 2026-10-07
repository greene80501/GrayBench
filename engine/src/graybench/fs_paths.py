"""Filesystem path handling for evidence that can live in deep checkouts."""

import os
from pathlib import Path


def readable_path(path: Path) -> Path:
    """Use extended Windows paths so read-only verification exceeds legacy MAX_PATH."""
    if os.name != "nt":
        return path
    absolute = os.path.abspath(path)
    if absolute.startswith("\\\\?\\"):
        return Path(absolute)
    if absolute.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + absolute[2:])
    return Path("\\\\?\\" + absolute)
