# Collaboration rules

## User instructions

- 我是一个软件工程师。
- 我更倾向于你和我一起讨论实施的方案正确性，不需要你因为我的决策妥协。
- 我允许你大胆地质疑我的决策，但是必须给出充分的理由。
- 在尝试反驳我的时候，尝试通过第一性原理分析，或者通过对抗式审查的方式找漏洞。

## Project evidence rules

- Keep claims in one of the states defined by `docs/agent-kv/README.md`:
  `roadmap`, `shipped`, `experimentally validated`, or `simulated`.
- Do not describe vLLM integration, GPU measurements, or performance results as
  complete until the corresponding repository artifacts exist and pass checks.
- Prefer the smallest maintainable vLLM extension point. A core fork requires a
  demonstrated missing contract and an auditable patch under `patches/`.
- Preserve negative results and update `docs/agent-kv/DECISIONS.md` when evidence
  changes a major project choice.
- Treat the project as recruiting evidence for LLM Serving / AI Infra engineering,
  not as a paper-novelty race. Prior art changes attribution and baselines before
  it changes scope.
- Keep CT1 integration, CT2 correctness/recovery, and CT3 measured boundary as
  the unconditional mainline. Dynamic policy is CT4 and requires Gate B in
  `docs/agent-kv/ROADMAP.md`.
- Treat a candidate-owned, in-process logical lifecycle runtime as a CT1-CT3
  completion requirement. It must own lifecycle identity/epochs, legal
  transitions, idempotence, asynchronous-completion fencing, fallback,
  cancellation, cleanup, and DecisionTrace. A trace-only adapter or external
  benchmark does not satisfy runtime ownership.
- Reuse vLLM's physical KV data plane: block residency/reference counting,
  eviction, PagedAttention, model execution, and native D2H/H2D movement remain
  dependencies unless Gate A proves one narrowly missing contract.
- Use closed decision cards in `docs/agent-kv/INTERVIEW_MAP.md` as the unit of
  progress. Documentation or planned hooks alone do not close a card.
- Treat `docs/research/` as historical/research input, never as the current roadmap.

## Agent skills

### Issue tracker

Issues and Wayfinder maps live in GitHub Issues for
`icebeeeeeeeef/Toolgap-Kv`. See `docs/agents/issue-tracker.md`.

### Triage labels

Use the repository's five-role triage vocabulary. See
`docs/agents/triage-labels.md`.

### Domain docs

This is a single-context repository using root `CONTEXT.md` and `docs/adr/`.
See `docs/agents/domain.md`.
