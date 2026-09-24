"""Benchmark xlsreport against triage on the same synthetic tree.

Measures wall time, peak committed memory, and files/sec for each tool, and
checks every run's output against the generator's ground-truth manifest — a
fast wrong answer is not a win.

Usage:
    python benchmarks/run.py --tree <path> --manifest <path> --out benchmarks/results.md
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

DEFAULT_XLSREPORT = REPO / "python" / ".venv" / "Scripts" / "xlsreport.exe"
DEFAULT_XLSREPORT_POSIX = REPO / "python" / ".venv" / "bin" / "xlsreport"
DEFAULT_TRIAGE = REPO / "cpp" / "build" / "triage.exe"
DEFAULT_TRIAGE_POSIX = REPO / "cpp" / "build" / "triage"


# ---------------------------------------------------------------------------
# Peak memory
# ---------------------------------------------------------------------------

MEMORY_METRIC = "peak commit"

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    # Why a job object rather than GetProcessMemoryInfo / Get-Process:
    # on this host the kernel working-set counters read ~5 MiB for *every*
    # process, including a control that allocated and dirtied 300 MiB. ctypes
    # and PowerShell agree with each other because they read the same broken
    # counter. The job object's PeakProcessMemoryUsed tracks commit charge and
    # was validated against 200 MiB and 400 MiB control allocations
    # (reporting 208.6 MiB and 409.0 MiB).
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _JOB_EXTENDED_LIMIT_INFORMATION = 9

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_ulonglong),
            ("WriteOperationCount", ctypes.c_ulonglong),
            ("OtherOperationCount", ctypes.c_ulonglong),
            ("ReadTransferCount", ctypes.c_ulonglong),
            ("WriteTransferCount", ctypes.c_ulonglong),
            ("OtherTransferCount", ctypes.c_ulonglong),
        ]

    class _BasicLimitInformation(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_longlong),
            ("PerJobUserTimeLimit", ctypes.c_longlong),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _ExtendedLimitInformation(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimitInformation),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    def new_probe():
        return _kernel32.CreateJobObjectW(None, None)

    def attach_probe(probe, proc: subprocess.Popen) -> None:
        _kernel32.AssignProcessToJobObject(probe, wintypes.HANDLE(int(proc._handle)))

    def read_probe(probe) -> int:
        info = _ExtendedLimitInformation()
        returned = wintypes.DWORD(0)
        ok = _kernel32.QueryInformationJobObject(
            probe,
            _JOB_EXTENDED_LIMIT_INFORMATION,
            ctypes.byref(info),
            ctypes.sizeof(info),
            ctypes.byref(returned),
        )
        return int(info.PeakProcessMemoryUsed) if ok else 0

    def close_probe(probe) -> None:
        _kernel32.CloseHandle(probe)

else:  # pragma: no cover - the benchmark was run on Windows
    import resource

    def new_probe():
        return resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss

    def attach_probe(probe, proc: subprocess.Popen) -> None:
        return None

    def read_probe(probe) -> int:
        """ru_maxrss is a high-water mark across all reaped children, so take
        the delta above the mark that existed before this run started."""
        now = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        scale = 1 if sys.platform == "darwin" else 1024
        return max(int(now) - int(probe), 0) * scale

    def close_probe(probe) -> None:
        return None


@dataclass
class Run:
    wall_seconds: float
    peak_bytes: int
    payload: dict


def execute(cmd: list[str]) -> Run:
    probe = new_probe()
    started = time.perf_counter()
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    attach_probe(probe, proc)
    out, err = proc.communicate()
    elapsed = time.perf_counter() - started
    peak = read_probe(probe)
    close_probe(probe)
    if proc.returncode != 0:
        raise SystemExit(
            f"command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"{err.decode(errors='replace')}"
        )
    return Run(elapsed, peak, json.loads(out.decode().strip()))


def verify(payload: dict, manifest: dict) -> list[str]:
    """Return a list of mismatches against ground truth (empty means correct)."""
    checks = [
        ("total_files", manifest["total_files"]),
        ("total_bytes", manifest["total_bytes"]),
        ("distinct_contents", manifest["distinct_contents"]),
        ("duplicate_groups", manifest["duplicate_groups"]),
        ("redundant_copies", manifest["redundant_copies"]),
    ]
    problems = []
    for key, expected in checks:
        actual = payload.get(key)
        if actual != expected:
            problems.append(f"{key}: got {actual:,}, expected {expected:,}")
    return problems


def mib(value: float) -> float:
    return value / 1024.0 / 1024.0


def table(headers: list[str], body: list[list[str]]) -> str:
    line1 = "| " + " | ".join(headers) + " |"
    line2 = "| " + " | ".join("---" for _ in headers) + " |"
    rest = ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join([line1, line2, *rest])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tree", required=True, type=Path)
    ap.add_argument("--manifest", required=True, type=Path)
    ap.add_argument("--repeat", type=int, default=5)
    ap.add_argument("--warmup", type=int, default=1)
    ap.add_argument("--out", type=Path, default=None, help="write a markdown report here")
    ap.add_argument("--xlsreport", type=Path, default=None)
    ap.add_argument("--triage", type=Path, default=None)
    args = ap.parse_args()

    xlsreport = args.xlsreport or (
        DEFAULT_XLSREPORT if sys.platform == "win32" else DEFAULT_XLSREPORT_POSIX
    )
    triage = args.triage or (
        DEFAULT_TRIAGE if sys.platform == "win32" else DEFAULT_TRIAGE_POSIX
    )
    for binary in (xlsreport, triage):
        if not Path(binary).exists():
            print(f"error: missing binary {binary}", file=sys.stderr)
            return 1

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    tree = str(args.tree)

    tools = {
        "xlsreport (Python)": [str(xlsreport), "scan", tree, "--json"],
        "triage (C++)": [str(triage), "scan", tree, "--json"],
    }

    print(f"tree      : {tree}")
    print(f"files     : {manifest['total_files']:,}")
    print(f"bytes     : {manifest['total_bytes']:,} ({mib(manifest['total_bytes']):.1f} MiB)")
    print(f"warmup    : {args.warmup}   timed runs: {args.repeat}")
    print()

    # Warm the OS page cache so whichever tool runs first is not penalised for
    # pulling 500 MiB off disk on the other's behalf.
    for name, cmd in tools.items():
        for _ in range(args.warmup):
            print(f"  warmup {name} ...")
            execute(cmd)

    results: dict[str, list[Run]] = {name: [] for name in tools}
    problems: dict[str, list[str]] = {}

    # Alternate the tools each round so any machine drift hits both equally.
    for round_index in range(args.repeat):
        for name, cmd in tools.items():
            run = execute(cmd)
            results[name].append(run)
            issues = verify(run.payload, manifest)
            if issues:
                problems.setdefault(name, []).extend(issues)
            print(
                f"  round {round_index + 1}/{args.repeat}  {name:<20} "
                f"{run.wall_seconds:7.3f}s  peak {mib(run.peak_bytes):7.1f} MiB"
            )
    print()

    total_files = manifest["total_files"]
    rows = []
    for name, runs in results.items():
        walls = [r.wall_seconds for r in runs]
        best = min(walls)
        payload = runs[0].payload
        rows.append(
            {
                "tool": name,
                "best": best,
                "median": statistics.median(walls),
                "worst": max(walls),
                "peak_mib": mib(max(r.peak_bytes for r in runs)),
                "files_per_sec": total_files / best,
                "walk": payload["walk_seconds"],
                "hash": payload["hash_seconds"],
                "hashed_files": payload["hashed_files"],
                "hashed_bytes": payload["hashed_bytes"],
                "correct": name not in problems,
            }
        )

    main_table = table(
        ["Tool", "Best", "Median", "Worst", "Peak commit", "Files/sec", "Correct"],
        [
            [
                r["tool"],
                f"{r['best']:.3f} s",
                f"{r['median']:.3f} s",
                f"{r['worst']:.3f} s",
                f"{r['peak_mib']:.1f} MiB",
                f"{r['files_per_sec']:,.0f}",
                "yes" if r["correct"] else "NO",
            ]
            for r in rows
        ],
    )

    phase_table = table(
        ["Tool", "Walk", "Hash", "Files hashed", "Bytes hashed"],
        [
            [
                r["tool"],
                f"{r['walk']:.3f} s",
                f"{r['hash']:.3f} s",
                f"{r['hashed_files']:,}",
                f"{mib(r['hashed_bytes']):.1f} MiB",
            ]
            for r in rows
        ],
    )

    print(main_table)
    print()
    print(phase_table)

    if problems:
        print()
        print("CORRECTNESS FAILURES:")
        for name, issues in problems.items():
            for issue in sorted(set(issues)):
                print(f"  {name}: {issue}")

    if args.out:
        write_report(args, manifest, main_table, phase_table)
        print()
        print(f"wrote {args.out}")

    return 1 if problems else 0


KEEP_MARKER = "<!-- keep-below: hand-written analysis, not regenerated -->"


def write_report(args, manifest: dict, main_table: str, phase_table: str) -> None:
    # Anything below KEEP_MARKER in an existing report is authored by hand, so
    # carry it across instead of clobbering it on every run.
    carried = ""
    if args.out.exists():
        previous = args.out.read_text(encoding="utf-8")
        if KEEP_MARKER in previous:
            carried = "\n" + previous[previous.index(KEEP_MARKER) :].rstrip() + "\n"

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    fence = "```"
    lines = [
        "# Benchmark results",
        "",
        f"Generated by `benchmarks/run.py` on {stamp}. Every number here was",
        "measured on the machine described below. None are estimated.",
        "",
        "## Environment",
        "",
        "| Field | Value |",
        "| --- | --- |",
        f"| OS | {platform.platform()} |",
        f"| CPU | {platform.processor() or 'unknown'} |",
        f"| Python | {platform.python_version()} |",
        (
            f"| Tree | {manifest['total_files']:,} files,"
            f" {mib(manifest['total_bytes']):.1f} MiB,"
            f" {manifest['directories']:,} directories |"
        ),
        (
            f"| Duplicates | {manifest['duplicate_groups']:,} groups,"
            f" {manifest['redundant_copies']:,} redundant copies |"
        ),
        f"| Seed | {manifest['seed']} |",
        f"| Runs | {args.warmup} warmup + {args.repeat} timed, tools alternated, page cache warm |",
        "",
        "## Wall time, memory, throughput",
        "",
        main_table,
        "",
        f"`Files/sec` uses each tool's best run over all {manifest['total_files']:,} files.",
        "`Correct` means every timed run matched the generator manifest exactly.",
        "",
        "`Peak commit` is the job object PeakProcessMemoryUsed counter. The kernel",
        "working-set counters are NOT usable on this host: GetProcessMemoryInfo and",
        "PowerShell Get-Process both report ~5 MiB for every process, including a",
        "control that allocated and dirtied 300 MiB. The job-object counter was",
        "validated against 200 MiB and 400 MiB controls (208.6 and 409.0 MiB).",
        "",
        "## Phase breakdown",
        "",
        "Each tool reports its own internal timing for the two phases.",
        "",
        phase_table,
        "",
        "## Reproducing",
        "",
        fence + "bash",
        (
            "python benchmarks/generate_tree.py --out <tree> --files 50000"
            f" --dup-groups 2000 --seed {manifest['seed']}"
        ),
        (
            "python benchmarks/run.py --tree <tree>"
            " --manifest <tree>_manifest.json --out benchmarks/results.md"
        ),
        fence,
        "",
    ]
    args.out.write_text("\n".join(lines) + carried, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
