"""Language adapter registry.

Maps a config `languages` value (e.g. "python", "typescript") to the adapter
that parses it. Adapters are instantiated lazily so importing this package
doesn't pull in tree-sitter unless a TS/JS file is actually parsed.
"""

from __future__ import annotations

from autodocstrings.adapters.base import LanguageAdapter

_ADAPTERS: dict[str, LanguageAdapter] = {}


def get_adapter(language: str) -> LanguageAdapter:
    """Return the (cached) adapter instance for a language name."""
    if language not in _ADAPTERS:
        if language == "python":
            from autodocstrings.adapters.python_adapter import PythonAdapter

            _ADAPTERS[language] = PythonAdapter()
        elif language == "typescript":
            from autodocstrings.adapters.typescript_adapter import TypeScriptAdapter

            _ADAPTERS[language] = TypeScriptAdapter()
        else:
            raise ValueError(f"No language adapter registered for {language!r}")
    return _ADAPTERS[language]


__all__ = ["LanguageAdapter", "get_adapter"]
