# autodocstrings

A deterministic CLI that tracks docstring staleness across a codebase, paired
with an agent skill that writes the docstrings.

- **The CLI never calls an LLM.** It parses source, hashes symbol bodies, and
  reports which functions/classes/methods have docs that are missing, stale,
  or up to date. No API keys, no network, no watch/daemon mode.
- **The agent writes the docstrings.** A Claude Code skill
  (`skill/SKILL.md`) and a Copilot prompt file
  (`.github/prompts/autodocstrings.prompt.md`) read the CLI's `--json`
  output and write docs that follow your configured convention and
  verbosity -- and stop to ask you when a symbol's intent isn't clear from
  the code, instead of inventing an explanation.

Status: early development (v0.1, not yet released).

## Supported languages (v0.1)

- Python (`google` | `numpy` | `sphinx` docstring conventions)
- TypeScript / JavaScript (`jsdoc` | `tsdoc`)

## Quickstart

```bash
uv tool install autodocstrings   # or: pip install autodocstrings
cd your-project
autodoc init                     # or: autodoc init --yes for defaults, no prompts
```

`init` detects which languages are present, asks for a docstring convention
per language (showing you what each verbosity level actually looks like),
asks for a git hook mode, writes `autodocstrings.config.json`, and runs the
first scan into `.autodocstrings/state.json`.

Check what needs documentation:

```bash
autodoc status
```

Wire up the git hook, so staleness is caught before it's committed:

```bash
autodoc install-hook
```

By default the hook mode is `warn` (prints a reminder, never blocks the
commit). Set `hook.mode` to `"block"` in the config once your team is ready
to enforce it. See [docs/git-hooks.md](docs/git-hooks.md) for the
pre-commit-framework and husky/lint-staged alternatives.

Then point your agent at it. In Claude Code, the skill in `skill/SKILL.md`
picks up automatically once it's on your skill path; ask it to
"document the stale functions in `src/billing.py`" and it will run
`autodoc status`/`autodoc diff`, write docstrings following your config,
run `autodoc scan` + `autodoc approve` on what it touched, and summarize
what it skipped and why. See `.github/prompts/autodocstrings.prompt.md` for
the Copilot equivalent.

Try the whole flow on a tiny mixed Python/TS project without touching your
own code: [`examples/demo-mixed/`](examples/demo-mixed/).

## The state model

Every tracked symbol (function, method, or class) has exactly one status,
computed at read time from hashes stored in `.autodocstrings/state.json` --
nothing about status itself is stored, so there's nothing to fall out of
sync:

| Status | Meaning |
|---|---|
| `ignored` | Excluded by a config glob or an inline `# autodoc: ignore` / `// autodoc: ignore` marker. |
| `never_started` | No docstring, never approved. |
| `stale` | Documented (or previously approved), but the code has changed since -- or the docstring was removed after approval. |
| `up_to_date` | Documented, and the last approval matches the current code. |

"Approving" a symbol (`autodoc approve <file>:<name>`, normally run by the
agent right after it writes a docstring) records the current `code_hash` as
the baseline for staleness detection. Editing a docstring's *wording*
without touching the code doesn't invalidate an existing approval --
staleness tracks code changes, not doc-text changes. The signature is
hashed separately from the body (`signature_hash`), so `autodoc diff` can
flag "the signature changed" distinctly from "the body changed" even when
only one of the two actually did.

`state.json` is meant to be committed: it's serialized with sorted keys and
one field per line specifically to keep git diffs small and merges clean.

## Configuration

`autodocstrings.config.json`, discovered by walking up from the current
directory (like `package.json`). Every field has a default, so an empty or
absent config file is valid. Full schema (generated from the pydantic
model): [`docs/config.schema.json`](docs/config.schema.json).

| Field | Default | Meaning |
|---|---|---|
| `include` / `exclude` | all files / common noise dirs | Glob lists (files and dirs) selecting what gets scanned. |
| `languages` | `.py`→python, `.ts`/`.tsx`/`.js`/`.jsx`/`.mjs`→typescript | Extension → adapter mapping. |
| `conventions.python` | `"google"` | `google` \| `numpy` \| `sphinx` |
| `conventions.typescript` | `"tsdoc"` | `jsdoc` \| `tsdoc` |
| `verbosity` | `"standard"` | `minimal` \| `standard` \| `detailed` -- see `skill/SKILL.md` for what each looks like. |
| `noise_policy.document_trivial` | `false` | Whether trivial/self-explanatory symbols get documented at all. |
| `noise_policy.params` | `"when_non_obvious"` | `when_non_obvious` \| `always` \| `never` |
| `noise_policy.include_examples` | `false` | Whether the agent may add `Example:` blocks. |
| `hook.mode` | `"warn"` | `off` \| `warn` \| `block` |
| `hook.block_on` | `["stale", "never_started"]` | Which statuses cause `block` mode to fail. |
| `init.trust_existing` | `true` | On first scan, treat symbols that already have a docstring as an approved baseline (`up_to_date`) rather than `stale`. |
| `state_file` | `.autodocstrings/state.json` | Where state is persisted. |

## Migrating an existing project

You don't have to document everything at once. `scan`, `status`, and
`approve` all accept:

- `--path <file-or-dir>` -- scope to an explicit path.
- `--package` -- sugar for "the nearest enclosing package from where I'm
  standing" (closest ancestor directory containing `package.json` or
  `__init__.py`). `cd src/billing && autodoc status --package` scopes to
  just that package without typing the path out, which is what makes
  package-by-package migration of a large existing codebase practical.

Neither flag ever prunes tracked state outside its scope -- a `--path`- or
`--package`-scoped scan only updates/prunes within that scope, so you can
migrate incrementally without a full-repo scan clobbering unrelated state.

With `init.trust_existing: true` (the default), a package that already has
good docs on some symbols starts those as `up_to_date` rather than forcing
a re-review of everything; symbols with no docstring still show up as
`never_started` so you can decide, package by package, when to point the
agent at them.

## Development

```bash
uv sync --all-groups
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run pyright
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for more, and
[docs/agent-contract.md](docs/agent-contract.md) for the versioned JSON
contract between the CLI and the agent skill.
