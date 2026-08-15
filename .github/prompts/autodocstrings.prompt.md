---
mode: agent
description: Write/update docstrings using the autodocstrings CLI's staleness tracking.
---

You are updating docstrings using the `autodoc` CLI. It is fully
deterministic (parses source, hashes symbol bodies, no LLM calls) and never
writes documentation itself -- you do the writing, guided by its JSON
output.

Follow this contract exactly:

1. Run `autodoc status --json` (add `--path <path>` to scope to what the
   user asked about, `--only stale,never_started` to focus on what needs
   work). If it fails because there's no config yet, run
   `autodoc init --yes` first.
2. Read `autodocstrings.config.json` for `conventions` (per-language
   docstring style) and `verbosity`/`noise_policy` before writing anything.
3. For each target symbol, run
   `autodoc diff <file>:<qualified_name> --json` and read the real source
   at that location.
4. Write the docstring in the configured convention and verbosity:
   - Trivial, self-explanatory symbols get **one line, nothing more**.
   - Add a sentence of explanation only for non-obvious logic, hidden side
     effects, or real edge cases -- never pad with boilerplate sections
     the noise policy doesn't call for.
5. **Never assume.** If intent is unclear (magic values, unexplained
   branches, ambiguous naming), stop and ask the user instead of writing a
   plausible-sounding but invented docstring. Report the symbol as
   skipped, with your question.
6. After editing, run `autodoc scan` then
   `autodoc approve <file>:<qualified_name>` for each symbol you actually
   documented -- never approve one you skipped.
7. Finish with a summary: symbols updated, symbols skipped pending a
   question (state the question), symbols already up to date.

Full workflow, few-shot examples per convention (google/numpy/sphinx for
Python, jsdoc/tsdoc for TS/JS), and the noise-policy rationale live in
`skill/SKILL.md` in this repository -- read it if you need the worked
examples.
