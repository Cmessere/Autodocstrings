import subprocess
import sys
from pathlib import Path

import pytest


def _run(*args: str, cwd: Path, check: bool = True) -> subprocess.CompletedProcess:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(f"{args} failed: {result.stdout}\n{result.stderr}")
    return result


def _autodoc(*args: str, cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "autodocstrings.cli", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture
def git_repo(tmp_path: Path) -> Path:
    _run("git", "init", "-q", cwd=tmp_path)
    _run("git", "config", "user.email", "test@example.com", cwd=tmp_path)
    _run("git", "config", "user.name", "Test", cwd=tmp_path)
    (tmp_path / "sample.py").write_text(
        'def f():\n    """Does a thing."""\n    return 1\n', encoding="utf-8"
    )
    assert _autodoc("init", "--yes", cwd=tmp_path).returncode == 0
    _run("git", "add", "-A", cwd=tmp_path)
    _run("git", "commit", "-q", "-m", "initial", cwd=tmp_path)
    return tmp_path


def test_install_hook_writes_executable_pre_commit(git_repo: Path) -> None:
    result = _autodoc("install-hook", cwd=git_repo)
    assert result.returncode == 0, result.stderr
    hook_path = git_repo / ".git" / "hooks" / "pre-commit"
    assert hook_path.is_file()
    content = hook_path.read_text(encoding="utf-8")
    assert "autodoc check --staged" in content


def test_install_hook_is_idempotent(git_repo: Path) -> None:
    _autodoc("install-hook", cwd=git_repo)
    hook_path = git_repo / ".git" / "hooks" / "pre-commit"
    first_content = hook_path.read_text(encoding="utf-8")
    result = _autodoc("install-hook", cwd=git_repo)
    assert result.returncode == 0
    assert hook_path.read_text(encoding="utf-8") == first_content
    assert "already has an autodocstrings hook" in result.stdout


def _stage_body_edit(repo: Path) -> None:
    (repo / "sample.py").write_text(
        'def f():\n    """Does a thing."""\n    return 2\n', encoding="utf-8"
    )
    _run("git", "add", "sample.py", cwd=repo)


def test_check_staged_warn_mode_allows_commit(git_repo: Path) -> None:
    _stage_body_edit(git_repo)
    result = _autodoc("check", "--staged", "--mode", "warn", cwd=git_repo)
    assert result.returncode == 0
    assert "autodocstrings:" in result.stdout


def test_check_staged_block_mode_aborts(git_repo: Path) -> None:
    _stage_body_edit(git_repo)
    result = _autodoc("check", "--staged", "--mode", "block", cwd=git_repo)
    assert result.returncode == 1
    assert "autodocstrings:" in result.stderr


def test_check_staged_off_mode_is_silent(git_repo: Path) -> None:
    _stage_body_edit(git_repo)
    result = _autodoc("check", "--staged", "--mode", "off", cwd=git_repo)
    assert result.returncode == 0
    assert result.stdout.strip() == ""
