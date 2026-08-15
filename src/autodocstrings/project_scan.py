"""Discovers files, runs the right `LanguageAdapter` over each, and merges
the result into the persisted `State` — the engine behind `autodoc scan`.
"""

from __future__ import annotations

from pathlib import Path

from autodocstrings.adapters import get_adapter
from autodocstrings.config import Config
from autodocstrings.hashing import hash_text, normalize_whitespace
from autodocstrings.state import FileState, State, SymbolState, now_iso
from autodocstrings.symbols import Symbol


def discover_files(root: Path, config: Config) -> dict[str, str]:
    """Return {relative_posix_path: language} for every file the config selects."""
    included: set[Path] = set()
    for pattern in config.include:
        included.update(p for p in root.glob(pattern) if p.is_file())

    excluded: set[Path] = set()
    for pattern in config.exclude:
        excluded.update(p for p in root.glob(pattern) if p.is_file())

    result: dict[str, str] = {}
    for path in included - excluded:
        language = config.languages.get(path.suffix)
        if language is None:
            continue
        result[path.relative_to(root).as_posix()] = language
    return result


def _doc_hash(symbol: Symbol) -> str | None:
    if symbol.docstring is None:
        return None
    return hash_text(normalize_whitespace(symbol.docstring.text))


def _merge_symbol(
    previous: SymbolState | None, fresh: Symbol, *, trust_existing: bool, now: str
) -> SymbolState:
    doc_hash = _doc_hash(fresh)
    if previous is None:
        approved = fresh.code_hash if (trust_existing and doc_hash is not None) else None
        updated_at = now
    else:
        code_changed = previous.code_hash != fresh.code_hash
        approved = previous.approved_code_hash
        updated_at = now if code_changed else previous.updated_at
    return SymbolState(
        code_hash=fresh.code_hash,
        signature_hash=fresh.signature_hash,
        doc_hash=doc_hash,
        approved_code_hash=approved,
        updated_at=updated_at,
        ignored=fresh.ignored,
    )


def apply_scan(
    previous_state: State, parsed_files: dict[str, list[Symbol]], *, trust_existing: bool, now: str
) -> State:
    """Merge freshly-parsed symbols into the previous state.

    Files/symbols absent from `parsed_files` are pruned (deleted or now
    excluded). A symbol whose qualified name changed (rename) is a delete of
    the old name plus an addition of the new one.
    """
    new_files: dict[str, FileState] = {}
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


def scan_project(root: Path, config: Config, previous_state: State) -> State:
    """Discover, parse, and merge — the full `autodoc scan` pipeline."""
    discovered = discover_files(root, config)
    parsed: dict[str, list[Symbol]] = {}
    for relpath, language in discovered.items():
        source = (root / relpath).read_text(encoding="utf-8")
        adapter = get_adapter(language)
        parsed[relpath] = adapter.parse(source, relpath)
    return apply_scan(
        previous_state, parsed, trust_existing=config.init.trust_existing, now=now_iso()
    )
