# Related Work and Upstream Status

> Review date: 2026-07-11
>
> This is a planning snapshot. Re-verify statuses before implementation or any
> novelty claim because this area changes rapidly.

## 1. Positioning Rule

The project does not claim to invent retain/offload/recompute lifecycle control.
Its planned contribution is a modern vLLM runtime artifact plus rigorous,
hardware-calibrated evaluation and failure-domain analysis.

## 2. Directly Relevant Systems

| Work | Main contribution | Overlap | Project implication |
|---|---|---|---|
| [InferCept](https://arxiv.org/abs/2402.01869) | Preserve, swap, and discard for augmented LLM interceptions; MinWaste scheduling | Direct three-action predecessor | Use as a conceptual/cost baseline; do not claim mechanism novelty |
| [Continuum](https://arxiv.org/abs/2511.02230) | Tool-aware KV TTL and program-level scheduling | Direct static/dynamic retention predecessor | Tuned TTL is mandatory; duration prediction is not novel |
| [KVFlow](https://arxiv.org/abs/2507.07400) | Workflow-aware eviction and prefetch for multi-agent prefix caches | Related workflow-level policy | Relevant to static agent graphs; not an MVP implementation target |
| [PBKV](https://arxiv.org/abs/2605.06472) | Prediction-based lifecycle-aware eviction and conservative prefetch on SGLang/HiCache | Direct prediction and robustness predecessor | Do not claim first regret/robustness; a simplified port must be labeled inspired |
| [Astraea](https://arxiv.org/abs/2512.14142) | State-aware agent scheduling and adaptive KV management during I/O waits | Direct JCT and pressure-aware predecessor | End-to-end JCT optimization is already occupied; project value is implementation/evidence, not priority |

## 3. Adjacent Contracts and Mechanisms

| Work | Focus | Relationship |
|---|---|---|
| [Resident KV Claims](https://arxiv.org/abs/2605.24259) | Admission, feasibility, lifecycle state, and telemetry for resident KV claims | Informs retention contracts, refusal semantics, and observability rather than replacement policy |
| [Leyline](https://arxiv.org/abs/2606.01065) | Policy-directed cache editing and position-correct continuation | Adjacent context-mutation problem, not the same tool-gap lifecycle decision |
| [MARCONI](https://arxiv.org/abs/2411.19379) | Cost-aware prefix-cache admission and eviction | Supports cost-aware caching concepts; not agent tool-wait specific |
| [Mooncake](https://github.com/kvcache-ai/Mooncake) | KV-centric disaggregated serving, transfer, and storage | Possible future data-plane dependency |
| [LMCache](https://github.com/LMCache/LMCache) | External KV cache, offload, sharing, and connectors | Possible future storage dependency, not the lifecycle policy itself |

## 4. vLLM Upstream Status

### Context-Aware Retention

- [RFC #37003](https://github.com/vllm-project/vllm/issues/37003) proposes
  token-range priority and duration directives.
- [PR #38514](https://github.com/vllm-project/vllm/pull/38514) implemented the
  proposal and included tests/benchmarks, but was closed without merging after
  falling behind mainline.

Implication: retention semantics cannot be assumed stable. The calibration sprint
must inspect current mainline and either use a supported contract, carry a minimal
compatibility patch, narrow the project, or contribute a focused upstream change.

### Native CPU Offload

- [RFC #19854](https://github.com/vllm-project/vllm/issues/19854) describes the
  native offloading architecture.
- [PR #37874](https://github.com/vllm-project/vllm/pull/37874) merged a pluggable
  CPU offload `CachePolicy` structure.
- [vLLM releases](https://github.com/vllm-project/vllm/releases) show continued
  work on per-request policy hooks, selective offload, tiering, and connectors.

Implication: native offload is the default MVP mechanism. Use LMCache only when a
measured requirement exceeds native capabilities.

## 5. What Remains Safe to Claim

Before implementation:

```text
The project investigates a current and role-relevant runtime problem.
Existing systems demonstrate that lifecycle-aware KV management matters.
Current engines expose partial mechanisms but their contracts and policies vary.
```

After implementation and measurement, possible claims depend on evidence:

```text
modern vLLM implementation of a documented lifecycle policy
hardware-calibrated break-even and failure-domain map
deterministic lifecycle replay and DecisionTrace
runtime correctness and fallback evidence
upstream contribution or issue reproduction
```

Unsafe without a new exhaustive review:

```text
first cross-policy evaluation
first measured regret analysis
first agent-aware KV runtime
first production-ready lifecycle API
```

## 6. Fidelity Levels

Use these labels for external policies:

| Level | Meaning | Allowed wording |
|---|---|---|
| L0 | Original artifact on original engine/workload | Native artifact replay |
| L1 | Original/reference decisions compared on shared state vectors | Decision-equivalence study |
| L2 | Direction and ordering reproduced under a different harness | Trend-level reimplementation |
| L3 | Simplified or structurally changed policy | `<work>-inspired baseline` |

Decision-equivalence against a second implementation written from the same paper
does not by itself prove fidelity. Use original cases, invariants, artifacts, and
a deviation ledger wherever possible.

## 7. Mandatory Deviation Ledger

For each reimplementation, record:

```text
original engine and commit
original cache granularity
original offload/prefetch semantics
original preemption and scheduling behavior
policy parameters and tuning procedure
changed abstraction or missing mechanism
expected impact direction
native and retuned results
```

For PBKV-to-vLLM specifically, radix-node versus block granularity, HiCache versus
vLLM connector behavior, and preemption semantics are material deviations.

## 8. Review Procedure

Before every major roadmap revision:

1. Search recent arXiv and upstream issues for direct agent KV lifecycle work.
2. Read the evaluation and limitations sections, not only the abstract.
3. Record whether the work changes mechanism novelty, baseline requirements, or
   available engine interfaces.
4. Update [DECISIONS.md](DECISIONS.md).
5. Prefer narrowing or reframing over racing a new paper on novelty.
