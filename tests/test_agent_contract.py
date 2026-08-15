"""Snapshot tests for the `--json` schemas documented in docs/agent-contract.md.

Any change to these key sets is a breaking change to the agent contract and
must be intentional -- if one of these fails, update
docs/agent-contract.md (and bump AGENT_CONTRACT_VERSION) before touching
the assertion.
"""

from __future__ import annotations

from pathlib import Path

from autodocstrings.config import Config
from autodocstrings.project_scan import scan_project
from autodocstrings.reporting import (
    AGENT_CONTRACT_VERSION,
    build_diff_entries,
    build_status_entries,
)
from autodocstrings.state import State

STATUS_ENTRY_KEYS = {
    "file",
    "qualified_name",
    "status",
    "code_hash",
    "signature_hash",
    "doc_hash",
    "approved_code_hash",
    "approved_signature_hash",
    "updated_at",
}

DIFF_ENTRY_KEYS = {
    "file",
    "qualified_name",
    "kind",
    "status",
    "body_changed",
    "signature_changed",
    "has_docstring",
    "signature",
    "docstring",
}


def test_agent_contract_version_is_documented_value() -> None:
    assert AGENT_CONTRACT_VERSION == 1


def test_status_entry_shape(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text('def f():\n    """Doc."""\n    return 1\n', encoding="utf-8")
    state = scan_project(tmp_path, Config(), State())
    entries = build_status_entries(state)
    assert entries
    assert set(entries[0]) == STATUS_ENTRY_KEYS


def test_diff_entry_shape(tmp_path: Path) -> None:
    (tmp_path / "a.py").write_text('def f():\n    """Doc."""\n    return 1\n', encoding="utf-8")
    config = Config()
    state = scan_project(tmp_path, config, State())
    entries = build_diff_entries(tmp_path, "a.py", "f", config, state)
    assert entries
    assert set(entries[0]) == DIFF_ENTRY_KEYS
