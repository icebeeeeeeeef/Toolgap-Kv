# ToolGap-KV Documentation

> Status: `roadmap`
>
> Last reviewed: 2026-07-23
>
> Engine-independent Phase 0 contracts, seven domain-contract tests, and three
> repository-validator regression tests are `shipped` (ten local tests total).
> A0.1 has one real-GPU, pinned-vLLM `experimentally validated` negative
> full-block coverage result; the separate A0.1R experiment has a three-ordinal
> stock-APC admission result for its eligible 192-token prefix. The separate
> foreground-length qualification has experimentally validated and committed
> three A0.2 foreground input anchors (`L=2048/8192/16384`) under the supported
> chunked-prefill/HND pin. A0.2 itself remains `roadmap`: no capacity-pressure
> matrix, APC/CPU-offload comparison, measured resume metric, performance claim,
> or lifecycle runtime exists.

## One-Sentence Definition

ToolGap-KV is the repository codename for a proposed candidate-owned, in-process
paused-agent KV lifecycle runtime integrated with current vLLM, plus correctness,
attribution, and measured retain/offload/recompute boundaries.

The project's central question is:

> Can the smallest candidate-owned lifecycle controller over a maintainable
> current-vLLM seam make the three paths enforceable, observable, and safe under
> failure, then measure where each path wins or loses on the available
> single-node testbed?

Dynamic-policy superiority is a conditional Gate B question, not the project
success condition.

## Reading Order

1. [../../CONTEXT.md](../../CONTEXT.md): canonical domain terms.
2. [FIRST_PRINCIPLES.md](FIRST_PRINCIPLES.md): recruiting objective, hard gates,
   decision-card unit, and adopted scope rules.
3. [PROJECT.md](PROJECT.md): problem background, first-principles question,
   goals, non-goals, and success conditions.
4. [ROADMAP.md](ROADMAP.md): Gate A, evidence phases, Gate B, and stop branches.
5. [../../experiments/0001-mechanism-feasibility/README.md](../../experiments/0001-mechanism-feasibility/README.md):
   the first executable evidence protocol.
6. [../../experiments/A0.1R-partial-block-residual/A0.1R-results-2026-07-22.md](../../experiments/A0.1R-partial-block-residual/A0.1R-results-2026-07-22.md):
   the real-GPU stock-APC admission result and its strict boundary.
7. [ARCHITECTURE.md](ARCHITECTURE.md): proposed components, lifecycle contracts,
   decision path, and failure semantics.
8. [EVALUATION.md](EVALUATION.md): hypotheses, baselines, workloads, metrics,
   bounds, negative cases, and evidence rules.
9. [INTERVIEW_MAP.md](INTERVIEW_MAP.md): decision-card registry, organic hooks,
   claim trees, and evidence gates.
10. [NARRATIVE.md](NARRATIVE.md): candidate story, ownership boundary, interview
   framing, and resume templates.
11. [interview-grill/README.md](interview-grill/README.md): adversarial TL
   questions, evidence-gated answers, and mock-interview maintenance workflow.
12. [RELATED_WORK.md](RELATED_WORK.md): direct predecessors, adjacent systems,
   vLLM status, and fidelity rules.
13. [DECISIONS.md](DECISIONS.md): accepted, deferred, rejected, and superseded decisions.

## Current Snapshot

| Dimension | Current state |
|---|---|
| Core problem | Defined |
| Engine-independent contracts | `shipped`: events/actions/DecisionTrace scaffolding and tests |
| Runtime architecture | `roadmap`: proposed only |
| vLLM target commit | A0.1/A0.1R: `752a3a504485790a2e8491cacbb35c137339ad34` (`vLLM 0.25.1`) |
| Hardware | A0.1/A0.1R: NVIDIA A10; driver `580.126.09`; Torch CUDA `13.0` |
| Workload | Candidate sources identified; no replay built |
| Runtime code | `shipped`: engine-independent Phase 0 plus A0.1/A0.1R measurement harnesses; no candidate-owned lifecycle runtime |
| Benchmark data | `experimentally validated`: negative A0.1 full-span coverage artifact and three-ordinal A0.1R stock-APC admission artifact; raw bundles are locally retained and their hashes/commands are tracked in [A0.1 results](../../experiments/0001-mechanism-feasibility/A0.1-results-2026-07-22.md) and [A0.1R results](../../experiments/A0.1R-partial-block-residual/A0.1R-results-2026-07-22.md) |
| Simulator data | None |
| Resume claim | No positive runtime or performance bullet allowed; only the narrow A0.1/A0.1R applicability findings may be discussed with their testbed boundaries |

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
| DecisionTrace | Structured record connecting lifecycle identity, requested action, observed path, fallback, accounting, timing, and outcome |
| Testbed | The real engine, model, hardware, and workload execution environment |
| Hindsight bound | Offline comparator with explicitly stated future information and assumptions |

## Claim States

All project claims must use one of these states:

- `roadmap`: planned but not implemented.
- `shipped`: implemented and exercised in the stated system.
- `experimentally validated`: measured under a declared environment and workload.
- `simulated`: supported only by replay, trace, optimizer, cost model, or
  simulator; calibration limits must be stated.

An artifact can have different states on different axes. For example:

```text
execution: experimentally validated on a real GPU testbed
workload: trace-derived synthetic
scale: single-node and truncated relative to production
```

## Scope Boundary

The mainline owns one bounded evidence chain: a candidate-owned in-process
lifecycle controller, current-vLLM integration, correctness/fallback, and measured
retain/offload/recompute boundaries. The controller owns logical identity/epochs,
legal transitions, idempotence, asynchronous-completion fencing, action
orchestration, fallback, cancellation, cleanup, and DecisionTrace. A logging-only
adapter, proxy, or external benchmark is supporting evidence, not the mechanism.
Dynamic selection is Gate B-only.

vLLM remains the physical KV data plane for shared block residency/refcounts,
eviction, PagedAttention, model execution, and native D2H/H2D movement. Reusing
those capabilities is the intended design, not a reduction in candidate ownership.

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

Those items require independent project review even after CT1-CT3 succeed.

## Maintenance Rules

1. Pin source links, dependency commits, model versions, and hardware manifests.
2. Add measurements only with the exact command, workload, and raw artifact.
3. Keep negative results; do not remove paths or workloads where the mechanism or
   selected action loses.
4. Update [DECISIONS.md](DECISIONS.md) when a major scope or mechanism changes.
5. Update [RELATED_WORK.md](RELATED_WORK.md) before claiming novelty.
6. Never convert roadmap bullets into resume bullets by changing verb tense.

## Immediate Next Decision

Execute Gate A in [ROADMAP.md](ROADMAP.md). First complete the capability matrix;
then prove a viable controller seam with one candidate-owned lifecycle transition,
obtain a pinned-vLLM requested-to-observed nominal raw trace, add one
source-audited fault/fallback fixture, and close the first decision card. A
trace-only observer cannot pass the ownership gate. A performance/applicability
negative case is useful but cannot replace the safety fixture. Gate A's purpose
is not to prove a speedup.
