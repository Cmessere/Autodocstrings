"""Byte-offset helpers shared by both language adapters.

Both `ast` (parsing `str` source) and `tree-sitter` (parsing `bytes` source)
report columns as **UTF-8 byte offsets** within a line, not character
offsets. To extract source text correctly for non-ASCII content, we work
against the UTF-8-encoded byte buffer throughout, and decode only the final
extracted slice.
"""

from __future__ import annotations


class SourceBuffer:
    """A source file's bytes, plus an index for (line, byte_col) -> offset."""

    def __init__(self, source: str) -> None:
        self.text = source
        self.data = source.encode("utf-8")
        self._line_offsets = self._build_line_offsets(self.data)

    @staticmethod
    def _build_line_offsets(data: bytes) -> list[int]:
        offsets = [0]
        for i, byte in enumerate(data):
            if byte == 0x0A:  # \n
                offsets.append(i + 1)
        return offsets

    def offset(self, line: int, col: int) -> int:
        """Convert 1-indexed line + 0-indexed byte column to an absolute byte offset."""
        return self._line_offsets[line - 1] + col

    def extract(self, start_line: int, start_col: int, end_line: int, end_col: int) -> str:
        """Extract source text between two (1-indexed line, 0-indexed byte col) points."""
        start = self.offset(start_line, start_col)
        end = self.offset(end_line, end_col)
        return self.data[start:end].decode("utf-8")
