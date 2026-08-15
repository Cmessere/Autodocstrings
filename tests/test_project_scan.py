from pathlib import Path

from autodocstrings.config import Config
from autodocstrings.project_scan import discover_files, scan_project
from autodocstrings.state import State, approve_symbol, compute_status, save_state


def _write(root: Path, relpath: str, content: str) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_discover_files_respects_include_exclude_and_languages(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/a.py", "def f():\n    return 1\n")
    _write(tmp_path, "pkg/b.txt", "not source")
    _write(tmp_path, "node_modules/dep/c.py", "def g():\n    return 2\n")
    config = Config()
    discovered = discover_files(tmp_path, config)
    assert discovered == {"pkg/a.py": "python"}


def test_new_symbol_never_started_by_default(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", "def f():\n    return 1\n")
    config = Config(init={"trust_existing": False})
    state = scan_project(tmp_path, config, State())
    sym = state.files["a.py"].symbols["f"]
    assert compute_status(sym) == "never_started"


def test_new_documented_symbol_trusted_baseline(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 1\n')
    config = Config(init={"trust_existing": True})
    state = scan_project(tmp_path, config, State())
    sym = state.files["a.py"].symbols["f"]
    assert compute_status(sym) == "up_to_date"


def test_new_documented_symbol_not_trusted(tmp_path: Path) -> None:
    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 1\n')
    config = Config(init={"trust_existing": False})
    state = scan_project(tmp_path, config, State())
    sym = state.files["a.py"].symbols["f"]
    assert compute_status(sym) == "stale"


def test_body_edit_makes_up_to_date_symbol_stale(tmp_path: Path) -> None:
    config = Config(init={"trust_existing": True})
    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 1\n')
    state1 = scan_project(tmp_path, config, State())
    assert compute_status(state1.files["a.py"].symbols["f"]) == "up_to_date"

    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 2\n')
    state2 = scan_project(tmp_path, config, state1)
    assert compute_status(state2.files["a.py"].symbols["f"]) == "stale"


def test_doc_edit_without_body_edit_stays_up_to_date(tmp_path: Path) -> None:
    config = Config(init={"trust_existing": True})
    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 1\n')
    state1 = scan_project(tmp_path, config, State())

    _write(
        tmp_path, "a.py", 'def f():\n    """Does a thing, differently worded."""\n    return 1\n'
    )
    state2 = scan_project(tmp_path, config, state1)
    sym = state2.files["a.py"].symbols["f"]
    assert compute_status(sym) == "up_to_date"
    assert sym.doc_hash != state1.files["a.py"].symbols["f"].doc_hash


def test_approve_transitions_stale_to_up_to_date(tmp_path: Path) -> None:
    config = Config(init={"trust_existing": False})
    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 1\n')
    state = scan_project(tmp_path, config, State())
    assert compute_status(state.files["a.py"].symbols["f"]) == "stale"

    approved = approve_symbol(state, "a.py", "f")
    assert compute_status(approved.files["a.py"].symbols["f"]) == "up_to_date"


def test_ignore_marker_added_and_removed(tmp_path: Path) -> None:
    config = Config()
    _write(tmp_path, "a.py", "def f():\n    return 1\n")
    state1 = scan_project(tmp_path, config, State())
    assert compute_status(state1.files["a.py"].symbols["f"]) == "never_started"

    _write(tmp_path, "a.py", "# autodoc: ignore\ndef f():\n    return 1\n")
    state2 = scan_project(tmp_path, config, state1)
    assert state2.files["a.py"].symbols == {}  # whole-file marker: nothing tracked

    _write(tmp_path, "a.py", "def f():\n    return 1\n")
    state3 = scan_project(tmp_path, config, state2)
    assert compute_status(state3.files["a.py"].symbols["f"]) == "never_started"


def test_symbol_level_ignore_marker(tmp_path: Path) -> None:
    config = Config()
    _write(
        tmp_path,
        "a.py",
        "def tracked():\n    return 1\n\n\n# autodoc: ignore\ndef skipped():\n    return 2\n",
    )
    state = scan_project(tmp_path, config, State())
    assert compute_status(state.files["a.py"].symbols["tracked"]) == "never_started"
    assert compute_status(state.files["a.py"].symbols["skipped"]) == "ignored"


def test_file_deleted_is_pruned(tmp_path: Path) -> None:
    config = Config()
    _write(tmp_path, "a.py", "def f():\n    return 1\n")
    state1 = scan_project(tmp_path, config, State())
    assert "a.py" in state1.files

    (tmp_path / "a.py").unlink()
    state2 = scan_project(tmp_path, config, state1)
    assert "a.py" not in state2.files


def test_symbol_deleted_is_pruned(tmp_path: Path) -> None:
    config = Config()
    _write(tmp_path, "a.py", "def f():\n    return 1\n\n\ndef g():\n    return 2\n")
    state1 = scan_project(tmp_path, config, State())
    assert set(state1.files["a.py"].symbols) == {"f", "g"}

    _write(tmp_path, "a.py", "def f():\n    return 1\n")
    state2 = scan_project(tmp_path, config, state1)
    assert set(state2.files["a.py"].symbols) == {"f"}


def test_rename_is_delete_plus_new(tmp_path: Path) -> None:
    config = Config(init={"trust_existing": False})
    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 1\n')
    state1 = scan_project(tmp_path, config, State())
    approved = approve_symbol(state1, "a.py", "f")
    assert compute_status(approved.files["a.py"].symbols["f"]) == "up_to_date"

    _write(tmp_path, "a.py", 'def renamed():\n    """Does a thing."""\n    return 1\n')
    state2 = scan_project(tmp_path, config, approved)
    assert "f" not in state2.files["a.py"].symbols
    assert "renamed" in state2.files["a.py"].symbols
    assert compute_status(state2.files["a.py"].symbols["renamed"]) == "stale"


def test_scoped_scan_does_not_prune_files_outside_scope(tmp_path: Path) -> None:
    config = Config()
    _write(tmp_path, "pkg_a/a.py", "def f():\n    return 1\n")
    _write(tmp_path, "pkg_b/b.py", "def g():\n    return 2\n")
    state1 = scan_project(tmp_path, config, State())
    assert set(state1.files) == {"pkg_a/a.py", "pkg_b/b.py"}

    (tmp_path / "pkg_b/b.py").unlink()
    state2 = scan_project(tmp_path, config, state1, scopes=[tmp_path / "pkg_a"])
    assert "pkg_a/a.py" in state2.files
    assert "pkg_b/b.py" in state2.files  # untouched: outside the scanned scope


def test_scoped_scan_still_prunes_deletions_inside_scope(tmp_path: Path) -> None:
    config = Config()
    _write(tmp_path, "pkg_a/a.py", "def f():\n    return 1\n")
    _write(tmp_path, "pkg_a/other.py", "def h():\n    return 3\n")
    state1 = scan_project(tmp_path, config, State())

    (tmp_path / "pkg_a/other.py").unlink()
    state2 = scan_project(tmp_path, config, state1, scopes=[tmp_path / "pkg_a"])
    assert "pkg_a/a.py" in state2.files
    assert "pkg_a/other.py" not in state2.files


def test_idempotent_rescan_produces_identical_state(tmp_path: Path) -> None:
    config = Config()
    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 1\n')
    state1 = scan_project(tmp_path, config, State())
    state2 = scan_project(tmp_path, config, state1)
    assert state1 == state2


def test_idempotent_rescan_writes_byte_identical_file(tmp_path: Path) -> None:
    config = Config()
    _write(tmp_path, "a.py", 'def f():\n    """Does a thing."""\n    return 1\n')
    state1 = scan_project(tmp_path, config, State())
    state_path = tmp_path / ".autodocstrings" / "state.json"
    save_state(state1, state_path)
    first_bytes = state_path.read_bytes()

    state2 = scan_project(tmp_path, config, state1)
    save_state(state2, state_path)
    second_bytes = state_path.read_bytes()

    assert first_bytes == second_bytes
