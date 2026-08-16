"""Discovers files, runs the right `LanguageAdapter` over each, and merges
the result into the persisted `State` — the engine behind `autodoc scan`.
"""

from __future__ import annotations

import os
from pathlib import Path

from autodocstrings.adapters import get_adapter
from autodocstrings.config import Config
from autodocstrings.globbing import glob_match
from autodocstrings.hashing import hash_text, normalize_whitespace
from autodocstrings.state import FileState, State, SymbolState, now_iso
from autodocstrings.symbols import Symbol

# Pruned from directory walks outright, as a performance optimization on top
# of the config's own `exclude` patterns -- these can otherwise be enormous
# (vendored virtualenvs, node_modules) and there is never a reason to
# descend into them.
_PRUNED_DIR_NAMES = frozenset({"node_modules", ".venv", "venv", "__pycache__", ".git"})


def discover_files(root: Path, config: Config) -> dict[str, str]:
    """Return {relative_posix_path: language} for every file the config selects."""
    result: dict[str, str] = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in _PRUNED_DIR_NAMES]
        for filename in filenames:
            file_path = Path(dirpath) / filename
            relpath = file_path.relative_to(root).as_posix()

            if not any(glob_match(relpath, pattern) for pattern in config.include):
                continue
            if any(glob_match(relpath, pattern) for pattern in config.exclude):
                continue

            language = config.languages.get(file_path.suffix)
            if language is None:
                continue
            result[relpath] = language
    return result


def _doc_hash(symbol: Symbol) -> str | None:
    if symbol.docstring is None:
        return None
    return hash_text(normalize_whitespace(symbol.docstring.text))


def _merge_symbol(
    previous: SymbolState | None, fresh: Symbol, *, trust_existing: bool, now: str
) -> SymbolState:
    doc_hash = _doc_hash(fresh)
    trusted_baseline = trust_existing and doc_hash is not None
    if previous is None:
        approved_code = fresh.code_hash if trusted_baseline else None
        approved_signature = fresh.signature_hash if trusted_baseline else None
        updated_at = now
    else:
        code_changed = previous.code_hash != fresh.code_hash
        approved_code = previous.approved_code_hash
        approved_signature = previous.approved_signature_hash
        updated_at = now if code_changed else previous.updated_at
    return SymbolState(
        code_hash=fresh.code_hash,
        signature_hash=fresh.signature_hash,
        doc_hash=doc_hash,
        approved_code_hash=approved_code,
        approved_signature_hash=approved_signature,
        updated_at=updated_at,
        ignored=fresh.ignored,
    )


def _in_scope(relpath: str, scope_rels: frozenset[str] | None) -> bool:
    if scope_rels is None:
        return True
    return any(relpath == s or relpath.startswith(s + "/") for s in scope_rels)


def apply_scan(
    previous_state: State,
    parsed_files: dict[str, list[Symbol]],
    *,
    trust_existing: bool,
    now: str,
    scope_rels: frozenset[str] | None = None,
) -> State:
    """Merge freshly-parsed symbols into the previous state.

    Files/symbols absent from `parsed_files` are pruned (deleted or now
    excluded) -- but only within `scope_rels` (relative-posix file or
    directory prefixes). Files outside scope are left untouched, so a
    scoped scan (`--path`/`--package`/`check --staged`) never prunes state
    for the rest of the repo. A symbol whose qualified name changed (rename)
    is a delete of the old name plus an addition of the new one.
    """
    new_files: dict[str, FileState] = {
        relpath: file_state
        for relpath, file_state in previous_state.files.items()
        if relpath in parsed_files or not _in_scope(relpath, scope_rels)
    }
    for relpath, symbols in parsed_files.items():
        previous_file = previous_state.files.get(relpath)
        previous_symbols = previous_file.symbols if previous_file is not None else {}
        new_symbols = {
            symbol.qualified_name: _merge_symbol(
                previous_symbols.get(symbol.qualified_name),
                symbol,
                trust_existing=trust_existing,
                now=now,
            )
            for symbol in symbols
        }
        new_files[relpath] = FileState(symbols=new_symbols)
    return State(files=new_files)


def scan_project(
    root: Path,
    config: Config,
    previous_state: State,
    scopes: list[Path] | None = None,
) -> State:
    """Discover, parse, and merge — the full `autodoc scan` pipeline.

    `scopes`, if given, restricts which discovered files are (re)parsed and
    which state entries can be pruned, to the given files/directories.
    """
    discovered = discover_files(root, config)
    scope_rels: frozenset[str] | None = None
    if scopes is not None:
        scope_rels = frozenset(
            scope.resolve().relative_to(root.resolve()).as_posix() for scope in scopes
        )
        discovered = {rp: lang for rp, lang in discovered.items() if _in_scope(rp, scope_rels)}

    parsed: dict[str, list[Symbol]] = {}
    for relpath, language in discovered.items():
        source = (root / relpath).read_text(encoding="utf-8")
        adapter = get_adapter(language)
        parsed[relpath] = adapter.parse(source, relpath)
    return apply_scan(
        previous_state,
        parsed,
        trust_existing=config.init.trust_existing,
        now=now_iso(),
        scope_rels=scope_rels,
    )
