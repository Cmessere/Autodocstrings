"""The `LanguageAdapter` interface every language parser implements."""

from __future__ import annotations

from abc import ABC, abstractmethod

from autodocstrings.symbols import Symbol


class LanguageAdapter(ABC):
    """Parses one language's source into a flat list of `Symbol`s."""

    language: str

    @abstractmethod
    def parse(self, source: str, file_path: str) -> list[Symbol]:
        """Parse `source` (the full text of one file) into its symbols.

        `file_path` is used only for error messages; the adapter does not
        read from disk itself.
        """
        raise NotImplementedError
