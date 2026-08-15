# autodocstrings

A deterministic CLI that tracks docstring staleness across a codebase, paired
with an agent skill that writes the docstrings.

- **The CLI never calls an LLM.** It parses source, hashes symbol bodies, and
  reports which functions/classes have docs that are missing, stale, or
  up to date. No API keys, no network.
- **The agent writes the docstrings.** A Claude Code skill (and a Copilot
  prompt file) read the CLI's `--json` output and write docs that follow your
  configured convention and verbosity.

Status: early development (v0.1, not yet released).

## Quickstart

```bash
uv tool install autodocstrings
autodoc init
```

(Full quickstart — init → hook → skill — will be filled in during Phase 7.)

## Supported languages (v0.1)

- Python (`google` | `numpy` | `sphinx` docstring conventions)
- TypeScript / JavaScript (`jsdoc` | `tsdoc`)

## Development

```bash
uv sync
uv run pytest
uv run ruff check .
uv run pyright
```

See [docs/agent-contract.md](docs/agent-contract.md) for the JSON contract
between the CLI and the agent skill.
