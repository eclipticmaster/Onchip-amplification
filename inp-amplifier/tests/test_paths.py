"""Repeated commands reserve separate directories and preserve saved results."""
from datetime import datetime, timedelta, timezone

import pytest

from inpamp.paths import output_directory


NOW = datetime(2026, 11, 5, 14, 3, 7, tzinfo=timezone(timedelta(hours=-8)))


def test_timestamp_and_same_second_collisions(tmp_path):
    first = output_directory(root=tmp_path, label="mode", now=NOW)
    (first / "native.mat").write_bytes(b"previous native results")
    second = output_directory(root=tmp_path, label="mode", now=NOW)
    assert first.name == "mode-2026-11-05_14-03-07-0800"
    assert second.name == first.name + "-02"
    assert (first / "native.mat").read_bytes() == b"previous native results"
    assert second.is_dir() and not list(second.iterdir())


def test_repeated_explicit_output_uses_timestamped_siblings(tmp_path):
    requested = tmp_path / "native-mode"
    first = output_directory(requested, now=NOW)
    (first / "saved.lms").write_bytes(b"keep this run")
    second = output_directory(requested, now=NOW)
    (second / "saved.lms").write_bytes(b"keep the second run")
    third = output_directory(requested, now=NOW)
    assert first == requested
    assert second.name == "native-mode-2026-11-05_14-03-07-0800"
    assert third.name == second.name + "-02"
    assert (requested / "saved.lms").read_bytes() == b"keep this run"
    assert (second / "saved.lms").read_bytes() == b"keep the second run"


def test_output_file_is_preserved(tmp_path):
    path = tmp_path / "notes.txt"
    path.write_text("my notes")
    with pytest.raises(ValueError, match="a file exists"):
        output_directory(path, now=NOW)
    assert path.read_text() == "my notes"
