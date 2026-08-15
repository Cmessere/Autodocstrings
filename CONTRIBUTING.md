# Contributing

## Setup

```bash
uv sync --all-groups
```

## Before sending a change

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

All four must pass. CI (`.github/workflows/ci.yml`) runs the same checks on
Python 3.11 and 3.12.

## Conventions

- Conventional commits (`feat:`, `fix:`, `docs:`, `chore:`, ...).
- One phase/feature per commit where practical; keep commits reviewable.
- No LLM calls, network access, or watch/daemon mode in the CLI itself --
  see "Non-goals" in the design plan. The CLI is deterministic by design;
  anything that needs an LLM belongs in the agent skill layer
  (`skill/SKILL.md`), not in `src/autodocstrings/`.
- `docs/agent-contract.md` documents the `--json` output of `status` and
  `diff`. Any change to those shapes is a breaking change: bump
  `AGENT_CONTRACT_VERSION` in `src/autodocstrings/reporting.py`, update the
  doc, and update `tests/test_agent_contract.py`'s expected key sets in the
  same change.
- `docs/config.schema.json` is generated from the `Config` pydantic model
  (`src/autodocstrings/config.py`) -- regenerate it after changing the
  model:

  ```bash
  uv run python -c "import json; from autodocstrings.config import export_json_schema; print(json.dumps(export_json_schema(), indent=2))" > docs/config.schema.json
  ```

## Adding a language

New languages plug in as a `LanguageAdapter`
(`src/autodocstrings/adapters/base.py`): parse source into `Symbol`s
(`src/autodocstrings/symbols.py`), register the adapter in
`src/autodocstrings/adapters/__init__.py`, and add it to
`DEFAULT_LANGUAGES`/the language extension map in
`src/autodocstrings/config.py`. Add golden-file tests against a small
fixture file, plus the determinism and comment-invariance property tests
the existing adapters have (see `tests/test_python_adapter.py` /
`tests/test_typescript_adapter.py` for the pattern).
