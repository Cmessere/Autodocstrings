---
name: autodocstrings
description: Writes and updates docstrings using the autodocstrings CLI's staleness tracking. Use when the user asks to document a function/class/module, update stale docstrings, "run autodocstrings", or catch up docs after a refactor. The CLI never writes docs itself -- it only reports what's missing/stale via JSON; this skill does the writing.
---

# autodocstrings

`autodoc` is a deterministic CLI: it parses source, hashes symbol bodies,
and reports which functions/classes/methods have documentation that is
missing, stale, or up to date. **It never calls an LLM and never writes a
docstring itself.** You are the agent that does the writing, guided by its
`--json` output.

## Workflow

1. **Get the target list.** Run `autodoc status --json`, scoped to what the
   user asked for:
   - Whole repo: `autodoc status --json`
   - One file or directory: `autodoc status --path <path> --json`
   - Only what needs work: add `--only stale,never_started`

   If `autodoc status` fails because there's no config/state yet, run
   `autodoc init --yes` first (or ask the user if they'd rather answer the
   wizard's prompts themselves), then re-run `status`.

2. **Read the config before writing anything.** Open
   `autodocstrings.config.json` (or note the defaults if absent) for:
   - `conventions` (e.g. `google`/`numpy`/`sphinx` for Python,
     `jsdoc`/`tsdoc` for TS/JS) -- per language, not your own preference.
   - `verbosity` (`minimal` / `standard` / `detailed`) and `noise_policy`
     -- these control how much you're allowed to write. See the few-shot
     examples below for what each verbosity level actually looks like.

3. **For each target symbol, run `autodoc diff <file>:<qualified_name>
   --json`** and then **read the actual source** at the reported location.
   `diff` tells you whether the body and/or signature changed since the
   last approval, and gives you the current signature text and any
   existing docstring -- but you still need to read the real code to
   understand *what it does*, especially for the noise-policy judgment
   call in the next step.

4. **Write the docstring**, following the convention and verbosity from
   the config.

   **Noise policy -- this is the most important rule after "never assume"
   below:**
   - A trivial, self-explanatory function gets **one line and nothing
     more**. `capitalise_string(value)` -> `"""Capitalises the string."""`.
     Do not add an `Args:`/`Returns:` section to a one-line-obvious
     function just because a convention technically allows it, unless
     `noise_policy.params` is `"always"`.
   - Add explanatory notes **only** for non-obvious business logic, hidden
     side effects, surprising data structures, or real edge cases -- e.g.
     a function builds a hashmap for an uncommon purpose: say *why* in one
     sentence, not what a hashmap is.
   - Never pad a docstring with an `Example:` block unless
     `noise_policy.include_examples` is true.

5. **Never assume.** If the symbol's intent is unclear -- magic
   numbers/strings with no explanation, a branch whose condition doesn't
   obviously map to a real-world case, an ambiguous or misleading name,
   behavior that depends on external state you can't see -- **stop and ask
   the user** instead of writing a plausible-sounding but invented
   docstring. Report it as skipped, not documented.

6. **After editing, run `autodoc scan` then `autodoc approve
   <file>:<qualified_name>`** for each symbol you actually touched (or
   `autodoc approve --path <path>` if you touched everything under a
   scope). Do not approve symbols you skipped in step 5.

7. **End with a summary**: which symbols were updated, which were skipped
   pending a question to the user (and what the question is), and which
   were left alone because they were already `up_to_date`.

## Few-shot examples

### Trivial vs. non-obvious (noise policy)

Trivial -- one line, done:

```python
def capitalise_string(value: str) -> str:
    """Capitalises the string."""
    return value[:1].upper() + value[1:]
```

Non-obvious -- the *why* earns a sentence, still no padding:

```python
def build_lookup(records: list[Record]) -> dict[str, list[Record]]:
    """Groups records by owner_id.

    Uses a dict instead of sorting because callers hit this per-request
    and the owner set is usually small enough that hashing wins.
    """
    ...
```

### Ambiguous -- ask, don't invent

```python
def process(item, mode=2):
    if mode == 2:
        return item.value * FACTOR
    return item.value
```

Do **not** write "Processes the item using the given mode." That's a
paraphrase, not documentation -- it doesn't say what `mode=2` versus other
modes *mean*, because the code doesn't say either. Skip this symbol and
ask: "`process()` branches on `mode == 2` using an undocumented `FACTOR`
constant -- what do the different `mode` values represent?"

### One example per convention

**Google (Python):**

```python
def resize(self, width: int, height: int) -> None:
    """Resizes the widget.

    Args:
        width: New width in pixels.
        height: New height in pixels.
    """
```

**NumPy (Python):**

```python
def resize(self, width: int, height: int) -> None:
    """Resizes the widget.

    Parameters
    ----------
    width : int
        New width in pixels.
    height : int
        New height in pixels.
    """
```

**Sphinx (Python):**

```python
def resize(self, width: int, height: int) -> None:
    """Resizes the widget.

    :param width: New width in pixels.
    :param height: New height in pixels.
    """
```

**JSDoc (TS/JS):**

```ts
/**
 * Resizes the widget.
 * @param width - New width in pixels.
 * @param height - New height in pixels.
 */
resize(width: number, height: number): void {
```

**TSDoc (TS/JS):**

```ts
/**
 * Resizes the widget.
 * @param width - New width in pixels.
 * @param height - New height in pixels.
 */
resize(width: number, height: number): void {
```

(TSDoc and JSDoc look nearly identical for simple cases; the difference
shows up in richer tags like `@remarks`/`@typeParam`. Follow whichever the
config specifies.)

## Hard rules

- Never invent behavior that isn't in the code.
- Never run `autodoc approve` on a symbol you didn't actually write/verify
  the docs for.
- Never write docs for a symbol reported as `ignored`.
- If `autodoc` isn't installed or the repo has no config, offer to run
  `autodoc init` rather than guessing at conventions yourself.
