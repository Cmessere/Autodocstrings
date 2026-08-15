"""Inline `autodoc: ignore` marker recognition, shared by all language adapters.

The marker is valid in two positions:
- **File level**: as the first line of the file (optionally after a shebang),
  which excludes every symbol in the file.
- **Symbol level**: on a line immediately preceding a function/class
  definition (or its decorators), which excludes just that symbol.
"""

from __future__ import annotations

MARKER_TEXT = "autodoc: ignore"

PYTHON_MARKER_LINE = f"# {MARKER_TEXT}"
JS_MARKER_LINE = f"// {MARKER_TEXT}"

_MARKERS_BY_COMMENT_STYLE = {
    "python": PYTHON_MARKER_LINE,
    "typescript": JS_MARKER_LINE,
}


def marker_line_for(language: str) -> str:
    """Return the exact comment line that marks a file/symbol as ignored."""
    try:
        return _MARKERS_BY_COMMENT_STYLE[language]
    except KeyError as exc:
        raise ValueError(f"No ignore marker defined for language {language!r}") from exc


def is_marker_comment(line: str, language: str) -> bool:
    """Whether a single line of source is exactly an ignore marker comment."""
    return line.strip() == marker_line_for(language)


def file_is_ignored(source: str, language: str) -> bool:
    """Whether the ignore marker appears as the file's first substantive line.

    A leading shebang line (`#!...`) is skipped for Python files before
    checking the first line.
    """
    lines = source.splitlines()
    if language == "python" and lines and lines[0].startswith("#!"):
        lines = lines[1:]
    if not lines:
        return False
    return is_marker_comment(lines[0], language)
