"""Tests for the duplicate scanner."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from xlsreport import __version__
from xlsreport.__main__ import app
from xlsreport.scan import scan

runner = CliRunner()


def build_tree(root: Path) -> None:
    """Three copies of A, two of B, one unique, one unique-by-size."""
    (root / "nested" / "deep").mkdir(parents=True)
    (root / "a1.txt").write_bytes(b"AAAA")
    (root / "nested" / "a2.txt").write_bytes(b"AAAA")
    (root / "nested" / "deep" / "a3.txt").write_bytes(b"AAAA")
    (root / "b1.bin").write_bytes(b"BBBB")
    (root / "nested" / "b2.bin").write_bytes(b"BBBB")
    (root / "c1.log").write_bytes(b"CCCC")
    (root / "nested" / "deep" / "d1.dat").write_bytes(b"DDDDDDDDDD")


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_scan_counts(tmp_path: Path) -> None:
    build_tree(tmp_path)
    result = scan(str(tmp_path))
    assert result.total_files == 7
    assert result.total_bytes == 4 * 6 + 10
    # A(3) + B(2) + C(1) + D(1)
    assert result.distinct_contents == 4
    assert result.duplicate_groups == 2
    assert result.redundant_copies == 3
    assert result.redundant_bytes == 4 * 3


def test_scan_skips_unique_sizes(tmp_path: Path) -> None:
    """A size seen once is never hashed."""
    build_tree(tmp_path)
    result = scan(str(tmp_path))
    # d1.dat is the only 10-byte file, so it is skipped by the size filter.
    assert result.hashed_files == 6


def test_empty_tree(tmp_path: Path) -> None:
    result = scan(str(tmp_path))
    assert result.total_files == 0
    assert result.duplicate_groups == 0
    assert result.distinct_contents == 0


def test_cli_json(tmp_path: Path) -> None:
    build_tree(tmp_path)
    outcome = runner.invoke(app, ["scan", str(tmp_path), "--json"])
    assert outcome.exit_code == 0
    payload = json.loads(outcome.stdout)
    assert payload["tool"] == "xlsreport"
    assert payload["total_files"] == 7
    assert payload["duplicate_groups"] == 2
    assert payload["redundant_copies"] == 3
