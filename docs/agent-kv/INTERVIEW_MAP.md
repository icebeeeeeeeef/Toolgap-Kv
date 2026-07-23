# Evidence-Backed Interview Map

> Project claim state: `roadmap`
>
> Last reviewed: 2026-07-23
>
> No lifecycle-runtime tree in this file is `evidence-backed`. DC0 preserves the
> original negative A0.1 applicability result, whose branch decision was later
> superseded by D027. DC0.2 closes the stock-sufficiency question as a valid
> `inconclusive` experiment under D028. Neither card supports a completed runtime
> or performance claim.

## 1. Purpose

This document maps a future resume or interview claim into the follow-up branches
an inference-platform interviewer can reasonably explore. It is not a script to
memorize and does not duplicate the question bank in
[interview-grill/README.md](interview-grill/README.md).

The governing path is:

```text
claim
-> why this problem matters
-> why this integration point
-> alternatives and rejected designs
-> invariant and authority
-> failure, ordering, and cancellation
-> measurement and operational boundary
-> changed scenario or adjacent runtime topic
```

Every branch must end at an owned artifact, an explicitly unvalidated hypothesis,
or an honest scope boundary.

## 2. Tree Contract

Each maintained claim tree contains:

```text
tree ID and state
candidate claim
owned runtime contract
root interviewer challenge
follow-up branches
minimum evidence gate
dangerous answer patterns
organic extension hooks
```

Tree states reuse the question states in
[interview-grill/README.md](interview-grill/README.md): `unanswered`, `draft`,
`evidence-backed`, `invalidated`, and `retired`.

## 3. Decision Card Registry

A card is `closed` only when it has alternatives, a preregistered falsifiable
expectation, real measurement or deterministic fault evidence, a decision, a
losing/applicability boundary, exact artifact links, and one reproduction command.
Source reading alone may reject an architecture but cannot satisfy a card's
measurement requirement unless the decision is specifically a conformance contract
and is exercised by a real trace or test.

DC0 and DC0.2 below are closed evidence cards. All controller, correctness, and
performance cards remain `roadmap` and must not borrow their evidence.

### DC0: Canonical Tool-Call Full-Block Applicability

State: `evidence-backed` (negative, historical branch decision superseded);
closed; does not support CT1.

```text
Decision:
  start the A0.2 stock-sufficiency matrix on this pin/fixture, or stop before
  controller implementation because the prerequisite full block does not exist.
Alternatives:
  proceed to A0.2 after exact semantic round-trip; stop when the registered
  full-block ceiling fails; change fixture/padding to seek alignment.
Preregistered falsifiable expectation:
  R0/R1 must have an exact assistant tool-call semantic span and
  reusable_full_block_ceiling >= a_end. Any earlier semantic mismatch or
  insufficient ceiling is serialization_stop, not a cache miss.
Measurement and attribution:
  five isolated, single-request R0 preflights read RequestOutput token IDs;
  a clean fifth engine then renders R1. A v2 message-scoped span adapter maps
  the marker only inside a template-prefix-derived assistant region. vLLM block
  size is observed from the engine, not chosen by the harness.
Artifacts:
  scripts/run_a01.py;
  experiments/0001-mechanism-feasibility/A0.1-token-roundtrip-spec.md;
  experiments/0001-mechanism-feasibility/A0.1-results-2026-07-22.md;
  local ignored raw/a0.1/a01-20260721T190035Z-span-v2/ bundle whose SHA-256
  inventory is tracked in that report.
Reproduction:
  export CUDA_HOME=/usr/local/cuda-12.8; export PATH="$CUDA_HOME/bin:$PATH";
  HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 python scripts/run_a01.py
  --model-revision a09a35458c702b33eeacc393d103063234e8bc28
  --tokenizer-revision a09a35458c702b33eeacc393d103063234e8bc28
  --chunked-prefill disabled --run-id <new-run-id>
Observed real evidence:
  on A10 / vLLM 0.25.1 commit 752a3a504485790a2e8491cacbb35c137339ad34,
  semantic_span_equal=true at [178,198), LCP=199, block_size=16, and
  reusable_full_block_ceiling=192. The semantic end is not covered (slack=-6).
Decision:
  the preregistered A0.1 verdict was serialization_stop and D026 originally
  blocked A0.2. D027 later superseded that branch decision only after A0.1R
  independently observed stock APC admitting the eligible 192-token prefix.
  The A0.1 raw verdict itself remains unchanged.
Losing/applicability boundary:
  semantic equality alone is insufficient when APC full-block geometry ends
  before the assistant semantic span. This does not claim an APC miss, CPU
  restore behavior, performance delta, or behavior for other models/templates.
Organic hooks:
  prompt canonicalization, template/parser boundaries, prefix-cache block
  granularity, evidence-gated stop conditions, and why a negative result can
  prevent an invalid systems implementation.
```

### DC0.2: Stock APC / Native-Offload Sufficiency

State: `evidence-backed` (`inconclusive`); closed; does not support CT1.

```text
Decision:
  whether the preregistered stock APC (S0) versus stock APC plus native CPU
  offload (S1) matrix leaves a candidate-addressable gap that authorizes A1.
Alternatives:
  Stop/narrow because one stock static path covers the declared cells;
  Continue to A1 because a registered unrestored miss, directional trade-off,
  or foreground-direction reversal exists; retain valid evidence as
  inconclusive when neither branch is satisfied.
Preregistered falsifiable expectation:
  exactly 3 lengths × 3 M bands × 5 pairs × 2 policies; materiality requires an
  S0 full-recompute miss with Δservice > θ and token-accounting agreement;
  request-scoped transfer overlap is mandatory for the directional-trade-off
  branch; no selective extra runs or post-hoc material redefinition.
Measurement and attribution:
  HND layout in both arms, supported chunked prefill, 3151 explicitly frozen
  GPU KV blocks, 5 GiB S1 CPU tier, per-request local/external cached-token
  accounting, active-probe timing, and independent engine execution per run.
Artifacts:
  experiments/A0.2-stock-sufficiency/
    A0.2-stock-sufficiency-results-2026-07-23.md;
  experiments/A0.2-stock-sufficiency/results/attempt-02/
    a02-matrix-summary.json;
  local ignored raw/matrix/**/ordinal-*-a02/ bundles with all 630 JSON hashes
  recorded in the machine summary.
Reproduction:
  PYTHONPATH=experiments/A0.2-stock-sufficiency:src
  python3 experiments/A0.2-stock-sufficiency/aggregate_results.py --attempt 2
  in a clean results directory or evidence copy.
Observed real evidence:
  90/90 valid observations. Six pressure cells had S0 missing prefixes; three
  were material full-recompute cells. S1 restored all 15 material pairs.
  Material foreground direction was S1-faster in all three cells, so there was
  no reversal. transfer_overlap_observable=false was frozen before execution,
  disabling Stop 3 and Continue 2. No other Stop or Continue condition fired.
Decision:
  D028 closes A0.2 as experimentally validated inconclusive. Do not enter A1,
  implement the lifecycle runtime, redefine partial misses as material, or
  claim ToolGap performance from this evidence.
Losing/applicability boundary:
  capacity-pressure synthetic workload, one Qwen/vLLM/A10/HND testbed, no
  request-scoped transfer interval, no real wall-clock tool-gap load, no
  lifecycle identity/epoch/fallback/cancel behavior.
Organic hooks:
  why valid evidence can remain inconclusive; full versus partial prefix miss;
  APC/offload accounting; HND fairness; transfer observability; preregistration
  discipline; preserving provenance-invalid Attempt 1.
```

### DC1: Smallest Current-vLLM Integration Seam

State: `roadmap`; supports CT1.

```text
Decision:
  supported extension/plugin versus minimal auditable core patch
Alternatives:
  external proxy; native connector/offload hook; scheduler/block-manager patch
Measurement or exercised evidence:
  pinned source capability matrix, patch surface, one end-to-end real trace,
  candidate-controller removal/bypass test, unchanged default-request regression
Artifacts:
  pinned commit, source matrix, patch/plugin, test, DecisionTrace, launch command
Close gate:
  selected seam lets candidate code own a real transition/fallback and observe
  its outcome with a maintainable diff; a trace-only seam cannot close the card;
  rejected alternatives have concrete missing-contract evidence
Organic hooks:
  vLLM scheduler ownership, KVConnector, prefix caching, plugin versus fork
```

### DC2: Requested, Observed, and Fallback Semantics

State: `roadmap`; supports CT1 and CT2.

```text
Decision:
  legal requested -> observed mappings and explicit fallback reasons
Alternatives:
  trust requested action; infer from latency; validate runtime outcomes and accounting
Measurement or exercised evidence:
  forced gpu_hit/cpu_restore/recompute cases plus one fallback/fault case
Artifacts:
  DecisionTrace schema, contract tests, raw runtime events, token/block accounting
Close gate:
  every mismatch is rejected or names an allowed, path-proven fallback;
  output and cleanup checks pass
Organic hooks:
  KV cache correctness, observability, preemption/cache misses, failure recovery
```

### DC3: Lifecycle Identity, Epoch, and Shared Blocks

State: `roadmap`; supports CT2.

```text
Decision:
  which current-vLLM object carries lifecycle authority and stale-completion fencing
Alternatives:
  long-lived request ownership; session/turn identity; lifecycle claim plus epoch
  over engine-owned shared prefix references
Measurement or exercised evidence:
  pinned source/refcount audit, duplicate or stale completion test, capacity cleanup
Artifacts:
  ownership map, invariant tests, fault trace, rejected identity design
Close gate:
  a stale event cannot resurrect state or free/reuse the wrong physical blocks;
  language distinguishes logical claims from engine-owned shared residency
Organic hooks:
  PagedAttention blocks, prefix sharing, cache identity, async cancellation
```

### DC4: Retain, Offload, or Recompute Boundary

State: `roadmap`; supports CT3.

```text
Decision:
  which action is justified in each tested cost/pressure region
Alternatives:
  forced retain; native CPU offload/restore; full recompute
Measurement or exercised evidence:
  same-engine context/KV-size sweep crossed with transfer/recompute ratio and one
  active-decode or HBM-pressure condition
Artifacts:
  manifests, raw timings, cost curves, trace attribution, exact benchmark command
Close gate:
  one reproducible boundary or dominance result plus one losing action;
  queue/store/restore/prefill/first-token time is separated
Organic hooks:
  KV sizing, PagedAttention granularity, chunked-prefill interaction if measured,
  multi-level memory, TTFT
```

### DC5: Transfer Admission, Backpressure, and Tail Impact

State: `roadmap`; supports CT3 only if Gate A exposes a controllable transfer queue.

```text
Decision:
  whether native behavior is sufficient or a bounded admission/concurrency rule is needed
Alternatives:
  native/unbounded behavior; fixed concurrency cap; queue-aware admission or recompute
Measurement or exercised evidence:
  concurrent transfer/load sweep with active decode, queue depth, bandwidth,
  resumed-request and active-request p50/p95/p99
Artifacts:
  queue trace, raw per-run data, configured limits, negative workload
Close gate:
  a selected rule has a measured tail/throughput boundary and rollback condition;
  no performance claim is made if the relevant control is not candidate-owned
Negative-conformance closure:
  a pinned source audit plus real trace proves no controllable queue seam; retain
  native behavior, document the missing contract, and award no backpressure hook
  credit without a candidate-owned measurement
Organic hooks:
  continuous batching, scheduler interference, backpressure, tail latency
```

### DC6: Static TTL/Eviction Sufficiency and Negative Region

State: `roadmap`; supports the post-CT3 Gate B0 admission audit and decides
whether CT4 may open.

```text
Decision:
  tuned static behavior is sufficient versus multiple reachable action regimes exist
Alternatives:
  default eviction/recompute; tuned static TTL/retention; action-only baselines
Measurement or exercised evidence:
  separate tuning/test workloads, regime coverage, negative/cancellation-heavy case
Artifacts:
  tuning ledger, held-out raw runs, baseline parity note, losing-region report
Close gate:
  baseline uses the same executor/failure semantics and the conclusion is stable
  across repetitions; Gate B opens only if at least two regimes disagree
Negative-conformance closure:
  if no fair TTL/retention seam exists, use the strongest action-only/static
  substitute; if no fair substitute exists, record the missing contract and
  retire CT4 rather than weakening baseline parity
Organic hooks:
  prefix eviction, cache pressure, workload shift, baseline fairness
```

### DC7: Restore Failure, Cancellation, and Cleanup

State: `roadmap`; supports CT2 and is unconditional after Gate A selects a real
path.

```text
Decision:
  safe terminal behavior when restore fails, cancellation races a transfer, or
  a completion arrives after the lifecycle epoch changes
Alternatives:
  expose partial state; retry in place; fail explicitly; invalidate and recompute
Measurement or exercised evidence:
  deterministic injected failure plus late/duplicate completion and capacity checks
Artifacts:
  fault injector, regression test, DecisionTrace, cleanup accounting, exact command
Close gate:
  failed materialization never becomes reusable; the request either recomputes
  from authoritative tokens or fails explicitly; capacity returns to baseline
Organic hooks:
  asynchronous state machines, idempotence, cancellation, failure recovery,
  resource reclamation
```

### Organic Hook Map

Hooks count only after their linked card closes and the named code or measurement
exists. The denominator must be refreshed from representative target JDs.

| Serving knowledge band | Candidate card/path | Current credit | Boundary |
|---|---|---|---|
| KV cache computation and lifecycle | DC2-DC4, DC7 | 0 | Core target |
| PagedAttention/page or block size | DC3-DC4 | 0 | Counts only if source objects or measured granularity matter |
| Prefix caching and eviction | DC1, DC3, DC6 | 0 | Core target |
| Scheduling and continuous batching | DC5 | 0 | Counts only with real active-request/queue evidence |
| Multi-level/distributed KV | DC4 | 0 | Local HBM+CPU may count as multi-level; distributed remains excluded |
| Chunked prefill | DC4 | 0 | Conditional on a measured recompute interaction |
| P/D separation | Study boundary only | 0 | NIXL is not part of the mainline |
| MLA/GQA | Project-external study | 0 | Explain KV-size effects; do not add implementation |
| Speculative decoding | Project-external study | 0 | Disabled in Gate A; no hard-attached hook |

The present evidence-backed coverage is `0/9`. The planned mainline can
organically reach at least five bands, but planned coverage receives no score.

## 4. Planned Core Trees

### CT1: Why This Runtime Boundary?

State: `draft`

Candidate claim allowed only after its evidence gate:

> Integrated agent KV lifecycle control into a pinned current-vLLM runtime using
> the smallest extension point that preserves scheduler and transfer correctness.

Root challenge:

> Why did this require your integration instead of an external proxy, an existing
> connector, or a paper's vLLM fork?

Follow-up branches:

```text
What lifecycle event is missing or ambiguous in the stock path?
Which state belongs to the scheduler, block manager, connector, and project code?
When is a store or load result allowed to affect scheduling?
Why is a supported plugin sufficient, or what exact contract forces a core patch?
How is the default non-agent path kept unchanged?
Why not start with LMCache, Mooncake, SGLang, or Continuum's fork?
```

#### Decision branch: external lifecycle controller or native vLLM tool lifecycle?

State: `roadmap`; this is a Gate A seam decision, not a claim that either
implementation already runs.

```text
External-controller route:
  the agent application observes tool-call/tool-result events; ToolGapController
  owns lifecycle claim + epoch + legal transition + fallback, then submits a new
  canonical-conversation request carrying a private envelope. vLLM owns physical
  blocks, refcounts, eviction, scheduling, and D2H/H2D.

Native-vLLM route:
  vLLM would introduce a first-class logical tool-wait/resume contract. It must
  define the interface for pause, resume, cancellation, lifecycle identity,
  visibility of async completion, and the relation between a logical claim and
  shared physical prefix blocks.

First-principles choice:
  start with the external route if its supported seam can cause one real,
  non-duplicative lifecycle transition or fallback and ordinary requests bypass
  it. A larger vLLM diff is not stronger ownership by itself.

Upgrade condition for a narrow core patch:
  an unmodified-vLLM failing test identifies one precise missing physical or
  scheduler contract that is necessary for the tested lifecycle semantic (for
  example, safe per-claim invalidation), and the patch exposes that contract
  without making vLLM own agent orchestration or replacing shared-block
  ownership.

Stop/narrow condition:
  if the required behavior needs a broad scheduler/block-manager fork or a
  first-class agent-orchestration subsystem, narrow to supported
  offload/recompute conformance or reject this vLLM version as the runtime
  mainline. Do not call a trace-only adapter a lifecycle runtime.
```

Interviewer probes for this branch:

```text
Why is submitting a new request after a tool result semantically honest rather
than a fake continuation?
What additional correctness and maintenance obligations would native pause/resume
place on vLLM's request state machine and shared-block allocator?
Which exact failing test would justify a core patch rather than a wrapper?
Why does candidate ownership belong in ToolGapController instead of an application
driver or vLLM scheduler?
What evidence shows the controller changes behavior rather than merely logging it?
```

Minimum evidence gate:

```text
pinned vLLM commit and capability matrix
minimal patch or extension diff
one end-to-end request trace through the candidate lifecycle controller
controller removal/bypass test showing the owned behavior disappears
tests showing both the owned state-transition path and unchanged default path
documented rejected integration alternative
```

Dangerous answer patterns:

```text
listing frameworks instead of naming the missing contract
calling connector-provided transfer code candidate-owned
calling DecisionTrace instrumentation the lifecycle mechanism
equating a larger core diff with stronger ownership
claiming current-vLLM behavior from an old paper fork
```

Organic extension hooks:

```text
KVConnector semantics
prefill/decode disaggregation
block-manager ownership
plugin versus fork maintenance
```

### CT2: What Makes Moved KV Safe to Reuse?

State: `draft`

Candidate claim allowed only after its evidence gate:

> Defined lifecycle epochs, cache identity, visibility, and fallback rules so
> failed or stale KV movement cannot silently affect a resumed request.

Root challenge:

> If a restore completes partially, late, or after cancellation, why is the next
> token still correct?

Follow-up branches:

```text
What is authoritative: tokens, GPU KV, CPU KV, or connector metadata?
At what granularity does a transferred block become visible?
What happens after full-load failure versus partial-block failure?
How are cancel-during-load and duplicate resume serialized?
How does an epoch reject stale completion without leaking capacity?
Which model, tokenizer, layout, and token fields belong in cache identity?
When does the runtime recompute, explicitly fail, or retry?
How is fallback output compared with the no-cache baseline?
```

Minimum evidence gate:

```text
state-machine and invariant tests
deterministic fault injection for at least one transfer failure
duplicate or stale-completion regression test
cancel-during-transfer and idempotent-cleanup regression tests
resource-cleanup assertion
fallback output-equivalence check
DecisionTrace record linking failure to outcome
```

Dangerous answer patterns:

```text
assuming connector success is atomic without verifying the contract
using retries without idempotency or visibility semantics
calling output plausibility a correctness oracle
claiming exactly-once behavior without cleanup and duplicate-event tests
```

Organic extension hooks:

```text
derived-state recovery
cache identity and prefix reuse
async scheduling and request abort
speculative-decoding accounting as a boundary question
```

### CT3: When Should KV Move Instead of Recompute?

State: `draft`

Candidate claim allowed only after its evidence gate:

> Measured the conditions under which CPU offload, GPU retention, or recompute
> changes resume latency and system pressure on a declared testbed.

Root challenge:

> Why is moving KV better than recomputing it, and did helping the resumed request
> hurt active requests?

Follow-up branches:

```text
How were prefill, store, restore, and queue delay measured on the real path?
How do context length, KV bytes, host-link bandwidth, and load move the boundary?
How does offload traffic interfere with active decode?
How are CPU-tier capacity and destination reservation handled?
Would batching restores improve bandwidth at the cost of resume TTFT?
How should batch size and maximum wait time be selected?
What happens during correlated resume bursts?
Which negative workload makes offload or retention lose?
```

Minimum evidence gate:

```text
environment manifest and exact launch command
raw prefill, store, restore, and end-to-end timing
contention or load sweep with repeated runs
active-request and resumed-request metrics
one negative operating region
trace attribution for the selected path
```

Dangerous answer patterns:

```text
using isolated memcpy time as restore latency
reporting only the request helped by the policy
calling memory limiting a simulation of different hardware
choosing batch or pressure thresholds without calibration
```

Organic extension hooks:

```text
PagedAttention block granularity
prefix caching and eviction pressure
continuous batching and preemption
chunked prefill and recompute cost
multi-tier and disaggregated KV movement
```

### CT4: Is Dynamic Policy Worth Its Complexity?

State: `draft`; conditional on CT1-CT3 producing real evidence.

Candidate claim allowed only after its evidence gate:

> Compared a transparent lifecycle policy with action-only baselines and a tuned
> static policy, including regions where dynamic control disabled itself or lost.

Root challenge:

> Why is a dynamic policy necessary instead of one tuned TTL or always-offload?

Follow-up branches:

```text
Do at least two reachable regimes favor different actions?
Was the static baseline tuned on a separate calibration split?
How much latency and scheduler complexity does the policy add?
What information is observable at decision time?
How does prediction or calibration error change the result?
When does the policy fall back to static behavior?
```

Minimum evidence gate:

```text
shared executors across all policy baselines
separate tuning and test workloads
decision-overhead measurement
action and outcome trace for each comparison
one ablation and one losing workload
```

Retirement rule:

Retire CT4 as a main claim when a tuned static policy is sufficient on all
reachable regimes or when current runtime observability cannot support an
attributable comparison. CT1-CT3 remain valid engineering outcomes.

## 5. Resume-Claim Rule

Every noun and result in a resume bullet is an API exposed to the interviewer.
Before a bullet is used, map it to:

```text
owned file or module
test or reproduction command
raw result or trace
rejected alternative
known negative case
validity boundary
one adjacent-scenario answer
```

If any required mapping is absent, narrow the bullet rather than invent an
answer. A dependency capability may be described as integrated or evaluated, not
implemented by the candidate.

## 6. Phase Output Rule

Each implementation or experiment phase should produce paired outputs:

```text
work sample: patch + tests + raw evidence
interview asset: updated claim tree + decision/incident note
```

The expected progression is:

1. **Mechanism conformance:** establish CT1 and one behavior-changing path
   through the candidate-owned controller; tracing alone does not pass.
2. **Correctness and calibration:** establish CT2 and the cost inputs for CT3.
3. **Pressure evaluation:** complete CT3 under load and preserve a negative case.
4. **Conditional mechanism work:** pursue CT4 or a data-plane fix only when prior
   evidence identifies a concrete problem.

## 7. Adjacent Topic Boundary

The project should create natural bridges to PagedAttention, prefix caching,
continuous batching, chunked prefill, connectors, and P/D disaggregation. It
must not add features merely to name every current inference topic.

MLA, quantization, and speculative decoding remain study topics unless owned code
or experiments make them part of a core contract. Until then, the correct answer
is the precise effect they might have on this project's assumptions and the fact
that the effect has not been measured here.

## 8. Pass Standard

The map is interview-ready when CT1-CT3 are `evidence-backed`, at least five
decision cards are closed, at least half of the JD-calibrated hook set is organic,
CT4 is either evidence-backed or honestly retired, and the candidate can:

```text
trace one request through owned code
show which runtime behavior disappears when the owned controller is bypassed
defend one rejected design
reproduce one correctness failure or injected fault
explain one measured performance trade-off
show one workload where the optimization loses
branch into adjacent runtime topics without laundering unimplemented work
```
