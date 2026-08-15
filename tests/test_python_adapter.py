from pathlib import Path

from autodocstrings.adapters.python_adapter import PythonAdapter

FIXTURE = Path(__file__).parent.parent / "examples" / "fixture-python" / "pkg" / "sample.py"


def _parse(source: str):
    return PythonAdapter().parse(source, "sample.py")


def _by_name(symbols, name):
    return next(s for s in symbols if s.qualified_name == name)


def test_fixture_symbols_shape() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    symbols = _parse(source)
    names = {s.qualified_name for s in symbols}
    assert names == {
        "capitalise_string",
        "undocumented_add",
        "ignored_by_marker",
        "cached_lookup",
        "fetch_data",
        "outer",
        "outer.inner",
        "number_stream",
        "Widget",
        "Widget.__init__",
        "Widget.size",
        "Widget.resize",
        "Widget.default",
    }


def test_documented_trivial_function() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "capitalise_string")
    assert sym.kind == "function"
    assert sym.docstring is not None
    assert sym.docstring.text == '"""Capitalises the string."""'


def test_undocumented_function_has_no_docstring() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "undocumented_add")
    assert sym.docstring is None


def test_inline_ignore_marker() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "ignored_by_marker")
    assert sym.ignored is True
    other = _by_name(symbols, "undocumented_add")
    assert other.ignored is False


def test_decorator_captured() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "cached_lookup")
    assert sym.decorators == ("@lru_cache(maxsize=None)",)


def test_async_function() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "fetch_data")
    assert sym.is_async is True
    assert sym.is_generator is False


def test_nested_function() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    outer = _by_name(symbols, "outer")
    inner = _by_name(symbols, "outer.inner")
    assert outer.kind == "function"
    assert inner.kind == "function"


def test_generator() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "number_stream")
    assert sym.is_generator is True


def test_class_and_methods() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    widget = _by_name(symbols, "Widget")
    assert widget.kind == "class"
    init = _by_name(symbols, "Widget.__init__")
    assert init.kind == "method"
    prop = _by_name(symbols, "Widget.size")
    assert prop.kind == "method"
    assert prop.decorators == ("@property",)
    static = _by_name(symbols, "Widget.default")
    assert static.decorators == ("@staticmethod",)


def test_file_level_ignore_marker_excludes_everything() -> None:
    source = "# autodoc: ignore\ndef f():\n    return 1\n"
    assert _parse(source) == []


def test_determinism_same_source_same_hashes() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    first = _parse(source)
    second = _parse(source)
    first_hashes = {s.qualified_name: (s.code_hash, s.signature_hash) for s in first}
    second_hashes = {s.qualified_name: (s.code_hash, s.signature_hash) for s in second}
    assert first_hashes == second_hashes


def test_adding_comment_inside_body_does_not_change_code_hash() -> None:
    without_comment = "def f(a, b):\n    total = a + b\n    return total\n"
    with_comment = "def f(a, b):\n    total = a + b  # add them\n    return total\n"
    sym1 = _by_name(_parse(without_comment), "f")
    sym2 = _by_name(_parse(with_comment), "f")
    assert sym1.code_hash == sym2.code_hash


def test_changing_body_changes_code_hash_but_not_signature_hash() -> None:
    v1 = "def f(a, b):\n    return a + b\n"
    v2 = "def f(a, b):\n    return a - b\n"
    sym1 = _by_name(_parse(v1), "f")
    sym2 = _by_name(_parse(v2), "f")
    assert sym1.code_hash != sym2.code_hash
    assert sym1.signature_hash == sym2.signature_hash


def test_changing_signature_changes_signature_hash() -> None:
    v1 = "def f(a, b):\n    return a + b\n"
    v2 = "def f(a, b, c):\n    return a + b\n"
    sym1 = _by_name(_parse(v1), "f")
    sym2 = _by_name(_parse(v2), "f")
    assert sym1.signature_hash != sym2.signature_hash


def test_body_only_docstring_has_empty_body_text() -> None:
    source = 'def f():\n    """Just a docstring."""\n'
    sym = _by_name(_parse(source), "f")
    assert sym.body_text == ""
    assert sym.docstring is not None
