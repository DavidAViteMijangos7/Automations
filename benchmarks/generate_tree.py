"""Build a synthetic file tree for benchmarking xlsreport and triage.

Deterministic: the same --seed always produces a byte-identical tree, so both
tools are measured against exactly the same input.

Writes a ground-truth manifest (outside the tree, so scanners never see it)
recording the exact duplicate structure. That lets the benchmark check each
tool for *correctness*, not just speed.

Usage:
    python generate_tree.py --out benchmarks/tree
    python generate_tree.py --out D:/scratch/tree --files 50000 --seed 1234
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Tunables. Weights are relative; they do not need to sum to 1.
# ---------------------------------------------------------------------------

EXTENSIONS: list[tuple[str, float]] = [
    (".txt", 20),
    (".log", 15),
    (".csv", 12),
    (".json", 12),
    (".md", 8),
    (".xml", 6),
    (".yaml", 5),
    (".bin", 8),
    (".dat", 6),
    (".cfg", 4),
    (".ini", 4),
]

# (label, min_bytes, max_bytes, weight)
SIZE_CLASSES: list[tuple[str, int, int, float]] = [
    ("small", 64, 4 * 1024, 78.0),
    ("medium", 4 * 1024, 32 * 1024, 18.0),
    ("large", 32 * 1024, 192 * 1024, 3.7),
    ("xlarge", 192 * 1024, 768 * 1024, 0.3),
]

# Directory fan-out: 12 * 10 * 10 == 1200 leaf directories.
FANOUT = (12, 10, 10)


def build_dirs(root: Path, rng: random.Random) -> list[Path]:
    """Create the nested folder skeleton and return every directory in it.

    Files land at all depths, not just the leaves, so the walk has to recurse
    through a realistically uneven tree.
    """
    dirs: list[Path] = [root]
    level1 = [root / f"dept_{i:02d}" for i in range(FANOUT[0])]
    for d1 in level1:
        dirs.append(d1)
        for j in range(FANOUT[1]):
            d2 = d1 / f"project_{j:02d}"
            dirs.append(d2)
            for k in range(FANOUT[2]):
                d3 = d2 / f"batch_{k:02d}"
                dirs.append(d3)
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def weighted_pick(rng: random.Random, items: list, weights: list[float]):
    return rng.choices(items, weights=weights, k=1)[0]


def pick_size(rng: random.Random) -> int:
    labels = [c[0] for c in SIZE_CLASSES]
    weights = [c[3] for c in SIZE_CLASSES]
    label = weighted_pick(rng, labels, weights)
    _, lo, hi, _ = next(c for c in SIZE_CLASSES if c[0] == label)
    return rng.randint(lo, hi)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", required=True, type=Path, help="tree root to create")
    ap.add_argument("--manifest", type=Path, default=None,
                    help="ground-truth JSON (default: <out>_manifest.json, beside the tree)")
    ap.add_argument("--files", type=int, default=50_000, help="total files to create")
    ap.add_argument("--dup-groups", type=int, default=2_000,
                    help="number of distinct contents that get duplicated")
    ap.add_argument("--seed", type=int, default=1234)
    ap.add_argument("--force", action="store_true", help="delete --out if it exists")
    args = ap.parse_args()

    root: Path = args.out
    manifest_path: Path = args.manifest or root.with_name(root.name + "_manifest.json")

    if root.exists():
        if not args.force:
            print(f"error: {root} already exists (pass --force to replace)", file=sys.stderr)
            return 1
        shutil.rmtree(root)

    rng = random.Random(args.seed)
    t0 = time.perf_counter()

    print(f"creating directory skeleton under {root} ...")
    dirs = build_dirs(root, rng)

    # ---- Decide the duplicate structure up front -------------------------
    # Each duplicate group is one distinct blob written to 2..5 paths.
    group_sizes = [rng.randint(2, 5) for _ in range(args.dup_groups)]
    dup_file_count = sum(group_sizes)
    if dup_file_count >= args.files:
        print("error: --dup-groups too large for --files", file=sys.stderr)
        return 1
    unique_file_count = args.files - dup_file_count

    print(f"plan: {args.files:,} files = {unique_file_count:,} unique-content "
          f"+ {dup_file_count:,} across {args.dup_groups:,} duplicate groups")

    ext_names = [e[0] for e in EXTENSIONS]
    ext_weights = [e[1] for e in EXTENSIONS]

    total_bytes = 0
    counter = 0
    groups_manifest: list[dict] = []

    # ---- Duplicate groups -------------------------------------------------
    for gi, gsize in enumerate(group_sizes):
        size = pick_size(rng)
        blob = rng.randbytes(size)
        digest = hashlib.sha256(blob).hexdigest()
        ext = weighted_pick(rng, ext_names, ext_weights)
        paths: list[str] = []
        for _ in range(gsize):
            d = rng.choice(dirs)
            p = d / f"file_{counter:06d}{ext}"
            counter += 1
            p.write_bytes(blob)
            total_bytes += size
            paths.append(str(p.relative_to(root)).replace("\\", "/"))
        groups_manifest.append({
            "sha256": digest,
            "size_bytes": size,
            "copies": gsize,
            "paths": sorted(paths),
        })
        if (gi + 1) % 500 == 0:
            print(f"  ... {gi + 1:,}/{args.dup_groups:,} duplicate groups written")

    # ---- Unique files -----------------------------------------------------
    # A 16-byte unique prefix guarantees no accidental collisions with each
    # other or with the duplicate blobs.
    for i in range(unique_file_count):
        size = pick_size(rng)
        blob = counter.to_bytes(8, "little") + args.seed.to_bytes(8, "little") \
            + rng.randbytes(max(0, size - 16))
        ext = weighted_pick(rng, ext_names, ext_weights)
        d = rng.choice(dirs)
        p = d / f"file_{counter:06d}{ext}"
        counter += 1
        p.write_bytes(blob)
        total_bytes += len(blob)
        if (i + 1) % 10_000 == 0:
            print(f"  ... {i + 1:,}/{unique_file_count:,} unique files written")

    elapsed = time.perf_counter() - t0

    manifest = {
        "seed": args.seed,
        "root": str(root),
        "total_files": counter,
        "total_bytes": total_bytes,
        "directories": len(dirs),
        "unique_content_files": unique_file_count,
        "duplicate_groups": args.dup_groups,
        "files_in_duplicate_groups": dup_file_count,
        # The number of files a deduplicator could delete: every copy past the first.
        "redundant_copies": dup_file_count - args.dup_groups,
        "distinct_contents": unique_file_count + args.dup_groups,
        "generated_in_seconds": round(elapsed, 2),
        "groups": groups_manifest,
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print()
    print(f"done in {elapsed:.1f}s")
    print(f"  files           : {counter:,}")
    print(f"  bytes           : {total_bytes:,} ({total_bytes / 1024 / 1024:.1f} MiB)")
    print(f"  directories     : {len(dirs):,}")
    print(f"  distinct blobs  : {unique_file_count + args.dup_groups:,}")
    print(f"  dup groups      : {args.dup_groups:,}")
    print(f"  redundant copies: {dup_file_count - args.dup_groups:,}")
    print(f"  manifest        : {manifest_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
