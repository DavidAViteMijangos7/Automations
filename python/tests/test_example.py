"""Example test. Replace with real tests for your tool."""

from typer.testing import CliRunner

from package_name import __version__
from package_name.__main__ import app

runner = CliRunner()


def test_version() -> None:
    assert __version__ == "0.1.0"


def test_hello_default() -> None:
    result = runner.invoke(app, ["hello"])
    assert result.exit_code == 0
    assert "Hello, world!" in result.stdout


def test_hello_with_name() -> None:
    result = runner.invoke(app, ["hello", "--name", "David"])
    assert result.exit_code == 0
    assert "Hello, David!" in result.stdout
