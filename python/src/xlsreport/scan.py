"""Duplicate-file scanner.

Deliberately mirrors cpp/src/scan.cpp step for step so the two are comparable:

  1. recursive walk, collecting (path, size)
  2. bucket by size; a size seen once cannot be a duplicate, so skip it
  3. SHA-256 the survivors, streaming in 64 KiB chunks
  4. bucket by digest

Single-threaded on purpose. See benchmarks/results.md.
"""

from __future__ import annotations

import hashlib
import os
import time
from collections import defaultdict
from dataclasses import dataclass

CHUNK_BYTES = 64 * 1024


@dataclass
class ScanResult:
    total_files: int
    total_bytes: int
    hashed_files: int
    hashed_bytes: int
    distinct_contents: int
    duplicate_groups: int
    redundant_copies: int
    redundant_bytes: int
    walk_seconds: float
    hash_seconds: float
    total_seconds: float

    def as_dict(self) -> dict:
        return {
            "tool": "xlsreport",
            "total_files": self.total_files,
            "total_bytes": self.total_bytes,
            "hashed_files": self.hashed_files,
            "hashed_bytes": self.hashed_bytes,
            "distinct_contents": self.distinct_contents,
            "duplicate_groups": self.duplicate_groups,
            "redundant_copies": self.redundant_copies,
            "redundant_bytes": self.redundant_bytes,
            "walk_seconds": round(self.walk_seconds, 4),
            "hash_seconds": round(self.hash_seconds, 4),
            "total_seconds": round(self.total_seconds, 4),
        }


def walk(root: str) -> list[tuple[str, int]]:
    """Collect (path, size) for every regular file under root."""
    found: list[tuple[str, int]] = []
    stack: list[str] = [root]
    while stack:
        current = stack.pop()
        try:
            with os.scandir(current) as it:
                for entry in it:
                    try:
                        if entry.is_dir(follow_symlinks=False):
                            stack.append(entry.path)
                        elif entry.is_file(follow_symlinks=False):
                            found.append((entry.path, entry.stat(follow_symlinks=False).st_size))
                    except OSError:
                        continue
        except OSError:
            continue
    return found


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb", buffering=0) as handle:
        while chunk := handle.read(CHUNK_BYTES):
            digest.update(chunk)
    return digest.hexdigest()


def scan(root: str) -> ScanResult:
    start = time.perf_counter()

    files = walk(root)
    after_walk = time.perf_counter()

    by_size: dict[int, list[str]] = defaultdict(list)
    for path, size in files:
        by_size[size].append(path)

    size_of: dict[str, int] = dict(files)
    solo_by_size = sum(1 for paths in by_size.values() if len(paths) == 1)

    by_digest: dict[str, list[str]] = defaultdict(list)
    hashed_files = 0
    hashed_bytes = 0
    for paths in by_size.values():
        if len(paths) < 2:
            continue
        for path in paths:
            by_digest[sha256_file(path)].append(path)
            hashed_files += 1
            hashed_bytes += size_of[path]
    end = time.perf_counter()

    duplicate_groups = 0
    redundant_copies = 0
    redundant_bytes = 0
    for digest_paths in by_digest.values():
        if len(digest_paths) > 1:
            duplicate_groups += 1
            extra = len(digest_paths) - 1
            redundant_copies += extra
            redundant_bytes += extra * size_of[digest_paths[0]]

    return ScanResult(
        total_files=len(files),
        total_bytes=sum(s for _, s in files),
        hashed_files=hashed_files,
        hashed_bytes=hashed_bytes,
        distinct_contents=solo_by_size + len(by_digest),
        duplicate_groups=duplicate_groups,
        redundant_copies=redundant_copies,
        redundant_bytes=redundant_bytes,
        walk_seconds=after_walk - start,
        hash_seconds=end - after_walk,
        total_seconds=end - start,
    )
