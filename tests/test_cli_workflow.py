import json
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.usefixtures("_isolate_cwd")


@pytest.fixture
def _isolate_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.chdir(tmp_path)
    yield tmp_path


def _run(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "autodocstrings.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


def _write(root: Path, relpath: str, content: str) -> None:
    path = root / relpath
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_init_writes_config_and_scans(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "sample.py",
        'def f():\n    """Doc."""\n    return 1\n\n\ndef g():\n    return 2\n',
    )
    result = _run("init", "--yes", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert (tmp_path / "autodocstrings.config.json").is_file()
    assert (tmp_path / ".autodocstrings" / "state.json").is_file()
    assert "2 symbol(s) tracked" in result.stdout


def test_scan_then_status_json_schema(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "sample.py",
        'def f():\n    """Doc."""\n    return 1\n\n\ndef g():\n    return 2\n',
    )
    assert _run("init", "--yes", cwd=tmp_path).returncode == 0

    result = _run("status", "--json", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["schema_version"] == 1
    statuses = {e["qualified_name"]: e["status"] for e in payload["symbols"]}
    assert statuses == {"f": "up_to_date", "g": "never_started"}


def test_status_only_filter(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "sample.py",
        'def f():\n    """Doc."""\n    return 1\n\n\ndef g():\n    return 2\n',
    )
    _run("init", "--yes", cwd=tmp_path)
    result = _run("status", "--only", "never_started", cwd=tmp_path)
    assert "sample.py:g" in result.stdout
    assert "sample.py:f" not in result.stdout


def test_diff_never_started_symbol(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", "def g():\n    return 2\n")
    _run("init", "--yes", cwd=tmp_path)
    result = _run("diff", "sample.py:g", "--json", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    entry = payload["symbols"][0]
    assert entry["status"] == "never_started"
    assert entry["body_changed"] is True


def test_approve_then_status_up_to_date(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", 'def g():\n    """Doc."""\n    return 2\n')
    _run("init", "--yes", cwd=tmp_path)
    # trust_existing default True, so g should already be up_to_date from init's scan.
    result = _run("status", "--json", cwd=tmp_path)
    payload = json.loads(result.stdout)
    assert payload["symbols"][0]["status"] == "up_to_date"

    # Now edit the body and re-approve explicitly.
    _write(tmp_path, "sample.py", 'def g():\n    """Doc."""\n    return 3\n')
    _run("scan", cwd=tmp_path)
    result = _run("status", "--json", cwd=tmp_path)
    assert json.loads(result.stdout)["symbols"][0]["status"] == "stale"

    approve_result = _run("approve", "sample.py:g", cwd=tmp_path)
    assert "Approved 1 symbol" in approve_result.stdout
    result = _run("status", "--json", cwd=tmp_path)
    assert json.loads(result.stdout)["symbols"][0]["status"] == "up_to_date"


def test_approve_by_path_scope(tmp_path: Path) -> None:
    _write(tmp_path, "pkg/a.py", "def f():\n    return 1\n")
    _write(tmp_path, "pkg/b.py", "def h():\n    return 2\n")
    _run("init", "--yes", cwd=tmp_path)
    result = _run("approve", "--path", "pkg", cwd=tmp_path)
    assert "Approved 2 symbol" in result.stdout


def test_check_block_mode_exits_nonzero_when_stale(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", "def g():\n    return 2\n")
    _run("init", "--yes", cwd=tmp_path)
    result = _run("check", "--mode", "block", cwd=tmp_path)
    assert result.returncode == 1
    assert "autodocstrings:" in result.stderr


def test_check_warn_mode_prints_but_exits_zero(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", "def g():\n    return 2\n")
    _run("init", "--yes", cwd=tmp_path)
    result = _run("check", "--mode", "warn", cwd=tmp_path)
    assert result.returncode == 0
    assert "autodocstrings:" in result.stdout


def test_check_off_mode_is_silent(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", "def g():\n    return 2\n")
    _run("init", "--yes", cwd=tmp_path)
    result = _run("check", "--mode", "off", cwd=tmp_path)
    assert result.returncode == 0
    assert result.stdout.strip() == ""


def test_check_all_documented_exits_zero(tmp_path: Path) -> None:
    _write(tmp_path, "sample.py", 'def g():\n    """Doc."""\n    return 2\n')
    _run("init", "--yes", cwd=tmp_path)
    result = _run("check", "--mode", "block", cwd=tmp_path)
    assert result.returncode == 0
