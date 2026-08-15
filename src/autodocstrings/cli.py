"""The `autodoc` CLI. See docs/agent-contract.md for the `--json` schemas."""

from __future__ import annotations

import json
import subprocess
from collections import Counter
from pathlib import Path

import typer

from autodocstrings import __version__
from autodocstrings.config import CONFIG_FILENAME, Config
from autodocstrings.project import Project, load_project
from autodocstrings.project_scan import scan_project
from autodocstrings.reporting import (
    AGENT_CONTRACT_VERSION,
    DiffTargetNotFound,
    build_diff_entries,
    build_status_entries,
)
from autodocstrings.state import State, approve_symbol, compute_status, now_iso

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


def _to_relpath(root: Path, raw: str) -> str:
    p = Path(raw)
    absolute = p if p.is_absolute() else (Path.cwd() / p)
    return absolute.resolve().relative_to(root).as_posix()


def _parse_target(target: str) -> tuple[str, str | None]:
    """Split `file[:qualified_name]`, tolerant of Windows drive-letter colons."""
    if ":" not in target:
        return target, None
    file_part, _, symbol_part = target.rpartition(":")
    if len(file_part) <= 1:
        return target, None
    return file_part, symbol_part


def _scope_relpaths(root: Path, path: Path) -> str:
    return path.resolve().relative_to(root).as_posix()


@app.command()
def scan(
    path: Path | None = typer.Option(
        None, "--path", help="Restrict scanning to a file or directory"
    ),
) -> None:
    """(Re)parse source and refresh state.json's hashes."""
    project = load_project()
    previous = project.load_state()
    scopes = [path] if path is not None else None
    new_state = scan_project(project.root, project.config, previous, scopes=scopes)
    project.save_state(new_state)
    total_symbols = sum(len(f.symbols) for f in new_state.files.values())
    typer.echo(f"Scanned {len(new_state.files)} file(s), {total_symbols} symbol(s) tracked.")


@app.command()
def status(
    path: Path | None = typer.Option(None, "--path", help="Restrict to a file or directory"),
    json_output: bool = typer.Option(False, "--json"),
    only: str | None = typer.Option(None, "--only", help="Comma-separated statuses to include"),
) -> None:
    """Show tracked symbols and their documentation status."""
    project = load_project()
    state = project.load_state()
    entries = build_status_entries(state)

    if path is not None:
        scope_rel = _scope_relpaths(project.root, path)
        entries = [
            e for e in entries if e["file"] == scope_rel or e["file"].startswith(scope_rel + "/")
        ]
    if only:
        wanted = {s.strip() for s in only.split(",") if s.strip()}
        entries = [e for e in entries if e["status"] in wanted]

    if json_output:
        payload = {
            "schema_version": AGENT_CONTRACT_VERSION,
            "root": str(project.root),
            "generated_at": now_iso(),
            "symbols": entries,
        }
        typer.echo(json.dumps(payload, indent=2))
        return

    if not entries:
        typer.echo("No tracked symbols match.")
        return
    for entry in entries:
        typer.echo(f"{entry['status']:<13} {entry['file']}:{entry['qualified_name']}")


@app.command()
def diff(
    target: str = typer.Argument(..., help="file[:qualified_name]"),
    json_output: bool = typer.Option(False, "--json"),
) -> None:
    """Show what changed in a symbol since its last approval."""
    project = load_project()
    state = project.load_state()
    raw_relpath, qualified_name = _parse_target(target)
    relpath = _to_relpath(project.root, raw_relpath)
    try:
        entries = build_diff_entries(project.root, relpath, qualified_name, project.config, state)
    except DiffTargetNotFound as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(1) from exc

    if json_output:
        typer.echo(
            json.dumps({"schema_version": AGENT_CONTRACT_VERSION, "symbols": entries}, indent=2)
        )
        return

    for entry in entries:
        typer.echo(f"{entry['qualified_name']} ({entry['status']})")
        typer.echo(f"  signature: {entry['signature']}")
        if entry["signature_changed"]:
            typer.echo("  ! signature changed since last approval")
        if entry["body_changed"]:
            typer.echo("  ! body changed since last approval")


@app.command()
def approve(
    target: str | None = typer.Argument(None, help="file[:qualified_name] to approve"),
    path: Path | None = typer.Option(
        None, "--path", help="Approve every tracked symbol under a file or directory"
    ),
) -> None:
    """Mark symbols' current code as matching their docs."""
    if target is None and path is None:
        typer.echo("Provide a target (file[:qualified_name]) or --path.", err=True)
        raise typer.Exit(2)

    project = load_project()
    state = project.load_state()
    approved_count = 0

    if target is not None:
        raw_relpath, qualified_name = _parse_target(target)
        relpath = _to_relpath(project.root, raw_relpath)
        file_state = state.files.get(relpath)
        if file_state is None:
            typer.echo(f"No tracked symbols in {relpath!r}.", err=True)
            raise typer.Exit(1)
        names = [qualified_name] if qualified_name is not None else list(file_state.symbols)
        for name in names:
            if name not in file_state.symbols:
                typer.echo(f"No symbol {name!r} tracked in {relpath!r}.", err=True)
                raise typer.Exit(1)
            state = approve_symbol(state, relpath, name)
            approved_count += 1
    else:
        assert path is not None
        scope_rel = _scope_relpaths(project.root, path)
        for relpath, file_state in list(state.files.items()):
            if not (relpath == scope_rel or relpath.startswith(scope_rel + "/")):
                continue
            for name in list(file_state.symbols):
                state = approve_symbol(state, relpath, name)
                approved_count += 1

    project.save_state(state)
    typer.echo(f"Approved {approved_count} symbol(s).")


def _git_staged_files(root: Path) -> list[str]:
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


@app.command()
def check(
    staged: bool = typer.Option(False, "--staged", help="Restrict to git-staged files"),
    mode: str | None = typer.Option(None, "--mode", help="Override the configured hook mode"),
) -> None:
    """Hook entrypoint: fails (in `block` mode) if tracked symbols need docs."""
    project = load_project()
    effective_mode = mode or project.config.hook.mode
    if effective_mode == "off":
        raise typer.Exit(0)

    state = project.load_state()
    if staged:
        staged_relpaths = _git_staged_files(project.root)
        scopes = [project.root / p for p in staged_relpaths if (project.root / p).is_file()]
        if scopes:
            state = scan_project(project.root, project.config, state, scopes=scopes)
            project.save_state(state)
        target_relpaths = set(staged_relpaths)
    else:
        state = scan_project(project.root, project.config, state)
        project.save_state(state)
        target_relpaths = set(state.files)

    block_on = set(project.config.hook.block_on)
    problems: list[tuple[str, str, str]] = []
    for relpath, file_state in state.files.items():
        if relpath not in target_relpaths:
            continue
        for qualified_name, symbol in file_state.symbols.items():
            symbol_status = compute_status(symbol)
            if symbol_status in block_on:
                problems.append((relpath, qualified_name, symbol_status))

    if not problems:
        raise typer.Exit(0)

    counts = Counter(status for _, _, status in problems)
    summary = ", ".join(f"{count} {status}" for status, count in sorted(counts.items()))
    scope_desc = "staged files" if staged else "scanned files"
    message = (
        f"autodocstrings: {summary} in {scope_desc}. "
        'Run "autodoc status --only stale" or ask your agent to run the autodocstrings skill.'
    )
    typer.echo(message, err=(effective_mode == "block"))
    if effective_mode == "block":
        raise typer.Exit(1)
    raise typer.Exit(0)


_VERBOSITY_EXAMPLES: dict[str, str] = {
    "minimal": '"""Capitalises the string."""',
    "standard": (
        '"""Capitalises the string.\n\n'
        "    Args:\n"
        "        value: The string to capitalise.\n\n"
        "    Returns:\n"
        "        The capitalised string.\n"
        '    """'
    ),
    "detailed": (
        '"""Capitalises the string.\n\n'
        "    Args:\n"
        "        value: The string to capitalise.\n\n"
        "    Returns:\n"
        "        The capitalised string.\n\n"
        "    Example:\n"
        '        >>> capitalise_string("hi")\n'
        "        'Hi'\n"
        '    """'
    ),
}

_NOISY_DIRS = {"node_modules", ".venv", "venv", "__pycache__", "dist", "build", ".git"}


def _detect_languages(root: Path) -> set[str]:
    defaults = Config()
    found: set[str] = set()
    for path in root.glob("**/*"):
        if not path.is_file() or any(part in _NOISY_DIRS for part in path.parts):
            continue
        language = defaults.languages.get(path.suffix)
        if language:
            found.add(language)
    return found


@app.command()
def init(
    yes: bool = typer.Option(False, "--yes", "-y", help="Accept defaults without prompting"),
) -> None:
    """Interactive wizard: detect languages, write config, run the first scan."""
    root = Path.cwd()
    config_path = root / CONFIG_FILENAME
    if (
        config_path.exists()
        and not yes
        and not typer.confirm(f"{CONFIG_FILENAME} already exists. Overwrite?", default=False)
    ):
        raise typer.Exit(0)

    detected = _detect_languages(root)
    conventions: dict[str, str] = {}
    for language in sorted(detected):
        if language == "python":
            default, options = "google", ("google", "numpy", "sphinx")
        else:
            default, options = "tsdoc", ("jsdoc", "tsdoc")
        if yes:
            conventions[language] = default
        else:
            typer.echo(f"Detected {language} files.")
            choice = typer.prompt(f"Docstring convention for {language}", default=default)
            conventions[language] = choice if choice in options else default

    if yes:
        verbosity = "standard"
    else:
        for level, example in _VERBOSITY_EXAMPLES.items():
            typer.echo(f"\n--- {level} ---\n{example}\n")
        verbosity = typer.prompt("Verbosity (minimal/standard/detailed)", default="standard")
        if verbosity not in _VERBOSITY_EXAMPLES:
            verbosity = "standard"

    hook_mode = "warn"
    if not yes:
        hook_mode = typer.prompt("Git hook mode (off/warn/block)", default="warn")
        if hook_mode not in ("off", "warn", "block"):
            hook_mode = "warn"

    config = Config(conventions=conventions, verbosity=verbosity, hook={"mode": hook_mode})  # type: ignore[arg-type]
    config_path.write_text(
        json.dumps(config.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    typer.echo(f"Wrote {config_path}")

    project = Project(root=root, config=config, config_path=config_path)
    new_state = scan_project(project.root, project.config, State())
    project.save_state(new_state)
    total_symbols = sum(len(f.symbols) for f in new_state.files.values())
    typer.echo(f"Initial scan: {len(new_state.files)} file(s), {total_symbols} symbol(s) tracked.")


_HOOK_MARKER_START = "# >>> autodocstrings hook >>>"
_HOOK_MARKER_END = "# <<< autodocstrings hook <<<"
_HOOK_BLOCK = f"{_HOOK_MARKER_START}\nautodoc check --staged\n{_HOOK_MARKER_END}\n"


def _find_git_dir(root: Path) -> Path | None:
    for directory in [root, *root.parents]:
        git_path = directory / ".git"
        if git_path.is_dir():
            return git_path
        if git_path.is_file():
            content = git_path.read_text(encoding="utf-8").strip()
            if content.startswith("gitdir:"):
                return (directory / content.split(":", 1)[1].strip()).resolve()
    return None


@app.command(name="install-hook")
def install_hook(
    force: bool = typer.Option(
        False, "--force", help="Append to an existing pre-commit hook without asking"
    ),
) -> None:
    """Write (or append to) `.git/hooks/pre-commit` to run `autodoc check --staged`."""
    project = load_project()
    git_dir = _find_git_dir(project.root)
    if git_dir is None:
        typer.echo("Not inside a git repository (no .git directory found).", err=True)
        raise typer.Exit(1)

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    hook_path = hooks_dir / "pre-commit"

    if hook_path.exists():
        existing = hook_path.read_text(encoding="utf-8")
        if _HOOK_MARKER_START in existing:
            typer.echo(f"{hook_path} already has an autodocstrings hook installed.")
            raise typer.Exit(0)
        if not force and not typer.confirm(
            f"{hook_path} already exists. Append the autodocstrings hook to it?", default=True
        ):
            raise typer.Exit(0)
        new_content = existing.rstrip("\n") + "\n\n" + _HOOK_BLOCK
    else:
        new_content = "#!/bin/sh\n" + _HOOK_BLOCK

    hook_path.write_text(new_content, encoding="utf-8", newline="\n")
    mode = hook_path.stat().st_mode
    hook_path.chmod(mode | 0o111)
    typer.echo(f"Installed pre-commit hook at {hook_path}")


if __name__ == "__main__":
    app()
