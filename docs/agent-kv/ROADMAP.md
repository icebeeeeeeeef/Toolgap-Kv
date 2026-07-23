# Evidence Roadmap

> Status: `roadmap`
>
> Last reviewed: 2026-07-14
>
> Time and hardware lens: about 20 hours/week, one 24 GB consumer GPU, one
> current-vLLM line, no production traffic or required multi-node environment.

## 1. Roadmap Contract

The roadmap optimizes interview evidence rather than feature completeness.

1. CT1 integration, CT2 correctness/recovery, and CT3 measured boundary are the
   unconditional mainline.
2. CT1-CT3 completion requires a candidate-owned, in-process logical lifecycle
   controller; a trace-only observer, proxy, or benchmark harness cannot pass.
3. vLLM continues to own physical shared blocks/refcounts, eviction,
   PagedAttention, model execution, and native D2H/H2D transfer.
4. Dynamic policy is conditional CT4 and cannot start before Gate B.
5. Each phase closes decision cards through real traces, tests, or measurements.
6. A negative result may narrow a branch while strengthening the work sample.
7. Multi-engine, multi-node, RDMA, remote-tier, router, and kernel work are excluded.
8. No milestone changes claim state without exact artifact paths and commands.

## 2. Gate A: Two-Week Falsification Sprint

Gate A answers whether the current project has a maintainable real-vLLM evidence
path. It does not evaluate policy quality.

### Week 1: Source Capability Matrix

Pin a release candidate only after auditing these contracts:

```text
request completion and prefix-reference release
tool-wait and tool-result/resume event entry into the runtime
forced nominal action injection for conformance tests
session/turn/epoch correlation when resume uses a new request
actual cache object and reference ownership
proactive versus eviction-triggered CPU store
store/load completion visibility
GPU invalidation while a CPU copy remains
GPU plus CPU invalidation for forced recompute
GPU hit, CPU hit, matched tokens, and recomputed-token observability
session, turn, lifecycle claim, and epoch mapping
fallback and cancellation visibility
ordinary-request default-path isolation
```

Required artifact:

```text
docs or experiment-local capability matrix
candidate tag and exact commit
source paths and relevant tests
supported seam versus missing-contract conclusion
expected patch/plugin boundary
candidate-owned controller transition and default-path bypass boundary
source-audited fault seam, allowed fallback, and separate fixture shape
```

Do not rent GPU time merely to discover a source-level semantic mismatch.

### Gate A0: Applicability Gates Before the Controller Vertical Slice

After Week 1 resolves the source seam and before candidate-owned controller code,
run two hard gates on the pinned engine:

1. **Token-round-trip gate:** compare R0's actual processed token sequence with
   R1's rendered history only through the token before the first tool result.
   The common prefix must cover the canonical assistant tool-call representation
   through its last reusable full block. A generic early mismatch is a
   canonical-serialization/token-compatibility result, not a ToolGap-KV cache
   miss; stop or reselect this runtime mainline.
2. **Stock-sufficiency gate:** compare stock APC (S0) and stock APC plus native
   CPU offload (S1) across a preregistered prefix length, tool gap, and HBM
   pressure matrix. If those stock paths cover every declared regime, stop or
   narrow the performance-runtime claim before implementing the controller.

Before the first S0/S1 comparative run, the experiment manifest must freeze:
`M = active_unique_KV / usable_HBM`, low/target/overload M bands, L and G
points, background arrival process, repetitions, primary metrics, and all
continue/stop interpretations. A calibration that only determines model KV size
or capacity may precede this freeze; no result-driven region selection may.

`--swap-space` removal in V1 refers to the old scheduler/preemption swap path.
It is distinct from the KVConnector/OffloadingConnector CPU store/load path used
by S1; never use “swap” as shorthand for the latter.

### 2026-07-22 Gate A0.1 Execution Record

The token-round-trip sub-gate was executed before any controller work on an
NVIDIA A10 with vLLM `0.25.1` commit
`752a3a504485790a2e8491cacbb35c137339ad34` and Qwen2.5-7B-Instruct revision
`a09a35458c702b33eeacc393d103063234e8bc28`. Its final artifact is
`a01-20260721T190035Z-span-v2`.

The five isolated R0 preflights were exact-token stable and the assistant
tool-call semantic span was equal in R0/R1. However, the observed block size was
16 and `reusable_full_block_ceiling=192 < a_end=198`. The registered verdict is
`serialization_stop`; the full command, raw-bundle hashes, harness history, and
scope limits are in
[A0.1 results](../../experiments/0001-mechanism-feasibility/A0.1-results-2026-07-22.md).

This originally blocked A0.2 under D026. The result remains a narrowly measured
canonical full-block applicability result, not an APC/offload/performance result,
and the fixture was not padded. D027 later superseded that branch decision after
A0.1R directly observed stock APC materializing the eligible 192-token prefix.
The historical A0.1 verdict and raw evidence remain unchanged.

### 2026-07-23 Gate A0.2 Execution Record

After the separately reviewed A0.1R and foreground-length qualification gates,
A0.2 executed the frozen stock APC (S0) versus stock APC plus native CPU offload
(S1) matrix on the pinned NVIDIA A10/vLLM/Qwen testbed.

Attempt 1 is preserved as provenance-invalid because engine-auto-selected GPU KV
capacity drifted from 3151 to 3157 blocks across runs. Attempt 2 explicitly froze
3151 blocks in both arms and completed all 90 registered runs as valid
observations.

All six target/overload cells produced S0 missing-prefix observations. Three were
registered material full-recompute cells and three were partial-miss cells. S1
provided attributable external cached tokens for every material miss; no
material-cell foreground-direction reversal occurred. The pinned connector did
not expose request-scoped load start/end intervals, so the preregistered
transfer-overlap-dependent conditions remained disabled.

No registered Stop or Continue condition fired. The final A0.2 decision is the
experimentally validated `inconclusive` D028 record, not a pass into A1. Week 2
controller/runtime work therefore remains blocked pending a separate
stop/narrow/reselect review or a newly preregistered, independently approved
question. The complete cell table and evidence boundary are in
[A0.2 results](../../experiments/A0.2-stock-sufficiency/A0.2-stock-sufficiency-results-2026-07-23.md).

### Week 2: Pinned Three-Path Trace

Use the schema-v0 nominal contract in
[Experiment 0001](../../experiments/0001-mechanism-feasibility/README.md) to
force and attribute, when supported, through a minimal candidate-owned controller
vertical slice:

1. `retain -> gpu_hit`;
2. `offload -> cpu_restore`;
3. `recompute -> recompute`.

At minimum, CPU restore and full recompute must be distinguished. Retain may be
removed from the immediate implementation if the source audit proves that it
requires a broad or unstable fork.

Schema v0 remains strict nominal conformance. Week 1 must add a separate
source-audited fault/fallback fixture before the Week 2 run; do not weaken the
nominal requested-to-observed pairs to make a fallback pass.

Required evidence pack:

```text
environment manifest and exact launch command
pinned vLLM commit and local patch hash
requested -> observed -> fallback trace
GPU/CPU hit and token/block accounting evidence
queue/store/restore/prefill/first-token timing provenance
output equivalence or declared correctness oracle
one source-audited fault/fallback fixture
optionally one separate performance/applicability negative case
one rejected integration alternative
first closed decision card
```

### Gate A Pass Conditions

Continue only when all are true:

- Gate A0 token compatibility and stock-sufficiency outcomes are recorded; the
  declared workload leaves a candidate-addressable gap;
- at least two real paths are forced and independently attributable;
- the relevant integration fits a supported seam or small auditable patch;
- candidate-owned in-process code owns at least one real lifecycle transition or
  fallback and ordinary requests demonstrably bypass it;
- removing/bypassing that controller removes the behavior rather than only its logs;
- requested/observed disagreement is rejected or explained by an allowed fallback;
- the exercised fault cannot silently reuse materialization and ends in explicit
  recompute or failure;
- another engineer can reproduce the trace from repository commands;
- the first decision card is closed by real evidence.

### Gate A Outcomes

| Evidence | Decision |
|---|---|
| Three paths are maintainable and observable | Continue full CT1-CT3 mainline |
| Retain is unavailable but offload/recompute are sound | Narrow to offload/recompute conformance and boundary measurement |
| One precise current-vLLM contract is missing | Publish diagnosis and implement only the minimal auditable patch |
| Paths are observable but no non-duplicative lifecycle semantic can be candidate-owned | Preserve the benchmark/diagnosis artifact, stop it as the main recruiting runtime, and rerun project selection |
| No maintainable in-process seam or attributable real path exists | Stop ToolGap-KV and rerun project selection from first principles |

Gate A failure never automatically starts NIXL fencing. That direction requires
its own unmodified-vLLM failing test proving a safety-relevant handoff gap.

## 3. Post-Gate-A Contract and Correctness Evidence

Implement the smallest candidate-owned logical lifecycle runtime revealed by
Gate A. It is mandatory even when the branch narrows to offload/recompute. Reuse
the vLLM physical data plane and do not build a policy platform.

### CT1 Integration

- freeze the candidate-owned versus vLLM-owned boundary;
- implement the lifecycle controller and vLLM adapter for lifecycle claims,
  epochs, legal transitions, forced/static actions, and event delivery;
- implement retain/offload/recompute executor adapters only for supported paths;
- keep ordinary requests on the default path;
- record actual block/transfer outcomes in DecisionTrace;
- prove with a removal/bypass test which runtime behavior is candidate-owned;
- close the extension-seam decision card.

### CT2 Correctness and Recovery

- define requested action, observed action, and allowed fallback reasons;
- define compatibility and lifecycle epoch using source-audited objects;
- distinguish lifecycle claims from physical shared-block ownership;
- implement idempotence and stale asynchronous-completion fencing;
- implement cancellation, terminal cleanup, and safe fallback orchestration;
- implement one high-value deterministic fault, initially restore failure to
  safe recompute unless Gate A identifies a better failure;
- assert output equivalence, stale-completion rejection, and capacity cleanup;
- close the attribution/fallback, lifecycle-identity, and recovery/cleanup cards
  with distinct decision questions even if one fault harness supplies evidence
  to more than one card.

Exit when CT1 is evidence-backed, controller removal/bypass proves the owned
behavior, state-transition and race tests pass, and at least one CT2 failure path
has a reproducible trace plus regression test.

## 4. Minimum Boundary Evidence

Measure the smallest experiment that can support a quantitative trade-off. Avoid
a four-dimensional exhaustive sweep.

### Required Axes

Start with:

```text
context or KV size
x transfer/recompute cost ratio
x one pressure condition: active decode or HBM pressure
```

Use the same real engine path for isolated calibration and end-to-end runs.
Separate queue wait, store, restore, prefill, first token, active-request p95/p99,
bytes moved, and repeated tokens.

### Required Comparators

- forced recompute;
- native/forced CPU offload when supported;
- retain or the strongest honest retention approximation when supported;
- one tuned static TTL/eviction baseline only when its semantics can be implemented
  fairly on the pinned runtime.

### Required Outputs

- one measured break-even or dominance boundary;
- one workload where the chosen action loses;
- one active-request/backpressure guardrail result;
- raw runs, variance policy, environment manifest, and exact commands;
- closed boundary card; close the fifth unconditional CT1-CT3 card through the
  CT2 recovery card rather than depending on a queue or TTL seam;
- optional backpressure or negative-region card when its source-audited seam exists;
- updated organic-hook map.

Exit when CT3 is evidence-backed. A result that one action dominates is a valid
completion and a reason not to build CT4.

## 5. Gate B0 Admission Audit and Gate B

After CT3, run a Gate B0 admission audit before implementing any selector. Use
the strongest fair static comparator supported by the pinned runtime:

- tuned static TTL/retention when its semantics and executor parity are real;
- otherwise a tuned action-only/static substitute over the same executors;
- if neither is expressible fairly, close a missing-contract/negative-conformance
  card and retire CT4.

Gate B0 is baseline work at the CT3 boundary, not dynamic-policy implementation
and not proof that Gate B has opened.

### Gate B: Is Dynamic Selection Justified?

CT4 opens only when all conditions hold:

1. CT1-CT3 are evidence-backed on the declared testbed.
2. At least two reachable, reproducible regimes prefer different actions.
3. Requested and observed behavior can be attributed without hidden executor
   differences.
4. Gate B0 produced a tuned fair static/action-only baseline and separate
   tuning/test split.
5. Measurement noise is smaller than the decision margin.
6. The selector can be implemented with bounded hot-path and tail overhead.

If any condition fails, retire CT4 and package the integration/correctness/boundary
work honestly.

### Conditional CT4 Work

When Gate B passes, implement one transparent deterministic selector using the
same executors as the baselines. Measure decision overhead, action error,
sensitivity, one ablation, and one losing condition. Prediction training,
workflow DAG scheduling, and a workflow-wide policy platform remain excluded
unless a later independent project review approves them.

## 6. Effort Budget

At about 20 hours/week, use these planning ranges:

| Work package | Active engineering effort |
|---|---:|
| Gate A source audit and controller vertical slice | 30-45 hours |
| Lifecycle runtime, vLLM adapters, and executor orchestration | 70-110 hours |
| Correctness, race, fault-injection, and cleanup tests | Included above; protect at least 40 hours of the package |
| Workload/replay, profiler, benchmark runner, and CT3 runs | 70-105 hours |
| Gate B0, evidence cards, reproducibility, and interview packaging | 30-60 hours |
| **Core CT1-CT3 and Gate B0** | **Approximately 220-320 hours / 11-16 weeks** |
| Conditional CT4 after Gate B | Additional 40-70 hours / 2-4 weeks |

The historical eight-week outline is a happy-path floor, not a defensible
completion promise once controller ownership, race coverage, repeated GPU runs,
and evidence packaging are included.

## 7. Supporting Workload Harness

The former Agent KV Regime Lab direction is not a separate project. Its allowed
role is a deterministic workload/replay harness for this roadmap:

- real tool/turn structures may be sampled from public trajectories;
- injected gap, cancellation, arrival, and pressure models are labeled
  `trace-derived synthetic`;
- at least one real-vLLM trace must calibrate the harness;
- public trajectories do not prove wall-clock tool latency, scheduler timing,
  GPU KV state, or production representativeness.

## 8. Explicitly Excluded Investment

Do not start these as parallel or automatic fallback projects:

```text
NIXL fencing without an independent failing safety test
KV State Ledger and reconciliation platform
deadline-aware transfer controller
agentic serving hint gateway
new LMCache/Mooncake-style storage layer
multi-node P/D or RDMA deployment
second serving engine
CUDA/kernel/operator optimization
```

Prior art, dependencies, and study topics may still appear as baselines or
interview context without becoming implementation scope.

## 9. Evidence and Claim-State Gates

| Milestone | Required evidence | Allowed claim state |
|---|---|---|
| Design only | Reviewed documents | `roadmap` |
| Phase 0 scaffolding | Exercised local contracts and repository checks | `shipped` for scaffolding only |
| Gate A plumbing | Pinned build, tests, and one real runtime trace | `shipped` for integration; no performance claim |
| Real experiment | Raw runs, manifest, repetitions, and attribution | `experimentally validated` only for that environment/workload |
| Replay/optimizer only | Trace, model, or solver artifacts | `simulated` with calibration limits |
| Resume statement | Claim-to-artifact/card mapping | Only verified nouns, verbs, scale, and results |

At every gate record new evidence, invalidated assumptions, claim promotions or
demotions, closed cards, organic hooks, weakest hiring-signal dimension, and the
next smallest experiment in [DECISIONS.md](DECISIONS.md) and
[INTERVIEW_MAP.md](INTERVIEW_MAP.md).
