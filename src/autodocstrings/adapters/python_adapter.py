"""Python source -> `Symbol` list, using the stdlib `ast` module."""

from __future__ import annotations

import ast
import io
import textwrap
import tokenize

from autodocstrings.adapters.base import LanguageAdapter
from autodocstrings.hashing import hash_signature, hash_text, normalize_whitespace
from autodocstrings.ignore_markers import file_is_ignored, is_marker_comment
from autodocstrings.source_utils import SourceBuffer
from autodocstrings.symbols import DocstringInfo, Span, Symbol

_DefNode = ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef
_FuncNode = ast.FunctionDef | ast.AsyncFunctionDef


def _end_pos(node: ast.expr | ast.stmt) -> tuple[int, int]:
    """end_lineno/end_col_offset are Optional in the ast stubs but always set
    for real nodes produced by `ast.parse` on source text."""
    assert node.end_lineno is not None
    assert node.end_col_offset is not None
    return node.end_lineno, node.end_col_offset


_SKIP_TOKEN_TYPES = frozenset(
    {
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENCODING,
        tokenize.ENDMARKER,
    }
)


def _normalize_python_body(body_text: str) -> str:
    """Strip comments and normalize whitespace via tokenize, with a safe fallback."""
    if not body_text.strip():
        return ""
    dedented = textwrap.dedent(body_text)
    try:
        tokens = [
            tok.string
            for tok in tokenize.generate_tokens(io.StringIO(dedented).readline)
            if tok.type not in _SKIP_TOKEN_TYPES
        ]
        return normalize_whitespace(" ".join(tokens))
    except (tokenize.TokenError, IndentationError, SyntaxError):
        return normalize_whitespace(dedented)


class _YieldFinder(ast.NodeVisitor):
    """Detects `yield`/`yield from` in a body without descending into nested defs."""

    def __init__(self) -> None:
        self.found = False

    def visit_Yield(self, node: ast.Yield) -> None:
        self.found = True

    def visit_YieldFrom(self, node: ast.YieldFrom) -> None:
        self.found = True

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        pass

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        pass

    def visit_Lambda(self, node: ast.Lambda) -> None:
        pass


def _is_generator(body: list[ast.stmt]) -> bool:
    finder = _YieldFinder()
    for stmt in body:
        finder.visit(stmt)
    return finder.found


def _docstring_node(body: list[ast.stmt]) -> ast.Expr | None:
    if not body:
        return None
    first = body[0]
    if (
        isinstance(first, ast.Expr)
        and isinstance(first.value, ast.Constant)
        and isinstance(first.value.value, str)
    ):
        return first
    return None


class _Visitor(ast.NodeVisitor):
    def __init__(self, buf: SourceBuffer, lines: list[str], symbols: list[Symbol]) -> None:
        self.buf = buf
        self.lines = lines
        self.symbols = symbols
        self.name_stack: list[str] = []
        self.in_class_stack: list[bool] = []

    def _qualified_name(self, name: str) -> str:
        return ".".join([*self.name_stack, name])

    def _is_ignored(self, node: _DefNode) -> bool:
        first_line = node.decorator_list[0].lineno if node.decorator_list else node.lineno
        idx = first_line - 2
        if idx < 0:
            return False
        return is_marker_comment(self.lines[idx], "python")

    def _extract(self, start_line: int, start_col: int, end_line: int, end_col: int) -> str:
        return self.buf.extract(start_line, start_col, end_line, end_col)

    def _build_symbol(self, node: _DefNode, kind: str) -> Symbol:
        decorators = tuple(
            "@" + self._extract(d.lineno, d.col_offset, *_end_pos(d)) for d in node.decorator_list
        )
        span_start_line, span_start_col = (
            (node.decorator_list[0].lineno, node.decorator_list[0].col_offset)
            if node.decorator_list
            else (node.lineno, node.col_offset)
        )

        body: list[ast.stmt] = node.body
        first_body_stmt = body[0]
        signature_text = self._extract(
            node.lineno, node.col_offset, first_body_stmt.lineno, first_body_stmt.col_offset
        ).rstrip()
        signature_span = Span(
            node.lineno, node.col_offset, first_body_stmt.lineno, first_body_stmt.col_offset
        )

        doc_node = _docstring_node(body)
        docstring = None
        if doc_node is not None:
            doc_end_line, doc_end_col = _end_pos(doc_node)
            doc_span = Span(doc_node.lineno, doc_node.col_offset, doc_end_line, doc_end_col)
            docstring = DocstringInfo(
                text=self._extract(doc_node.lineno, doc_node.col_offset, doc_end_line, doc_end_col),
                span=doc_span,
            )

        remaining = body[1:] if doc_node is not None else body
        if remaining:
            b_start, b_end = remaining[0], remaining[-1]
            b_end_line, b_end_col = _end_pos(b_end)
            body_span = Span(b_start.lineno, b_start.col_offset, b_end_line, b_end_col)
            body_text = self._extract(b_start.lineno, b_start.col_offset, b_end_line, b_end_col)
        elif doc_node is not None:
            anchor_line, anchor_col = _end_pos(doc_node)
            body_span = Span(anchor_line, anchor_col, anchor_line, anchor_col)
            body_text = ""
        else:
            anchor_line, anchor_col = node.lineno, node.col_offset
            body_span = Span(anchor_line, anchor_col, anchor_line, anchor_col)
            body_text = ""

        is_async = isinstance(node, ast.AsyncFunctionDef)
        is_generator = isinstance(node, _FuncNode) and _is_generator(body)

        node_end_line, node_end_col = _end_pos(node)
        symbol = Symbol(
            qualified_name=self._qualified_name(node.name),
            kind=kind,  # type: ignore[arg-type]
            signature=signature_text,
            body_text=body_text,
            span=Span(span_start_line, span_start_col, node_end_line, node_end_col),
            signature_span=signature_span,
            body_span=body_span,
            code_hash=hash_text(_normalize_python_body(body_text)),
            signature_hash=hash_signature(signature_text),
            docstring=docstring,
            decorators=decorators,
            is_async=is_async,
            is_generator=is_generator,
            ignored=self._is_ignored(node),
        )
        return symbol

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append(self._build_symbol(node, "class"))
        self.name_stack.append(node.name)
        self.in_class_stack.append(True)
        self.generic_visit(node)
        self.in_class_stack.pop()
        self.name_stack.pop()

    def _visit_function(self, node: _FuncNode) -> None:
        kind = "method" if self.in_class_stack and self.in_class_stack[-1] else "function"
        self.symbols.append(self._build_symbol(node, kind))
        self.name_stack.append(node.name)
        self.in_class_stack.append(False)
        self.generic_visit(node)
        self.in_class_stack.pop()
        self.name_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)


class PythonAdapter(LanguageAdapter):
    language = "python"

    def parse(self, source: str, file_path: str) -> list[Symbol]:
        if file_is_ignored(source, "python"):
            return []
        try:
            tree = ast.parse(source, filename=file_path)
        except SyntaxError as exc:
            raise ValueError(f"Failed to parse {file_path}: {exc}") from exc

        buf = SourceBuffer(source)
        lines = source.splitlines()
        symbols: list[Symbol] = []
        visitor = _Visitor(buf, lines, symbols)
        visitor.visit(tree)
        return symbols
