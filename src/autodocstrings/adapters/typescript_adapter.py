"""TypeScript/JavaScript source -> `Symbol` list, using tree-sitter.

Handles: function declarations (incl. generators/async), class declarations,
class methods, arrow functions assigned to `const`/`let`, class properties
holding arrow functions, and `export`-wrapped versions of all of the above.
Overload signatures (a declaration with no body) are skipped — only the
implementation carries a trackable body.
"""

from __future__ import annotations

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

from autodocstrings.adapters.base import LanguageAdapter
from autodocstrings.hashing import hash_signature, hash_text, normalize_whitespace
from autodocstrings.ignore_markers import file_is_ignored, is_marker_comment
from autodocstrings.symbols import DocstringInfo, Span, Symbol

_TS_LANGUAGE = Language(tsts.language_typescript())
_TSX_LANGUAGE = Language(tsts.language_tsx())
_JS_LANGUAGE = Language(tsjs.language())


def _node_span(node: Node) -> Span:
    return Span(
        node.start_point.row + 1,
        node.start_point.column,
        node.end_point.row + 1,
        node.end_point.column,
    )


def _text(node: Node) -> str:
    assert node.text is not None
    return node.text.decode("utf-8")


def _strip_comments_join(node: Node) -> str:
    if not node.children:
        return "" if node.type == "comment" else _text(node)
    parts = [_strip_comments_join(child) for child in node.children if child.type != "comment"]
    return " ".join(p for p in parts if p)


def _is_async(node: Node) -> bool:
    return any(child.type == "async" for child in node.children)


def _is_generator(node: Node) -> bool:
    return node.type == "generator_function_declaration" or any(
        child.type == "*" for child in node.children
    )


def _own_decorators(node: Node) -> tuple[str, ...]:
    return tuple(_text(c) for c in node.children if c.type == "decorator")


def _placement_node(node: Node) -> Node:
    """The node occupying a slot in its parent's children list, for JSDoc lookup."""
    n = node
    if n.parent is not None and n.parent.type == "export_statement":
        n = n.parent
    return n


def _find_leading_jsdoc(placement: Node) -> Node | None:
    parent = placement.parent
    if parent is None:
        return None
    siblings = parent.children
    key = (placement.start_byte, placement.end_byte, placement.type)
    idx = next(
        (i for i, s in enumerate(siblings) if (s.start_byte, s.end_byte, s.type) == key), None
    )
    if idx is None or idx == 0:
        return None
    prev = siblings[idx - 1]
    if prev.type == "comment" and _text(prev).startswith("/**"):
        return prev
    return None


def _find_leading_decorators(placement: Node) -> tuple[str, ...]:
    """Decorator siblings immediately preceding a class-member node (methods, fields)."""
    parent = placement.parent
    if parent is None:
        return ()
    siblings = parent.children
    key = (placement.start_byte, placement.end_byte, placement.type)
    idx = next(
        (i for i, s in enumerate(siblings) if (s.start_byte, s.end_byte, s.type) == key), None
    )
    if idx is None:
        return ()
    decorators: list[str] = []
    i = idx - 1
    while i >= 0 and siblings[i].type == "decorator":
        decorators.insert(0, _text(siblings[i]))
        i -= 1
    return tuple(decorators)


def _is_ignored(placement: Node, source_lines: list[str]) -> bool:
    line_idx = placement.start_point.row - 1
    if line_idx < 0:
        return False
    return is_marker_comment(source_lines[line_idx], "typescript")


class _Collector:
    def __init__(self, source_lines: list[str], symbols: list[Symbol]) -> None:
        self.source_lines = source_lines
        self.symbols = symbols
        self.name_stack: list[str] = []

    def _qualified_name(self, name: str) -> str:
        return ".".join([*self.name_stack, name])

    def _emit(
        self,
        *,
        name: str,
        kind: str,
        definition_node: Node,
        body_node: Node,
        decorators: tuple[str, ...],
        placement: Node,
        is_async: bool,
        is_generator: bool,
    ) -> None:
        signature_text = self._extract(
            definition_node.start_point.row + 1,
            definition_node.start_point.column,
            body_node.start_point.row + 1,
            body_node.start_point.column,
        ).rstrip()

        jsdoc = _find_leading_jsdoc(placement)
        docstring = (
            DocstringInfo(text=_text(jsdoc), span=_node_span(jsdoc)) if jsdoc is not None else None
        )

        body_text = _text(body_node)
        code_hash = hash_text(normalize_whitespace(_strip_comments_join(body_node)))

        self.symbols.append(
            Symbol(
                qualified_name=self._qualified_name(name),
                kind=kind,  # type: ignore[arg-type]
                signature=signature_text,
                body_text=body_text,
                span=_node_span(placement),
                signature_span=Span(
                    definition_node.start_point.row + 1,
                    definition_node.start_point.column,
                    body_node.start_point.row + 1,
                    body_node.start_point.column,
                ),
                body_span=_node_span(body_node),
                code_hash=code_hash,
                signature_hash=hash_signature(signature_text),
                docstring=docstring,
                decorators=decorators,
                is_async=is_async,
                is_generator=is_generator,
                ignored=_is_ignored(placement, self.source_lines),
            )
        )

    def _extract(self, start_line: int, start_col: int, end_line: int, end_col: int) -> str:
        # Columns from tree-sitter are UTF-8 byte offsets; re-encode the line to slice correctly.
        if start_line == end_line:
            line_bytes = self.source_lines[start_line - 1].encode("utf-8")
            return line_bytes[start_col:end_col].decode("utf-8")
        lines_bytes = [
            line.encode("utf-8") for line in self.source_lines[start_line - 1 : end_line]
        ]
        lines_bytes[0] = lines_bytes[0][start_col:]
        lines_bytes[-1] = lines_bytes[-1][:end_col]
        return "\n".join(b.decode("utf-8") for b in lines_bytes)

    def visit(self, node: Node) -> None:
        handler = getattr(self, f"_visit_{node.type}", None)
        if handler is not None:
            handler(node)
            return
        for child in node.children:
            self.visit(child)

    def _visit_class_declaration(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        name = _text(name_node) if name_node is not None else "<anonymous>"
        body_node = node.child_by_field_name("body")
        if body_node is None:
            return
        non_decorator_children = [c for c in node.children if c.type != "decorator"]
        definition_node = non_decorator_children[0] if non_decorator_children else node
        self._emit(
            name=name,
            kind="class",
            definition_node=definition_node,
            body_node=body_node,
            decorators=_own_decorators(node),
            placement=_placement_node(node),
            is_async=False,
            is_generator=False,
        )
        self.name_stack.append(name)
        for child in body_node.children:
            self.visit(child)
        self.name_stack.pop()

    def _visit_function_declaration(self, node: Node) -> None:
        self._visit_plain_function(node)

    def _visit_generator_function_declaration(self, node: Node) -> None:
        self._visit_plain_function(node)

    def _visit_plain_function(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")
        if name_node is None or body_node is None:
            return
        name = _text(name_node)
        self._emit(
            name=name,
            kind="function",
            definition_node=node,
            body_node=body_node,
            decorators=(),
            placement=_placement_node(node),
            is_async=_is_async(node),
            is_generator=_is_generator(node),
        )
        self.name_stack.append(name)
        for child in body_node.children:
            self.visit(child)
        self.name_stack.pop()

    def _visit_method_definition(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        body_node = node.child_by_field_name("body")
        if name_node is None or body_node is None:
            return
        name = _text(name_node)
        self._emit(
            name=name,
            kind="method",
            definition_node=node,
            body_node=body_node,
            decorators=_find_leading_decorators(node),
            placement=node,
            is_async=_is_async(node),
            is_generator=_is_generator(node),
        )
        self.name_stack.append(name)
        for child in body_node.children:
            self.visit(child)
        self.name_stack.pop()

    def _visit_method_signature(self, node: Node) -> None:
        return  # overload declaration, no body to track

    def _visit_function_signature(self, node: Node) -> None:
        return

    def _visit_abstract_method_signature(self, node: Node) -> None:
        return

    def _visit_public_field_definition(self, node: Node) -> None:
        self._visit_field_with_possible_function(node)

    def _visit_field_definition(self, node: Node) -> None:
        self._visit_field_with_possible_function(node)

    def _visit_field_with_possible_function(self, node: Node) -> None:
        name_node = node.child_by_field_name("name")
        value_node = node.child_by_field_name("value")
        if name_node is None or value_node is None or value_node.type != "arrow_function":
            for child in node.children:
                self.visit(child)
            return
        name = _text(name_node)
        body_node = value_node.child_by_field_name("body")
        if body_node is None:
            return
        self._emit(
            name=name,
            kind="method",
            definition_node=node,
            body_node=body_node,
            decorators=_find_leading_decorators(node),
            placement=node,
            is_async=_is_async(value_node),
            is_generator=False,
        )
        self.name_stack.append(name)
        for child in body_node.children:
            self.visit(child)
        self.name_stack.pop()

    def _visit_lexical_declaration(self, node: Node) -> None:
        self._visit_variable_style_declaration(node)

    def _visit_variable_declaration(self, node: Node) -> None:
        self._visit_variable_style_declaration(node)

    def _visit_variable_style_declaration(self, node: Node) -> None:
        declarators = [c for c in node.children if c.type == "variable_declarator"]
        arrow_declarators = [
            d
            for d in declarators
            if (v := d.child_by_field_name("value")) is not None and v.type == "arrow_function"
        ]
        if len(arrow_declarators) != 1:
            for child in node.children:
                self.visit(child)
            return

        declarator = arrow_declarators[0]
        name_node = declarator.child_by_field_name("name")
        value_node = declarator.child_by_field_name("value")
        assert value_node is not None
        body_node = value_node.child_by_field_name("body")
        if name_node is None or body_node is None:
            return
        name = _text(name_node)
        self._emit(
            name=name,
            kind="function",
            definition_node=node,
            body_node=body_node,
            decorators=(),
            placement=_placement_node(node),
            is_async=_is_async(value_node),
            is_generator=False,
        )
        self.name_stack.append(name)
        for child in body_node.children:
            self.visit(child)
        self.name_stack.pop()


class TypeScriptAdapter(LanguageAdapter):
    language = "typescript"

    def __init__(self, *, tsx: bool = False, javascript: bool = False) -> None:
        if javascript:
            ts_lang = _JS_LANGUAGE
        elif tsx:
            ts_lang = _TSX_LANGUAGE
        else:
            ts_lang = _TS_LANGUAGE
        self._parser = Parser(ts_lang)

    def parse(self, source: str, file_path: str) -> list[Symbol]:
        if file_is_ignored(source, "typescript"):
            return []
        tree = self._parser.parse(source.encode("utf-8"))
        source_lines = source.splitlines()
        symbols: list[Symbol] = []
        collector = _Collector(source_lines, symbols)
        for child in tree.root_node.children:
            collector.visit(child)
        return symbols
