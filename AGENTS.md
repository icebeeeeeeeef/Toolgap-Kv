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
