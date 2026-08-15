# Git hook setup

`autodoc check --staged` is the hook entrypoint. It exits 1 (only in
`block` mode) when staged files contain symbols whose status is in
`hook.block_on` (default: `stale` and `never_started`). `warn` mode prints
the same message but always exits 0; `off` is silent and exits 0.

## Option 1: native git hook

```bash
autodoc install-hook
```

Writes (or appends to, if one already exists) `.git/hooks/pre-commit` with:

```sh
# >>> autodocstrings hook >>>
autodoc check --staged
# <<< autodocstrings hook <<<
```

If a `pre-commit` hook already exists and doesn't already contain this
block, `install-hook` asks before appending (`--force` skips the prompt).

## Option 2: the [pre-commit](https://pre-commit.com) framework

This repo ships `.pre-commit-hooks.yaml`, so any project can reference it
directly in `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/<org>/autodocstrings
    rev: v0.1.0
    hooks:
      - id: autodocstrings-check
```

## Option 3: husky + lint-staged (JS-first repos)

```bash
npx husky init
```

`.husky/pre-commit`:

```sh
autodoc check --staged
```

`autodoc` still needs to be installed and on `PATH` (e.g. via `pip`/`uv
tool install`, or as a dev dependency invoked through `npx`/a package
script) -- husky only wires up *when* it runs, not how it's installed.
