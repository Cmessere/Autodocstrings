# Agent contract: `--json` output

This is the interface between the `autodoc` CLI and any agent (Claude Code
skill, Copilot prompt, or otherwise) that drives it. It is versioned via
`schema_version`; any change to a shape below **must** bump that number and
be called out in the changelog.

Current version: **1**

## `autodoc status --json`

```json
{
  "schema_version": 1,
  "root": "/absolute/path/to/project",
  "generated_at": "2026-01-01T00:00:00Z",
  "symbols": [
    {
      "file": "pkg/sample.py",
      "qualified_name": "Widget.resize",
      "status": "up_to_date",
      "code_hash": "c2db9ad35aac1ae3",
      "signature_hash": "8df14b63936f874a",
      "doc_hash": "3ef6c5d3b2d94aa2",
      "approved_code_hash": "c2db9ad35aac1ae3",
      "approved_signature_hash": "8df14b63936f874a",
      "updated_at": "2026-01-01T00:00:00Z"
    }
  ]
}
```

- `status` is one of `ignored` | `never_started` | `stale` | `up_to_date`,
  derived from the hashes at read time (see `docs/config.schema.json` and
  `src/autodocstrings/state.py` for the exact rule).
- `doc_hash` / `approved_code_hash` / `approved_signature_hash` are `null`
  when not applicable (no docstring yet / never approved).
- `--only <status,status,...>` and `--path <file-or-dir>` filter the
  `symbols` list; they do not change the shape of an entry.
- This command reads the persisted `state.json` only — it does not re-parse
  source. Run `autodoc scan` first if source may have changed.

## `autodoc diff <file[:symbol]> --json`

```json
{
  "schema_version": 1,
  "symbols": [
    {
      "file": "pkg/sample.py",
      "qualified_name": "Widget.resize",
      "kind": "method",
      "status": "stale",
      "body_changed": true,
      "signature_changed": false,
      "has_docstring": true,
      "signature": "def resize(self, delta: int) -> None:",
      "docstring": "\"\"\"Resizes the widget.\"\"\""
    }
  ]
}
```

- Unlike `status`, `diff` re-parses the target file fresh, so it reflects
  the current source even if `autodoc scan` hasn't been run since the last
  edit.
- `body_changed` / `signature_changed` are computed against the *last
  approval*, not the last scan — they answer "does this symbol's code
  differ from what was last approved," which is what an agent needs before
  deciding whether to write or rewrite a docstring.
- `docstring` is the raw current docstring text (including its quote/comment
  markers), or `null` if the symbol has none.

## Recommended agent workflow

See `skill/SKILL.md` (Phase 6) for the prescribed sequence: `status --json`
scoped to what the user asked, then `diff --json` per target symbol, then
write, then `scan` + `approve` for the touched symbols only.
