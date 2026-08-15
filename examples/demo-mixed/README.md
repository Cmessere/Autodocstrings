# demo-mixed

A tiny mixed Python/TypeScript project for trying `autodocstrings` end to
end. It deliberately mixes documentation states so you can see every status:

- `src/billing.py`: `capitalise_plan_name` is documented (`up_to_date`
  after init, since `init.trust_existing` defaults to true),
  `total_with_tax` has no docstring (`never_started`), and
  `apply_discount` has a docstring that doesn't explain its `tier == 3`
  magic number -- a good case for the skill's "ask, don't invent" rule.
- `web/billing.ts`: the TypeScript mirror of the first two functions.

Try it:

```bash
cd examples/demo-mixed
autodoc init --yes
autodoc status
```

Then point the `autodocstrings` skill (see `skill/SKILL.md`) at
`total_with_tax` or `apply_discount` and watch it either write a docstring
or stop and ask a question, depending on the case.
