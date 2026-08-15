from pathlib import Path

from autodocstrings.adapters.typescript_adapter import TypeScriptAdapter

FIXTURE = Path(__file__).parent.parent / "examples" / "fixture-ts" / "src" / "sample.ts"


def _parse(source: str):
    return TypeScriptAdapter().parse(source, "sample.ts")


def _by_name(symbols, name):
    return next(s for s in symbols if s.qualified_name == name)


def test_fixture_symbols_shape() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    symbols = _parse(source)
    names = {s.qualified_name for s in symbols}
    assert names == {
        "capitaliseString",
        "undocumentedAdd",
        "ignoredByMarker",
        "doubleEvens",
        "exportedFetch",
        "Cache",
        "Cache.get",
        "Cache.set",
    }


def test_jsdoc_docstring_captured() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "capitaliseString")
    assert sym.docstring is not None
    assert sym.docstring.text == "/** Capitalises the string. */"


def test_undocumented_function_has_no_docstring() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "undocumentedAdd")
    assert sym.docstring is None


def test_inline_ignore_marker() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "ignoredByMarker")
    assert sym.ignored is True


def test_arrow_function_assigned_to_const() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "doubleEvens")
    assert sym.kind == "function"
    assert sym.docstring is not None


def test_exported_function() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    sym = _by_name(symbols, "exportedFetch")
    assert sym.kind == "function"


def test_class_and_methods() -> None:
    symbols = _parse(FIXTURE.read_text(encoding="utf-8"))
    cache = _by_name(symbols, "Cache")
    assert cache.kind == "class"
    assert cache.docstring is not None
    get = _by_name(symbols, "Cache.get")
    assert get.kind == "method"
    assert get.docstring is not None
    set_method = _by_name(symbols, "Cache.set")
    assert set_method.kind == "method"
    assert set_method.docstring is None


def test_file_level_ignore_marker_excludes_everything() -> None:
    source = "// autodoc: ignore\nfunction f() { return 1; }\n"
    assert _parse(source) == []


def test_async_function() -> None:
    source = "async function fetchIt(): Promise<void> {}\n"
    sym = _by_name(_parse(source), "fetchIt")
    assert sym.is_async is True


def test_generator_function() -> None:
    source = "function* counter() { yield 1; }\n"
    sym = _by_name(_parse(source), "counter")
    assert sym.is_generator is True


def test_async_generator_function() -> None:
    source = "async function* agen() { yield 1; }\n"
    sym = _by_name(_parse(source), "agen")
    assert sym.is_async is True
    assert sym.is_generator is True


def test_nested_function() -> None:
    source = "function outer() {\n  function inner() { return 1; }\n  return inner();\n}\n"
    symbols = _parse(source)
    names = {s.qualified_name for s in symbols}
    assert "outer" in names
    assert "outer.inner" in names


def test_class_decorator() -> None:
    source = "@Component()\nclass Foo {\n  bar(): void {}\n}\n"
    symbols = _parse(source)
    foo = _by_name(symbols, "Foo")
    assert foo.decorators == ("@Component()",)


def test_method_decorator() -> None:
    source = "class Foo {\n  @Input()\n  bar(): void {}\n}\n"
    symbols = _parse(source)
    bar = _by_name(symbols, "Foo.bar")
    assert bar.decorators == ("@Input()",)


def test_class_property_holding_arrow_function() -> None:
    source = "class Foo {\n  resize = (delta: number): void => {\n    this.x += delta;\n  };\n}\n"
    symbols = _parse(source)
    resize = _by_name(symbols, "Foo.resize")
    assert resize.kind == "method"


def test_overload_signatures_skipped_implementation_kept() -> None:
    source = (
        "function bar(a: number, b: number): number;\n"
        "function bar(a: number, b?: number): number {\n"
        "  return a + (b ?? 0);\n"
        "}\n"
    )
    symbols = _parse(source)
    assert len(symbols) == 1
    assert symbols[0].qualified_name == "bar"


def test_determinism_same_source_same_hashes() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    first = _parse(source)
    second = _parse(source)
    first_hashes = {s.qualified_name: (s.code_hash, s.signature_hash) for s in first}
    second_hashes = {s.qualified_name: (s.code_hash, s.signature_hash) for s in second}
    assert first_hashes == second_hashes


def test_adding_comment_inside_body_does_not_change_code_hash() -> None:
    without_comment = "function f(a: number, b: number): number {\n  return a + b;\n}\n"
    with_comment = "function f(a: number, b: number): number {\n  // add them\n  return a + b;\n}\n"
    sym1 = _by_name(_parse(without_comment), "f")
    sym2 = _by_name(_parse(with_comment), "f")
    assert sym1.code_hash == sym2.code_hash


def test_changing_body_changes_code_hash_but_not_signature_hash() -> None:
    v1 = "function f(a: number, b: number): number {\n  return a + b;\n}\n"
    v2 = "function f(a: number, b: number): number {\n  return a - b;\n}\n"
    sym1 = _by_name(_parse(v1), "f")
    sym2 = _by_name(_parse(v2), "f")
    assert sym1.code_hash != sym2.code_hash
    assert sym1.signature_hash == sym2.signature_hash


def test_changing_signature_changes_signature_hash() -> None:
    v1 = "function f(a: number): number {\n  return a;\n}\n"
    v2 = "function f(a: number, b: number): number {\n  return a;\n}\n"
    sym1 = _by_name(_parse(v1), "f")
    sym2 = _by_name(_parse(v2), "f")
    assert sym1.signature_hash != sym2.signature_hash
