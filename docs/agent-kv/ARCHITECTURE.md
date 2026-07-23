# Architecture

> Status: `roadmap` proposal
>
> No component in this document is a current-vLLM implementation unless an exact
> artifact is linked. Engine-independent Phase 0 contracts are the only shipped
> code at the time of this review.

> **Pinned upstream model.** A0.2 pins vLLM commit
> `752a3a504485790a2e8491cacbb35c137339ad34`. Its native CPU-offload API is
> already job-scoped: `OffloadingConnectorMetadata` carries
> `store_jobs`/`load_jobs` keyed by scheduler-assigned `job_id`; each
> `TransferJob` carries its originating `req_id`; workers report
> `completed_jobs`; and the scheduler reduces those reports into one
> `TransferJobStatus` completion. This document must not model native transfer
> completion as a `reqs_to_store`/`reqs_to_load` request callback.

## 1. Design Principle

Separate action selection from mechanism without moving correctness outside the
runtime:

- Gate A uses forced actions; later phases may use static selectors.
- A dynamic policy estimates costs and chooses an action only after Gate B.
- The runtime state machine owns transitions, concurrency, and fallback.
- Executors adapt supported vLLM retain, native offload/restore, or recompute
  paths; dependency transfer code is not candidate-owned.
- DecisionTrace records the causal chain for evaluation.

Use official vLLM extension points where they preserve required semantics. Modify
engine core only when an explicit missing contract is demonstrated.

### Ownership Matrix

| Responsibility | Owner | Mainline status |
|---|---|---|
| Lifecycle claim/epoch, legal transitions, idempotence, stale-completion fencing | Candidate lifecycle runtime | Required CT1-CT2 |
| Forced/static action orchestration, fallback, cancellation, cleanup, DecisionTrace | Candidate lifecycle runtime | Required CT1-CT2 |
| Hook/event translation and executor adapters | Candidate integration, over audited vLLM contracts | Required CT1-CT2 |
| Shared block residency/refcounts, eviction, PagedAttention, model execution | vLLM physical data plane | Reused dependency |
| Native D2H/H2D store/restore and tier capacity semantics | vLLM physical data plane | Reused dependency |
| Cost profiling and boundary benchmark | Candidate harness | Required CT3 |
| Dynamic selector | Candidate policy | Conditional CT4 after Gate B |

A tracing-only hook does not own the lifecycle contract. Gate A must prove that
candidate code changes at least one real transition, fallback, or cleanup outcome
and that ordinary requests retain the default vLLM path.

## 2. System Overview

```mermaid
flowchart TB
    A["Agent workload / OpenAI-compatible client"] --> B["Logical tool turn"]
    B --> C["Candidate lifecycle claim: session / turn / epoch"]
    C --> D["New vLLM request (req_id)"]
    D --> E["Offloading scheduler: TransferJob(job_id, req_id)"]
    E --> F["Worker completed_jobs[job_id]"]
    F --> G["Scheduler TransferJobStatus completion"]
    G --> H["Lifecycle outcome adapter"]
    H --> I["LifecycleStateMachine"]
    I --> J["CostProfiler (CT3)"]
    I --> K["Action selector: forced / static / Gate-B dynamic"]
    K --> L["Retain executor"]
    K --> M["Offload / restore executor"]
    K --> N["Evict / recompute executor"]
    L --> O["GPU HBM"]
    M --> O
    M --> P["CPU DRAM"]
    N --> O
    I --> Q["DecisionTrace"]
    J --> Q
    K --> Q
    Q --> R["Replay and evaluation harness"]
```

## 3. Main Components

### LifecycleStateMachine

Owns logical lifecycle claims, epochs, legal transitions, idempotence,
asynchronous-completion fencing, fallback, cancellation, cleanup, and completion
semantics.

Proposed interface:

```text
on_tool_wait(event) -> Decision
submit_resume(event) -> (lifecycle_epoch, req_id)
on_cancel(event) -> CleanupPlan
on_transfer_job_complete(job_id, status) -> StateTransition
on_transfer_job_failure(job_id, reason) -> FallbackPlan
```

It does not estimate policy costs or directly move tensors. The exact object
carrying candidate state is a lifecycle claim over compatible prefix references,
not a long-lived vLLM `Request`. One logical claim may submit more than one
vLLM request and one request may have multiple store jobs. A native `job_id` is
therefore an asynchronous-completion correlation key, not the lifecycle identity.

### Identity and Completion Boundary

| Identity / event | Owner | Meaning | Candidate use |
|---|---|---|---|
| `session_id`, `turn_id`, `epoch` | ToolGap-KV | Logical agent lifecycle identity | Authority for idempotence, cancellation, and stale-completion fencing |
| `req_id` | vLLM request | One concrete submission, including a newly submitted resume | Map a submitted resume back to its current lifecycle epoch |
| `job_id` | Offloading scheduler | One native async store or load | Correlate one native completion with the mapped request; never use it as a session key |
| `completed_jobs[job_id]` | vLLM workers | Per-worker completion report | Treat as partial evidence only; it is not a completed lifecycle transition |
| `TransferJobStatus` at pending count zero | Offloading scheduler | Exactly one reduced native transfer completion | The only job-completion point an adapter may turn into an observed store/load outcome |

The candidate adapter must record `(lifecycle_epoch, req_id, job_id, direction)`
when an observed job is emitted. It may transition the lifecycle state only after
the scheduler has reduced `completed_jobs` for that job to completion. A late
job completion whose `(req_id, epoch)` mapping is no longer current is traceable
but cannot reactivate, complete, or clean up a newer lifecycle claim.

### CostProfiler

Builds measured curves for:

```text
prefill latency by prompt tokens, batch, model, and load
D2H store latency by KV bytes and contention
H2D restore latency by KV bytes and contention
decision overhead
HBM pressure and admission effects
```

Profiles are versioned by model, KV dtype, parallel configuration, engine commit,
hardware topology, and runtime configuration.

### Action Selector and Conditional LifecyclePolicy

Gate A consumes an explicit forced action. Static baselines later consume declared
configuration. A dynamic `LifecyclePolicy` is proposed only after Gate B and would
consume an immutable decision snapshot plus return one action and explanation.

```text
DecisionInput:
  request_id
  lifecycle_epoch
  model_fingerprint
  prefix_tokens
  kv_bytes
  estimated_gap
  estimated_resume_probability
  gpu_cache_pressure
  queue_depth
  transfer_pressure
  latency_slo

Decision:
  action: retain | offload | recompute
  estimated_costs
  selected_reason
  policy_version
```

If Gate B passes, the first dynamic policy is analytic and deterministic. Learned
prediction is not a dependency or current roadmap commitment.

### Executors

`RetainExecutor` is included only when the pinned runtime exposes maintainable
retention semantics. It adapts supported priority/TTL behavior rather than
claiming ownership of the engine's cache manager.

`OffloadExecutor` orchestrates vLLM's native asynchronous D2H/H2D mechanism and
reports completion or failure back to the project contract. The underlying
transfer/tiering implementation remains vLLM-owned.

`RecomputeExecutor` releases reusable state and prepares resume through normal
prefill. It must distinguish intentional recompute from accidental cache miss.

### DecisionTrace

The proposed integration must produce a structured trace record for every
lifecycle event:

```text
request_id
session_id
lifecycle_epoch
event_time
event_type
state_before / state_after
model and runtime fingerprint
decision inputs
estimated retain/offload/recompute costs
selected action and reason
actual store/restore/recompute timing
matched prefix tokens
fallback cause
SLO outcome
```

DecisionTrace is part of the runtime contract, not optional logging. It makes
policy effects attributable and enables deterministic replay.

## 4. Lifecycle State Machine

```mermaid
stateDiagram-v2
    [*] --> ACTIVE
    ACTIVE --> TOOL_WAIT: tool call emitted
    TOOL_WAIT --> RETAINED: retain selected
    TOOL_WAIT --> OFFLOAD_PENDING: offload selected
    TOOL_WAIT --> EVICTED: recompute selected
    OFFLOAD_PENDING --> OFFLOADED: store job completes
    OFFLOAD_PENDING --> EVICTED: store job fails / fallback
    RETAINED --> ACTIVE: resume with resident KV
    OFFLOADED --> RESTORE_PENDING: tool result received
    RESTORE_PENDING --> ACTIVE: load job completes
    RESTORE_PENDING --> RECOMPUTE_PENDING: load job fails
    EVICTED --> RECOMPUTE_PENDING: tool result received
    RECOMPUTE_PENDING --> ACTIVE: prefill complete
    TOOL_WAIT --> CANCELLED: cancel / timeout
    RETAINED --> CANCELLED: cancel / timeout
    OFFLOADED --> CANCELLED: cancel / timeout
    RESTORE_PENDING --> CANCELLED: cancel
    ACTIVE --> [*]: completion
    CANCELLED --> [*]
```

## 5. State and Correctness Invariants

1. A request has one monotonically increasing lifecycle epoch.
2. A resume event may activate only the current epoch.
3. One lifecycle claim/epoch has at most one terminal requested outcome. This
   does not grant a session ownership of physical blocks: shared/content-addressed
   blocks retain engine-defined reference, residency, and eviction ownership.
4. Restored KV is accepted only when model, tokenizer/template, KV dtype,
   attention layout, parallel configuration, and token hash are compatible.
5. A transfer failure cannot silently produce partial reuse; it falls back to
   recompute or fails the request explicitly.
6. Cancellation is idempotent and prevents a stale native `job_id` completion
   from resurrecting the lifecycle claim or a later resume `req_id`.
7. Ordinary non-agent requests remain on the default fast path.

## 6. Cache Identity

The compatibility fingerprint is a proposed safety boundary. Gate A must map it
to fields current vLLM actually exposes before implementation. Candidate fields
include:

```text
model identity and revision
tokenizer identity and revision
chat-template version
exact prefix token hashes
KV dtype and layout
attention backend assumptions
tensor/pipeline/context parallel configuration
engine and connector compatibility version
```

This fingerprint is a correctness boundary, not merely a cache-key optimization.

## 7. Scheduling and Resource Semantics

Retain consumes HBM over time. Offload consumes destination capacity and transfer
bandwidth. Recompute consumes future GPU compute and may delay unrelated decode
requests. CT3 measurement, and any later selector, must therefore include resource
pressure rather than compare isolated request latency only.

MVP resource scope:

```text
one vLLM process
one 24 GB GPU
tensor parallel size 1
GPU HBM
node-local CPU DRAM
fixed preemption configuration
```

NVMe, remote stores, multi-replica routing, and cross-engine sharing are separate
extensions because each adds independent correctness and performance questions.

## 8. Failure Handling

| Failure | Required behavior |
|---|---|
| D2H store failure | Mark offload unavailable; release or retain according to safe fallback |
| H2D restore failure | Recompute if compatible prompt tokens remain available |
| Resume during store | Serialize by epoch; either complete store then restore or cancel store safely |
| Cancel during restore | Suppress stale completion and release temporary capacity |
| Duplicate resume | Process once; record duplicate as a trace event |
| CPU tier full | Apply configured admission/eviction policy; never overwrite live data |
| Backend restart | Invalidate local metadata and reconcile before reuse |
| Stale cache identity | Reject reuse and recompute |

## 9. vLLM Integration Boundary

### Pinned Job-Scoped Offload Contract

The A0.2 pin is a release-line commit rather than a descendant of the `main`
merge commit for upstream #39186, so merge date alone is not a valid topology
test. The exact pinned source nevertheless contains the #39186 job-scoped
contract: `TransferJob`, `store_jobs`/`load_jobs`, `completed_jobs`, and
`TransferJobStatus`. The architecture is therefore intentionally aligned to
the pinned API, not to the old request-scoped model.

This distinction changes the ownership boundary:

```text
ToolGap-KV owns: logical tool lifecycle, epoch, request-to-claim mapping,
                  job-to-current-epoch correlation, fallback and trace.
vLLM owns:      job allocation, per-worker completion reduction, block fences,
                  complete_store/load, refcounts, and D2H/H2D execution.
```

`request_finished()` is only a request-lifetime event. It cannot be treated as
proof that every store is complete: a store job can outlive its request and is
made safe by vLLM's job/block fencing. Conversely, the candidate runtime must
not call `complete_store`, `complete_load`, or mutate vLLM job state.

### Patch 1 Candidate: Job-Scoped Load-Failure Recovery

D029 is an accepted **audit/admission gate**, not approval to implement a vLLM
patch. The pin has per-job success completion already, but it has no generic
job-failure contract:

- synchronous `submit_load()` and `submit_store()` failures assert;
- asynchronous transfer results assert `transfer_result.success` with the
  explicit comment that job failures are not supported;
- `completed_jobs` carries only successful per-worker counts;
- the generic vLLM scheduler already accepts `invalid_block_ids` and can apply
  `kv_load_failure_policy="recompute"`, but this Offloading Connector cannot
  turn a failed job into those block IDs.

Therefore a candidate Patch 1 exists only if the D029 fake-worker admission
tests prove the missing bridge cannot be supplied by an official extension. Its
minimal responsibility is **load-path failure recovery**, not completion
observability:

1. report a typed terminal job outcome across workers, rather than reinterpret
   `completed_jobs` as a failure counter;
2. retain enough scheduler-side load destination information to emit precise
   `invalid_block_ids` for a failed load job;
3. route the failed request into vLLM's existing recompute/fail policy without
   crashing the engine;
4. terminally discard a failed store and remove its `_jobs`, `transfer_jobs`,
   and `_block_id_to_pending_jobs` bookkeeping, without calling
   `complete_store`.

The patch must preserve vLLM's own completion reduction, job removal, refcounts,
and physical block-reuse fence. It must **not** recreate `reqs_to_store`, publish
a worker-local result before cross-worker reduction, use `request_finished()` as
a store-complete surrogate, or put ToolGap session/epoch semantics into vLLM.
ToolGap may consume a separate read-only scheduler-reduced outcome event, but a
late outcome may affect only its own logical lifecycle trace, never vLLM's job
state. If this scope cannot remain small and auditable, D024 requires stopping
or reselecting the runtime branch rather than widening into a scheduler fork.

As of the 2026-07-13 review, vLLM upstream has native CPU offload, a merged/released
multi-tier framework, and experimental per-request selective offload. Those are
dependencies, not candidate contributions. A prior context-aware token
priority/duration proposal closed without merging, but this does not prove that
the pinned target has no usable retention behavior. Gate A must pin a concrete
tag and commit and verify:

```text
whether request lifecycle hooks expose tool-wait and resume semantics
whether per-request offload requests and actual outcomes are expressible
whether retention can use a supported priority/TTL API
whether DecisionTrace can observe actual block outcomes
whether fallback can be implemented without broad scheduler changes
which object owns block references, shared residency, and asynchronous completion
```

If retention requires a large fork, the project must either narrow to
offload/recompute or isolate a minimal retention API contribution.

## 10. Planned Candidate Code Surface

Exact vLLM anchors wait for Gate A, but full CT1-CT3 completion must leave an
inspectable code surface equivalent to:

```text
src/toolgap_kv/contracts/       lifecycle identity, events, actions, trace schema
src/toolgap_kv/runtime/         state machine, controller, invariants, cleanup
src/toolgap_kv/integrations/    pinned-vLLM hooks, event translation, outcome adapter
src/toolgap_kv/executors/       retain/offload/recompute orchestration adapters
src/toolgap_kv/observability/   DecisionTrace sink, counters, timing attribution
src/toolgap_kv/workloads/       deterministic tool-gap compiler and replay driver
src/toolgap_kv/benchmarks/      profiler, experiment runner, result validation
tests/unit/                     transitions, epochs, idempotence, fallback
tests/integration/              real vLLM paths, default-path bypass, output checks
tests/fault/                    failure, cancel, duplicate/late completion, cleanup
patches/                        only a proven missing vLLM contract, pinned by commit
experiments/                    manifests, immutable raw traces, summaries, commands
```

The final file names may differ, but none of the first seven responsibilities can
be replaced by a diagram. Candidate code is expected to be several thousand lines
across runtime, adapters, tests, and harnesses; LOC is not an acceptance metric.
The auditable vLLM core patch should remain small or Gate A must reconsider the
seam.

## 11. Future Architecture, Not Mainline

A research extension may add a `StorageTier` abstraction for DRAM, NVMe, or
remote KV systems and a cache-aware router for multiple replicas. A production
extension may add multi-tenant quotas, admission control, HA metadata, and
orchestration. These extensions must not be used to claim completion of the
single-node lifecycle mechanism.
