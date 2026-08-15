"""Deterministic hashing shared by all language adapters.

`code_hash` is computed from the body with comments stripped and whitespace
normalized, so purely cosmetic edits (reformatting, adding/removing a
comment) never change it. `signature_hash` is computed from the raw
signature text with whitespace normalized only (no comment stripping —
signatures containing `//`-like substrings inside string literals must not
be mistaken for comments).
"""

from __future__ import annotations

import hashlib
import re

_WHITESPACE_RE = re.compile(r"\s+")

HASH_LENGTH = 16


def normalize_whitespace(text: str) -> str:
    """Collapse all runs of whitespace to a single space and strip the ends."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def hash_text(normalized: str) -> str:
    """Hash already-normalized text into a short, stable hex digest."""
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:HASH_LENGTH]


def hash_signature(signature_text: str) -> str:
    return hash_text(normalize_whitespace(signature_text))


def hash_body(comment_stripped_text: str) -> str:
    return hash_text(normalize_whitespace(comment_stripped_text))
