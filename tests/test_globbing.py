from autodocstrings.globbing import glob_match


def test_star_matches_within_segment() -> None:
    assert glob_match("a.py", "*.py")
    assert not glob_match("a.txt", "*.py")


def test_leading_doublestar_matches_any_depth() -> None:
    assert glob_match("a.py", "**/*")
    assert glob_match("pkg/a.py", "**/*")
    assert glob_match("pkg/sub/a.py", "**/*")


def test_doublestar_sandwiched_excludes_nested_files() -> None:
    """The exact pattern shape that broke on Python 3.12 in CI: `**/name/**`
    must match files nested two or more levels inside `name`, not just
    files directly inside it."""
    pattern = "**/node_modules/**"
    assert glob_match("node_modules/dep/index.js", pattern)
    assert glob_match("node_modules/a/b/c/index.js", pattern)
    assert glob_match("src/node_modules/dep/index.js", pattern)
    assert not glob_match("pkg/a.py", pattern)
    assert not glob_match("node_modules_backup/a.py", pattern)


def test_doublestar_in_middle_of_pattern() -> None:
    assert glob_match("src/pkg/mod.py", "src/**/*.py")
    assert glob_match("src/mod.py", "src/**/*.py")
    assert not glob_match("other/mod.py", "src/**/*.py")


def test_question_mark_matches_single_char() -> None:
    assert glob_match("a.py", "?.py")
    assert not glob_match("ab.py", "?.py")


def test_literal_dots_are_escaped() -> None:
    assert not glob_match("aXpy", "*.py")


def test_bare_doublestar_matches_everything() -> None:
    assert glob_match("a.py", "**")
    assert glob_match("pkg/sub/a.py", "**")
