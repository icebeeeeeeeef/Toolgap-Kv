# Domain docs

This is a single-context repository. Engineering skills consume domain
documentation using the following layout:

```text
/
├── CONTEXT.md
├── docs/
│   └── adr/
└── src/
```

## Before exploring

- Read root `CONTEXT.md` when it exists.
- Read ADRs under `docs/adr/` that affect the area being changed.
- If either path does not exist, proceed silently. The domain-modeling workflow
  creates it lazily when the first term or durable decision is resolved.

## Vocabulary rules

`CONTEXT.md` is a glossary, not a specification or implementation plan. Use its
canonical terms in issue titles, hypotheses, tests, and design documents. If a
needed concept is absent or an existing term is overloaded, resolve the domain
language before inventing a synonym.

The existing `docs/agent-kv/` directory remains the home for project framing,
architecture, evaluation, experiment planning, and interview evidence. Do not
move those concerns into `CONTEXT.md`.

## ADR rules

Create an ADR only when the decision is all of the following:

1. costly to reverse;
2. surprising without historical context; and
3. the result of a genuine trade-off.

Surface conflicts with an existing ADR explicitly instead of silently
overriding it.
