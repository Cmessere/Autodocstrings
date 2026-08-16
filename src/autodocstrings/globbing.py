"""Glob pattern matching for `include`/`exclude`, independent of `pathlib.Path.glob()`.

`pathlib.Path.glob()`'s handling of a trailing `**` path segment (e.g.
`**/node_modules/**` matching files *nested inside* `node_modules`) differs
between Python versions -- notably 3.11/3.12 vs 3.13+. Relying on it made
`discover_files` behave differently depending on which Python ran it (a
config exclude that worked locally silently stopped excluding anything in
CI). This module translates glob patterns to regexes ourselves, so matching
is identical on every supported Python version.

Supported syntax: `*` (anything except `/`), `?` (one char except `/`), and
`**` as a full path segment (zero or more directory levels, or -- as the
final segment -- the rest of the path).
"""

from __future__ import annotations

import re
from functools import cache


def _segment_to_regex(segment: str) -> str:
    """Translate one non-`**` path segment (never contains `/`) to a regex fragment."""
    out: list[str] = []
    for ch in segment:
        if ch == "*":
            out.append("[^/]*")
        elif ch == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(ch))
    return "".join(out)


@cache
def compile_glob(pattern: str) -> re.Pattern[str]:
    """Compile a glob pattern into a regex matched against a POSIX relative path."""
    segments = pattern.split("/")
    parts: list[str] = []
    i = 0
    n = len(segments)
    while i < n:
        if segments[i] == "**":
            j = i
            while j < n and segments[j] == "**":
                j += 1
            is_last = j == n
            parts.append(r".*" if is_last else r"(?:[^/]+/)*")
            i = j
        else:
            is_last = i == n - 1
            parts.append(_segment_to_regex(segments[i]))
            if not is_last:
                parts.append("/")
            i += 1
    return re.compile("^" + "".join(parts) + "$")


def glob_match(relpath: str, pattern: str) -> bool:
    """Whether a POSIX-style relative path matches a glob pattern."""
    return compile_glob(pattern).match(relpath) is not None
