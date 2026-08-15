"""The language-agnostic symbol model produced by every `LanguageAdapter`."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

SymbolKind = Literal["function", "method", "class"]


@dataclass(frozen=True)
class Span:
    """A source range, 1-indexed lines and 0-indexed UTF-8 byte columns."""

    start_line: int
    start_col: int
    end_line: int
    end_col: int


@dataclass(frozen=True)
class DocstringInfo:
    """A symbol's existing docstring: its raw text (quotes/comment markers
    included) and where it sits in the source."""

    text: str
    span: Span


@dataclass(frozen=True)
class Symbol:
    """One documentable unit of code (a function, method, or class)."""

    qualified_name: str
    kind: SymbolKind
    signature: str
    """Raw source text of the declaration, decorators excluded, docstring/body excluded."""
    body_text: str
    """Raw source text of the body, docstring excluded, comments included (for display)."""
    span: Span
    """The full span of the symbol, decorators through end of body."""
    signature_span: Span
    body_span: Span
    """Span of `body_text`. Zero-width when the body is empty after removing the docstring."""
    code_hash: str
    """Hash of the body with the docstring and comments stripped and whitespace normalized."""
    signature_hash: str
    """Hash of the signature with whitespace normalized."""
    docstring: DocstringInfo | None = None
    decorators: tuple[str, ...] = field(default_factory=tuple)
    is_async: bool = False
    is_generator: bool = False
    ignored: bool = False
    """True if an inline `autodoc: ignore` marker precedes this symbol specifically."""
