# ToolGap-KV Documentation

> Status: `roadmap`
>
> Last reviewed: 2026-07-11
>
> No implementation, GPU result, upstream contribution, or measured resume claim exists yet.

## One-Sentence Definition

ToolGap-KV is an agent-aware KV-cache lifecycle runtime for vLLM. When an
agent pauses for a tool call, the runtime chooses whether to retain its KV
cache in GPU HBM, offload it to a lower tier, or evict it and recompute on
resume.

The project's central question is:

> Under which hardware-cost ratios, memory-pressure regimes, and tool-gap
> distributions does a dynamic lifecycle policy outperform a tuned static TTL?

## Reading Order

1. [PROJECT.md](PROJECT.md): problem background, first-principles question,
   goals, non-goals, and success conditions.
2. [ARCHITECTURE.md](ARCHITECTURE.md): components, lifecycle state machine,
   decision path, and failure semantics.
3. [ROADMAP.md](ROADMAP.md): calibration sprint, MVP, research-grade system,
   and optional distributed extensions.
4. [EVALUATION.md](EVALUATION.md): hypotheses, baselines, workloads, metrics,
   bounds, negative cases, and evidence rules.
5. [NARRATIVE.md](NARRATIVE.md): candidate story, ownership boundary, interview
   framing, and resume templates.
6. [interview-grill/README.md](interview-grill/README.md): adversarial TL
   questions, evidence-gated answers, and mock-interview maintenance workflow.
7. [RELATED_WORK.md](RELATED_WORK.md): direct predecessors, adjacent systems,
   vLLM status, and fidelity rules.
8. [DECISIONS.md](DECISIONS.md): accepted, deferred, and rejected decisions.

## Current Snapshot

| Dimension | Current state |
|---|---|
| Core problem | Defined |
| Architecture | Roadmap design only |
| vLLM target commit | Not pinned |
| Hardware | Not recorded |
| Workload | Candidate sources identified; no replay built |
| Runtime code | None |
| Benchmark data | None |
| Resume claim | Not allowed yet |

## Core Glossary

| Term | Meaning in this project |
|---|---|
| Tool gap | Time between an agent emitting a tool call and receiving its result |
| Retain | Keep eligible KV blocks resident in GPU HBM during the gap |
| Offload | Store eligible KV blocks in a lower tier and restore them on resume |
| Recompute | Release reusable KV and repeat prefill when the request resumes |
| Resume TTFT | Time from tool-result arrival to the first newly generated token |
| JCT | End-to-end completion time of the full agent job |
| Goodput@SLO | Completed jobs per unit time that satisfy the declared latency SLO |
| DecisionTrace | Structured record connecting runtime state, policy choice, and outcome |
| Testbed | The real engine, model, hardware, and workload execution environment |
| Hindsight bound | Offline comparator with explicitly stated future information and assumptions |

## Claim States

All project claims must use one of these states:

- `roadmap`: planned but not implemented.
- `shipped`: implemented and exercised in the stated system.
- `experimentally validated`: measured under a declared environment and workload.
- `simulated`: supported only by a trace, model, optimizer, or simulator.

An artifact can have different states on different axes. For example:

```text
execution: experimentally validated on a real GPU testbed
workload: trace-derived synthetic
scale: single-node and truncated relative to production
```

## Scope Boundary

The mainline owns one mechanism: lifecycle selection for paused agent KV state.

MVP dependencies and baselines may include vLLM native offload, a static TTL,
soft retention, and recomputation. The following are not part of the MVP:

```text
SGLang adapter
full PBKV reimplementation
LMCache or Mooncake as a mandatory backend
NVMe or remote tier
multi-node routing
Kubernetes or AIBrix deployment
CUDA kernel work
production-scale claims
```

Those items may become independent extensions only after the main hypothesis is
validated.

## Maintenance Rules

1. Pin source links, dependency commits, model versions, and hardware manifests.
2. Add measurements only with the exact command, workload, and raw artifact.
3. Keep negative results; do not remove workloads where the policy loses.
4. Update [DECISIONS.md](DECISIONS.md) when a major scope or mechanism changes.
5. Update [RELATED_WORK.md](RELATED_WORK.md) before claiming novelty.
6. Never convert roadmap bullets into resume bullets by changing verb tense.

## Immediate Next Decision

Run the calibration sprint in [ROADMAP.md](ROADMAP.md). Its purpose is not to
prove a speedup. It determines whether current vLLM APIs, available hardware,
and repeatable workloads can support a credible project at all.
