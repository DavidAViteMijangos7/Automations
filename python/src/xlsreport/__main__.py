"""CLI entrypoint. Replace with your actual tool's logic."""

import typer

app = typer.Typer(help="xlsreport — one-line description.")


@app.callback()
def callback() -> None:
    """xlsreport — one-line description."""


@app.command()
def hello(name: str = "world") -> None:
    """Example command. Replace me."""
    typer.echo(f"Hello, {name}!")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
