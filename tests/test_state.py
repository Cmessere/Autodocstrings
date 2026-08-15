from autodocstrings.state import SymbolState, compute_status


def _symbol(**overrides) -> SymbolState:
    defaults = dict(
        code_hash="c1",
        signature_hash="s1",
        doc_hash=None,
        approved_code_hash=None,
        updated_at="2026-01-01T00:00:00Z",
        ignored=False,
    )
    defaults.update(overrides)
    return SymbolState(**defaults)


def test_never_started_no_doc_no_approval() -> None:
    assert compute_status(_symbol()) == "never_started"


def test_stale_doc_present_never_approved() -> None:
    assert compute_status(_symbol(doc_hash="d1")) == "stale"


def test_up_to_date_doc_present_approval_matches() -> None:
    sym = _symbol(doc_hash="d1", approved_code_hash="c1")
    assert compute_status(sym) == "up_to_date"


def test_stale_approved_but_code_changed() -> None:
    sym = _symbol(code_hash="c2", doc_hash="d1", approved_code_hash="c1")
    assert compute_status(sym) == "stale"


def test_stale_approved_but_docstring_removed() -> None:
    sym = _symbol(doc_hash=None, approved_code_hash="c1", code_hash="c1")
    assert compute_status(sym) == "stale"


def test_ignored_overrides_everything() -> None:
    sym = _symbol(doc_hash="d1", approved_code_hash="c1", ignored=True)
    assert compute_status(sym) == "ignored"
