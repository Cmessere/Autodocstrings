from autodocstrings.ignore_markers import file_is_ignored, is_marker_comment


def test_python_marker_recognized() -> None:
    assert is_marker_comment("# autodoc: ignore", "python")
    assert is_marker_comment("  # autodoc: ignore  ", "python")
    assert not is_marker_comment("# autodoc: ignore this file", "python")


def test_js_marker_recognized() -> None:
    assert is_marker_comment("// autodoc: ignore", "typescript")
    assert not is_marker_comment("# autodoc: ignore", "typescript")


def test_file_level_marker_python() -> None:
    source = "# autodoc: ignore\ndef f(): pass\n"
    assert file_is_ignored(source, "python")


def test_file_level_marker_python_after_shebang() -> None:
    source = "#!/usr/bin/env python3\n# autodoc: ignore\ndef f(): pass\n"
    assert file_is_ignored(source, "python")


def test_file_level_marker_not_present() -> None:
    source = "def f(): pass\n"
    assert not file_is_ignored(source, "python")


def test_file_level_marker_js() -> None:
    source = "// autodoc: ignore\nfunction f() {}\n"
    assert file_is_ignored(source, "typescript")


def test_empty_file_not_ignored() -> None:
    assert not file_is_ignored("", "python")
