# Project Definition

## 1. Problem Background

An ordinary LLM request performs two broad stages:

```text
prompt -> prefill -> autoregressive decode -> completion
```

Prefill computes attention keys and values for the prompt. These tensors are
stored in the KV cache so later decode steps do not recompute the whole history.

An agent workload introduces an interruption:

```text
LLM segment -> tool call -> external wait -> tool result -> next LLM segment
```

During the tool wait, the previous KV cache is idle but potentially reusable.
With multiple concurrent agents, preserving all paused sessions consumes GPU
HBM and can block active work. Evicting all paused sessions frees HBM but forces
recomputation when they resume. Offloading to CPU DRAM avoids recomputation but
consumes transfer bandwidth and adds restore latency.

The runtime therefore has three actions:

| Action | Benefit | Cost |
|---|---|---|
| Retain | Fastest resume | Occupies scarce HBM during the gap |
| Offload | Releases HBM and preserves computation | Store/restore latency and bandwidth contention |
| Recompute | No storage or transfer cost while waiting | Repeats prefill when the agent resumes |

Whether more than one action is preferable in reachable regimes is an empirical
question. It must not be assumed before Gate B.

## 2. Precise Problem Statement

On one pinned current-vLLM build, implement and verify the smallest
candidate-owned, in-process logical lifecycle controller that can orchestrate,
observe, and attribute `retain`, `offload`, and `recompute`; make transitions,
fallback, cancellation, and cleanup safe; then measure their boundary under
declared HBM, transfer, compute, and load conditions. Reuse vLLM's physical block
and tensor-transfer data plane rather than implementing a second one.

## 3. Falsifiable Question

> Can a candidate-owned lifecycle controller integrated at the smallest
> maintainable current-vLLM seam make paused-agent KV actions enforceable,
> observable, safe under failure, and quantitatively attributable enough to map
> retain/offload/recompute boundaries on the available single-node testbed?

This question is intentionally narrower than building a general inference
gateway or distributed KV store.

### Upstream Relationship and Route Boundary

vLLM's open [RFC #37003](https://github.com/vllm-project/vllm/issues/37003)
proposes an engine-owned retention-priority/duration API: an orchestrator supplies
intent and the scheduler still arbitrates shared physical KV eviction. This is a
candidate **narrow engine contract** (route C), not evidence that a full native
agent tool-wait/resume state machine (route B) belongs in vLLM.

ToolGap-KV therefore tests a narrower proposition on its pinned version: can an
in-process lifecycle layer use existing request-scoped seams for the supported
offload/recompute cases, while vLLM keeps physical arbitration? It must not claim
to express RFC-style retention priority unless the pinned seam actually provides
that contract. If it does not, the required unmodified-vLLM failing test is
evidence for a narrow retention interface, not permission to introduce a broad
scheduler or agent-orchestration fork.

**Terminology guard:** V1's removal of the V0 scheduler/preemption
`--swap-space` path does not mean that all CPU-tier KV movement disappeared.
This project uses only the independent `OffloadingConnector`/KVConnector store-
and-load path when available; it does not call that path preemption swapping.
The fixed source records the V1 swap removal in
[metrics.md](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/docs/design/metrics.md#L511-L514)
and the separate offload seam in the source audit.

It has three unconditional contract trunks:

1. **CT1 integration:** identify the smallest supported seam and execute one real
   request through candidate-owned lifecycle-controller code, from requested
   action to observed execution.
2. **CT2 correctness and recovery:** implement compatibility, visibility, epoch,
   legal-transition, idempotence, cancellation, failure, cleanup, stale-completion,
   and fallback semantics in that controller.
3. **CT3 measured boundary:** separate queue, store, restore, prefill, first-token,
   active-request, and tail effects across positive and negative regions.

### Conditional Gate B Question

Only after CT1-CT3 produce real evidence ask:

> Do at least two reachable regimes prefer different actions, and can a transparent
> dynamic selector beat tuned static/action-only baselines without unacceptable
> overhead or tail regression?

## 4. Hypothesis and Causal Chain

### Mainline Hypotheses

1. A canonical tool-call round trip can reproduce a long enough exact token
   prefix between R0's processed sequence and R1's pre-tool-result prefix. If it
   cannot, the primary problem is canonical serialization/token compatibility,
   not ToolGap-KV residency; this runtime mainline stops or is reselected.
2. Under a pre-registered pressure regime, stock APC and stock APC plus native
   offload leave a measurable, attributable recovery boundary. If the stock
   paths are sufficient on every declared regime, this runtime mainline stops or
   narrows rather than claiming an optimization.
3. Current vLLM can expose at least CPU-restore and full-recompute paths, and
   preferably GPU-hit, to a candidate-owned logical controller through an
   auditable extension or minimal patch.
4. Requested action, observed action, and allowed fallback can be distinguished
   from token/block accounting and runtime events.
5. Restore and recompute boundaries can be measured on the same real engine path,
   including at least one losing condition and active-request guardrails.

### Gate A0 Preconditions: Token Compatibility and Stock Sufficiency

After the source audit but before candidate-owned controller code, Gate A0 has
two hard gates:

1. **Token-round-trip gate.** Persist R0's actual processed token sequence and
   R1's rendered prompt sequence. Compare R0 with R1 only through the token
   immediately before the first tool-result token. The longest common prefix
   must cover the canonical assistant tool-call representation through its last
   reusable full block, with any deliberate template terminator difference
   declared. A generic early mismatch is a stop/reselection result, not merely a
   low cache-hit datapoint.
2. **Stock-sufficiency gate.** On the same pinned workload, compare stock APC
   (S0) with stock APC plus native CPU offload (S1), before comparing either with
   ToolGap code. This decides whether a physical recovery gap exists at all.

Gate A0 preregisters rather than searches for a favorable region. The manifest
must define, before the first S0/S1 comparative trace: `M = active_unique_KV /
usable_HBM`, the low/target/overload M bands, the exact prefix-length L points,
the tool-gap G points, arrival/background workload, repetitions, primary metrics,
and stop/win interpretation. Values may be calibrated from model KV size and
hardware capacity, but may not be moved after seeing a comparative outcome.

### Causal Chain

```text
canonical tool-call history round-trips to an exact token prefix
    -> APC may reuse its complete blocks without any ToolGap code
    -> tool waits plus concurrent agents may create HBM pressure and eviction
    -> stock APC/offload may or may not leave a recovery-cost boundary
    -> only then do lifecycle-related actions have a candidate problem to solve
    -> current runtime contracts determine which actions are expressible and visible
    -> correctness/fallback determines which observations are trustworthy
    -> real measurements reveal whether and where action preference changes
    -> only then can a selector be justified or rejected
```

If only one action wins, a tuned static policy is sufficient, or current hooks
cannot support attributable selection, CT4 is retired. CT1-CT3 remain valid
runtime integration, correctness, and measurement evidence.

## 5. First-Principles Cost Model

The initial model is deliberately transparent:

```text
C_retain = HBM opportunity cost(bytes, gap, pressure)

C_offload = T_store(bytes, contention)
          + P(resume) * T_restore(bytes, contention)
          + failure and queue penalties

C_recompute = P(resume) * T_prefill(tokens, batch, load)
```

This model initially organizes measurement; it is not an implemented online
policy. Gate A forces actions and records observed outcomes. Only Gate B may use
calibrated estimates for online selection. Hardware names are not substitutes
for measured curves.

## 6. Target Users and Role Alignment

The immediate user is an inference-platform engineer evaluating agent workloads
on a self-hosted vLLM deployment.

The project is aligned with these role families:

```text
LLM Serving Engineer
Inference Runtime Engineer
AI Infrastructure Engineer
ML Systems Engineer
Model Serving Platform Engineer
```

It primarily demonstrates runtime integration, stateful scheduling, memory/data
movement trade-offs, concurrency correctness, performance evaluation, and
failure handling. It is not positioned as model research or CUDA-kernel work.

## 7. Goals

1. Pin and source-audit one current vLLM release/commit.
2. Implement the smallest in-process lifecycle controller, via a supported
   extension or auditable patch, that owns lifecycle identity/epochs, legal
   transitions, idempotence, async-completion fencing, action orchestration,
   fallback, cancellation, cleanup, and DecisionTrace.
3. Strengthen DecisionTrace so every action, fallback, token/block outcome, and
   relevant timing can be attributed.
4. Close correctness cards for at least one real or injected failure plus cleanup.
5. Measure prefill, store, restore, pressure, active-request, and tail boundaries.
6. Preserve a losing workload and one rejected design with concrete evidence.
7. Produce at least five closed decision cards and a reproducible work sample.
8. Consider a transparent selector only after Gate B passes.

## 8. Non-Goals

The mainline does not attempt to:

- train or modify the base LLM;
- invent attention kernels or replace PagedAttention;
- reimplement vLLM block residency/refcounts, eviction, model execution, or
  native D2H/H2D tensor movement;
- build a general-purpose distributed KV store;
- reproduce all of InferCept, Continuum, PBKV, or Astraea;
- claim production validation from a single-node testbed;
- use multiple engines merely for technology coverage;
- claim a first or novel lifecycle mechanism;
- require an upstream issue or PR to declare the project successful;
- make NIXL fencing, a KV state ledger, a deadline controller, or a hint gateway
  an automatic fallback project.

## 9. Success Conditions

The project is successful as a runtime project when it provides:

```text
one pinned and reproducible current-vLLM integration
one candidate-owned in-process lifecycle controller with tested transitions,
epochs, idempotence, async-completion fencing, fallback, cancellation, and cleanup
one real request whose lifecycle behavior is changed and traced through that controller
requested -> observed -> fallback attribution
one correctness failure or injected failure plus regression test
one quantitatively defended transfer/recompute/HBM trade-off
one losing or negative operating region
at least five closed decision cards across CT1-CT3: integration, attribution,
identity/epoch, recovery/cleanup, and measured boundary; optional queue/TTL cards
must not be required for a valid narrowed branch
an explicit ownership and validity boundary
```

Dynamic policy is not required. A credible conformance, correctness, and
failure-domain map is more valuable than a selectively reported speedup.
A trace-only hook, telemetry adapter, replay harness, or external benchmark cannot
satisfy these runtime-project success conditions.

## 10. Stop and Pivot Conditions

Stop or narrow the current branch when any of these holds:

1. Current vLLM APIs cannot express the required lifecycle semantics without a
   large, unstable fork.
2. One action dominates across all reachable cost regimes on available hardware.
3. Repeated experiments cannot isolate mechanism effects from run-to-run noise.
4. A tuned static/action-only baseline is sufficient across reachable regimes.
5. The work remains outside the serving process and cannot own a runtime contract.
6. Stock vLLM already owns every relevant lifecycle semantic and Gate A cannot
   identify a non-duplicative candidate-owned transition, fallback, or
   correctness contract.

Valid in-project reductions include an offload/recompute controller plus boundary
study, or a demonstrated missing-contract diagnosis plus minimal patch. A
benchmark or negative-result report with no owned lifecycle semantic remains a
valuable artifact but does not complete this recruiting runtime; it triggers
mainline reselection. The workload harness remains supporting infrastructure, not
a separate recruiting project. A newly published predecessor changes positioning
and baselines; it does not by itself trigger a pivot.

## 11. Project Scale

These are roadmap estimates, not completed work:

| Level | Scope | Approximate engineering magnitude |
|---|---|---|
| Gate A | Capability matrix, pinned engine, controller vertical slice, nominal real trace, source-audited fault/fallback fixture, first closed card | 30-45 hours; target two weeks |
| Contract evidence | Candidate-owned lifecycle controller, vLLM adapters, requested/observed/fallback, concurrency and correctness failures | 70-110 hours after Gate A |
| Boundary evidence | Workload/replay, profiler, transfer/recompute/pressure experiment, losing region | 70-105 hours |
| Gate B0 and packaging | Strongest fair static/action-only baseline, evidence ledger, cards, reproducibility | 30-60 hours |
| Core CT1-CT3 total | Runtime, tests, harness, experiments, Gate B0, and defensible packaging | Approximately 220-320 hours, or 11-16 weeks at 20 hours/week |
| Conditional CT4 | Transparent selector only if Gate B0 passes and action preference changes | Additional 40-70 hours |
| Distributed/production work | Multi-node, RDMA, HA, multi-tenancy, orchestration | Excluded from this recruiting mainline |

These are planning ranges, not achievement claims. Gate A determines whether the
lower end is credible; an unstable integration seam, asynchronous race, or noisy
GPU experiment can move the work toward the upper end.
