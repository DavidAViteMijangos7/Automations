"""CLI entrypoint. Replace with your actual tool's logic."""

import typer

app = typer.Typer(help="package_name — one-line description.")


@app.command()
def hello(name: str = "world") -> None:
    """Example command. Replace me."""
    typer.echo(f"Hello, {name}!")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
