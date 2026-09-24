"""CLI entrypoint for xlsreport."""

from __future__ import annotations

import json as jsonlib

import typer

from xlsreport.scan import scan as run_scan

app = typer.Typer(help="xlsreport — find exact duplicate files in a directory tree.")


@app.callback()
def callback() -> None:
    """xlsreport — find exact duplicate files in a directory tree."""


@app.command()
def scan(
    root: str,
    json: bool = typer.Option(False, "--json", help="Emit machine-readable JSON."),
) -> None:
    """Scan ROOT for exact duplicate files."""
    result = run_scan(root)
    if json:
        typer.echo(jsonlib.dumps(result.as_dict()))
        return
    data = result.as_dict()
    typer.echo(f"files scanned    : {data['total_files']:,}")
    typer.echo(f"bytes scanned    : {data['total_bytes']:,}")
    typer.echo(f"distinct contents: {data['distinct_contents']:,}")
    typer.echo(f"duplicate groups : {data['duplicate_groups']:,}")
    typer.echo(f"redundant copies : {data['redundant_copies']:,}")
    typer.echo(f"reclaimable bytes: {data['redundant_bytes']:,}")
    typer.echo(f"elapsed          : {data['total_seconds']:.3f}s")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
