import typer

from autodocstrings import __version__

app = typer.Typer(
    name="autodoc",
    help="Track docstring staleness across a codebase. Deterministic, no LLM calls.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"autodoc {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="Show version and exit."
    ),
) -> None:
    """autodoc: deterministic docstring staleness tracker."""


if __name__ == "__main__":
    app()
