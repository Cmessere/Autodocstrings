"""Builds the `status`/`diff` JSON payloads documented in docs/agent-contract.md."""

from __future__ import annotations

from pathlib import Path

from autodocstrings.adapters import get_adapter
from autodocstrings.config import Config
from autodocstrings.state import State, compute_status
from autodocstrings.symbols import Symbol

AGENT_CONTRACT_VERSION = 1


def build_status_entries(state: State) -> list[dict]:
    """Flatten `State` into the list of symbol records used by `status --json`."""
    entries: list[dict] = []
    for relpath, file_state in sorted(state.files.items()):
        for qualified_name, symbol in sorted(file_state.symbols.items()):
            entries.append(
                {
                    "file": relpath,
                    "qualified_name": qualified_name,
                    "status": compute_status(symbol),
                    "code_hash": symbol.code_hash,
                    "signature_hash": symbol.signature_hash,
                    "doc_hash": symbol.doc_hash,
                    "approved_code_hash": symbol.approved_code_hash,
                    "approved_signature_hash": symbol.approved_signature_hash,
                    "updated_at": symbol.updated_at,
                }
            )
    return entries


class DiffTargetNotFound(Exception):
    pass


def _parse_target_symbols(
    root: Path, relpath: str, qualified_name: str | None, config: Config
) -> list[Symbol]:
    language = config.languages.get(Path(relpath).suffix)
    if language is None:
        raise DiffTargetNotFound(f"No language configured for file extension of {relpath!r}")
    file_path = root / relpath
    if not file_path.is_file():
        raise DiffTargetNotFound(f"No such file: {relpath!r}")
    source = file_path.read_text(encoding="utf-8")
    symbols = get_adapter(language).parse(source, relpath)
    if qualified_name is not None:
        symbols = [s for s in symbols if s.qualified_name == qualified_name]
        if not symbols:
            raise DiffTargetNotFound(f"No symbol {qualified_name!r} found in {relpath!r}")
    return symbols


def build_diff_entries(
    root: Path, relpath: str, qualified_name: str | None, config: Config, state: State
) -> list[dict]:
    """What changed in one symbol (or every symbol in a file) since its last approval."""
    fresh_symbols = _parse_target_symbols(root, relpath, qualified_name, config)
    file_state = state.files.get(relpath)
    entries: list[dict] = []
    for symbol in fresh_symbols:
        previous = file_state.symbols.get(symbol.qualified_name) if file_state is not None else None
        if previous is None:
            status = (
                "ignored" if symbol.ignored else ("stale" if symbol.docstring else "never_started")
            )
            body_changed = True
            signature_changed = True
        else:
            status = compute_status(previous)
            body_changed = previous.approved_code_hash != symbol.code_hash
            signature_changed = (
                previous.approved_signature_hash is not None
                and previous.approved_signature_hash != symbol.signature_hash
            )
        entries.append(
            {
                "file": relpath,
                "qualified_name": symbol.qualified_name,
                "kind": symbol.kind,
                "status": status,
                "body_changed": body_changed,
                "signature_changed": signature_changed,
                "has_docstring": symbol.docstring is not None,
                "signature": symbol.signature,
                "docstring": symbol.docstring.text if symbol.docstring else None,
            }
        )
    return entries
