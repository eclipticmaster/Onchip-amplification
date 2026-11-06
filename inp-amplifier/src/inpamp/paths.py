"""Allocate separate output directories for repeated command-line operations."""
from datetime import datetime
from pathlib import Path
import re


def output_directory(requested=None, *, root=Path("results"), label="run", now=None):
    """Reserve an empty directory, retaining existing results on collisions.

    Explicit paths are used directly when available. An occupied explicit path
    gets a timestamped sibling. Automatic paths always contain the local date,
    time and UTC offset. Timestamped paths use exclusive mkdir reservations.
    """
    timestamp = (now or datetime.now().astimezone()).strftime("%Y-%m-%d_%H-%M-%S%z")
    if requested is not None:
        requested = Path(requested).expanduser().resolve()
        if requested.is_file():
            raise ValueError(f"Choose a directory for --output; a file exists at {requested}")
        try:
            requested.mkdir(parents=True)
            return requested
        except FileExistsError:
            if not any(requested.iterdir()):
                return requested
        parent, prefix = requested.parent, requested.name
    else:
        parent = Path(root).expanduser().resolve()
        prefix = re.sub(r"[^A-Za-z0-9_.-]+", "-", label).strip(".-") or "run"
    for index in range(1, 100_000):
        suffix = "" if index == 1 else f"-{index:02d}"
        candidate = parent / f"{prefix}-{timestamp}{suffix}"
        try:
            candidate.mkdir(parents=True)
            return candidate
        except FileExistsError:
            continue
    raise RuntimeError(f"Unable to reserve an output directory under {parent}")
