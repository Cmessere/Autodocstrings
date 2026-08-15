# Skill eval checklist (manual)

Run the `autodocstrings` skill (or the Copilot prompt) against both fixture
projects (`examples/fixture-python/`, `examples/fixture-ts/`) and confirm
each case below. This is a manual checklist for now -- there's no automated
LLM-in-the-loop eval in v0.1 (see "Non-goals").

Setup:

```bash
cd examples/fixture-python   # or examples/fixture-ts
autodoc init --yes
```

## Cases

- [ ] **`never_started` symbol.** Pick an undocumented function (e.g.
  `undocumented_add` / `undocumentedAdd`). The agent should write a
  docstring, then run `autodoc scan` + `autodoc approve` for it, and
  `autodoc status` should report it `up_to_date` afterward.

- [ ] **`stale` symbol.** Edit a documented function's body (change the
  return expression) without touching its docstring, run `autodoc scan`
  so it shows `stale`, then run the skill. It should update the docstring
  if the behavior described actually changed, approve it, and `status`
  should show `up_to_date`.

- [ ] **Trivial function stays a one-liner.** For a simple, self-explanatory
  function (e.g. `capitalise_string`), the written/updated docstring must
  be a single line -- no `Args:`/`Returns:` padding, no invented examples,
  unless `noise_policy` in the config says otherwise.

- [ ] **Tricky function gets a note.** For a function whose logic isn't
  obvious from its name/signature alone (e.g. `cached_lookup`, decorated
  with `@lru_cache` for a non-obvious reason), the docstring should include
  a short *why* sentence -- not just a restatement of the code.

- [ ] **Ambiguous function triggers a question, not an invented doc.**
  Add a function with an unexplained magic value or mode branch (see the
  "ambiguous" example in `skill/SKILL.md`). The agent must stop and ask the
  user what the branch/constant means, report the symbol as skipped in its
  summary, and must **not** run `autodoc approve` on it.

- [ ] **Ignored symbols are left alone.** A symbol preceded by
  `# autodoc: ignore` / `// autodoc: ignore` should not appear as a task
  and the agent should not touch it even if asked to "document everything
  in this file."

- [ ] **Convention is read from config, not guessed.** Change
  `conventions.python` (or `.typescript`) in
  `autodocstrings.config.json` and re-run on a `never_started` symbol --
  the docstring format should follow the new setting.

- [ ] **Summary is accurate.** The agent's final summary lists exactly the
  symbols it updated and exactly the symbols it skipped (with the
  question asked for each skipped one) -- cross-check against
  `autodoc status --json` after the run.
