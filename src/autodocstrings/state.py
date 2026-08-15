"""The state tree: what's persisted to `state.json`, and the status engine.

Status is always **derived at read time** from the persisted hashes — it is
never itself stored, so there is nothing to keep in sync.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

STATE_VERSION = 1

Status = Literal["ignored", "never_started", "stale", "up_to_date"]


class SymbolState(BaseModel):
    """Persisted, hash-based record of one symbol's documentation state."""

    model_config = ConfigDict(extra="forbid")

    code_hash: str
    signature_hash: str
    doc_hash: str | None = None
    """Hash of the current docstring text, or None if the symbol has no docstring."""
    approved_code_hash: str | None = None
    """The code_hash as of the last `approve`. None means never approved."""
    updated_at: str
    """UTC timestamp (ISO 8601) of the last time code_hash changed. Stable across
    no-op scans so re-scanning with no changes doesn't touch this file."""
    ignored: bool = False


class FileState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: dict[str, SymbolState] = Field(default_factory=dict)


class State(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = STATE_VERSION
    files: dict[str, FileState] = Field(default_factory=dict)


def compute_status(symbol: SymbolState) -> Status:
    """Derive a symbol's status from its persisted hashes.

    - `ignored`: an inline `autodoc: ignore` marker applies.
    - `never_started`: no docstring, never approved.
    - `stale`: a docstring or an approval record exists, but the code has
      changed since (or the docstring was removed after approval).
    - `up_to_date`: documented and the approval matches the current code.
    """
    if symbol.ignored:
        return "ignored"
    has_doc = symbol.doc_hash is not None
    has_approval = symbol.approved_code_hash is not None
    if not has_doc and not has_approval:
        return "never_started"
    if not has_doc and has_approval:
        return "stale"
    if symbol.approved_code_hash != symbol.code_hash:
        return "stale"
    return "up_to_date"


def now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def serialize_state(state: State) -> str:
    """Merge-friendly JSON: sorted keys, indented, trailing newline."""
    data = state.model_dump(mode="json")
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def load_state(path: Path) -> State:
    """Load `state.json`, or return an empty state if it doesn't exist yet."""
    if not path.is_file():
        return State()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return State.model_validate(raw)


def save_state(state: State, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serialize_state(state), encoding="utf-8", newline="\n")


def approve_symbol(state: State, relpath: str, qualified_name: str) -> State:
    """Return a new `State` with one symbol's `approved_code_hash` set to its `code_hash`."""
    file_state = state.files.get(relpath)
    if file_state is None or qualified_name not in file_state.symbols:
        raise KeyError(f"No symbol {qualified_name!r} tracked in {relpath!r}")
    symbol = file_state.symbols[qualified_name]
    updated_symbol = symbol.model_copy(update={"approved_code_hash": symbol.code_hash})
    new_symbols = {**file_state.symbols, qualified_name: updated_symbol}
    new_files = {**state.files, relpath: FileState(symbols=new_symbols)}
    return state.model_copy(update={"files": new_files})
