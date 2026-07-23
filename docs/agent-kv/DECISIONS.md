# Decision Log

This file records major project choices so later discussion can distinguish a
new fact from a previously rejected idea.

## Status Values

```text
accepted: part of the current mainline
deferred: valid extension after the mainline succeeds
rejected: inconsistent with current scope or evidence standard
superseded: replaced by a later decision
```

## Current Decisions

| ID | Decision | Status | Rationale | Revisit trigger |
|---|---|---|---|---|
| D001 | Use vLLM as the primary engine | accepted | One engine controls variance and offers native offload policy hooks | vLLM cannot express lifecycle semantics with a maintainable change |
| D002 | Keep MVP single-node and HBM+CPU only | accepted | Smallest real system containing all three lifecycle costs | Main hypothesis validated and a new tier answers a specific question |
| D003 | Use native vLLM offload before LMCache | accepted | Fewer dependencies and clearer ownership | Cross-instance or additional-tier requirement is measured |
| D004 | Start with a transparent analytic policy | superseded | CT1-CT3 evidence must exist before any selector is justified | Gate B proves at least two reachable regimes prefer different actions |
| D005 | Prefer official runtime extension points to a core fork | accepted | Correct abstraction is stronger than patch volume | Required semantics or observability are missing |
| D006 | Treat context-aware retention as an interface risk | accepted | A prior token priority/duration proposal closed unmerged; current pinned behavior still requires audit | A supported retention contract is verified on the pinned target |
| D007 | Use tuned static TTL as the primary adaptive-policy challenger | superseded | Requiring the baseline only after Gate B creates a circular admission test | Replaced by D023 |
| D008 | Include negative workloads and stop conditions | accepted | Optimization is workload-dependent | Never; this is an evidence invariant |
| D009 | Label execution and workload provenance separately | accepted | Real GPU execution does not make a synthetic workload production traffic | Never; only labels may change with evidence |
| D010 | Avoid first/novel mechanism claims | accepted | InferCept, Continuum, PBKV, Astraea, and TokenCake directly overlap lifecycle/offload/policy ideas | Never for the project-level story; a narrow claim still requires fresh review |
| D011 | Run two-week Gate A before committing the full roadmap | accepted | Current vLLM seam, ownership, path attribution, hardware, and repeatability are unresolved | Gate A produces a pinned nominal trace, source-audited fault/fallback fixture, and first closed card |
| D012 | Define runtime ownership by semantics and correctness, not core diff size | accepted | A real in-process plugin may own critical behavior without a broad fork | Implementation remains outside the serving process |
| D013 | Keep SGLang out of MVP | accepted | Cross-engine work requires independent fidelity and evidence | A specific radix-vs-block hypothesis survives Phase 2 |
| D014 | Do not make full PBKV reproduction mandatory | accepted | Predictor and engine fidelity would dominate scope | Original artifact becomes easy to replay as an optional calibration anchor |
| D015 | Use small exact optimization and feasible hindsight carefully | accepted | Global JCT oracle is coupled and potentially intractable | A tighter, validated scalable bound becomes necessary |
| D016 | Exclude multi-tier/distributed platform work from the recruiting mainline | accepted | vLLM already ships multi-tier offload upstream, and distributed work adds independent contracts | A later project review identifies one measured missing contract |
| D017 | Generate resume bullets only from an evidence ledger | accepted | Prevents roadmap-to-achievement inflation | Never |
| D018 | Freeze ToolGap-KV as the only current recruiting-project mainline | accepted | Best fit for real serving work, storage-data-plane transferability, and deep evidence under available resources | Gate A proves no maintainable in-process or attributable real path |
| D019 | Fold Agent KV Regime Lab into the workload harness | accepted | Workload replay supports CT1-CT3 but lacks an independent candidate-owned runtime mechanism | A future review identifies a separate causal question and owned mechanism |
| D020 | Do not use NIXL fencing as an automatic fallback | accepted | It requires an independent unmodified-vLLM safety failing test and different P/D scope | Such a failing test exists and a new project review selects it |
| D021 | Stop current investment in KV State Ledger, deadline controller, and serving hint gateway | accepted | Each is an independent project with weaker current evidence conversion than CT1-CT3 | ToolGap-KV is stopped and a fresh four-variable review selects one |
| D022 | Make dynamic policy conditional CT4 | accepted | Prior art covers the mechanism idea; policy work adds value only when measured regimes disagree | Gate B passes all conditions in ROADMAP.md |
| D023 | Run a Gate B0 static-baseline admission audit after CT3 and before CT4 | accepted | Dynamic selection cannot be justified before comparison with the strongest fair static baseline; use tuned TTL only when the pinned runtime supports fair semantics, otherwise use an action-only/static substitute or record a missing contract | A later runtime exposes a stronger fair baseline, which must replace the substitute |
| D024 | Require a candidate-owned in-process logical lifecycle runtime for CT1-CT3 completion | accepted | The 2026-07-13 policy reduction accidentally allowed thin tracing to appear sufficient; runtime-project credibility requires owned lifecycle behavior, not only observation | Gate A proves no maintainable non-duplicative transition, fallback, or cleanup contract can be owned; then stop/reselect rather than downgrade silently |
| D025 | Reuse vLLM's physical KV data plane | accepted | Candidate ownership is lifecycle semantics and orchestration; rebuilding shared-block/refcount, PagedAttention, model execution, or D2H/H2D transfer adds scope without stronger interview evidence | A source-audited missing physical contract is reproduced and independently approved |
| D026 | Stop the A0.2/A1 branch after the A0.1 full-block coverage failure | superseded | The final real-GPU A0.1 run preserves semantic tool-call token equality but its reusable full-block ceiling is `192 < a_end 198`; the A0.2 input contract was therefore false under the original full-span coverage interpretation | Superseded by D027 after the separately reviewed A0.1R admission experiment directly observed stock APC materializing the eligible 192-token prefix |
| D027 | Reopen A0.2 for configuration-gated review after A0.1R stock-APC admission | superseded | Three independent pinned-vLLM A0.1R ordinals observed `R0.cached=0` and `R1.cached=192=C`; this directly disproves the interpretation that stock APC cannot materialize the canonical pair's eligible full-block prefix | Superseded by D028 after the valid 90-run A0.2 matrix satisfied neither a registered Stop nor Continue condition |
| D028 | Close A0.2 as experimentally validated `inconclusive` and do not enter A1 | accepted | Attempt 2 produced 90/90 valid observations under one frozen 3151-block capacity, but no registered Stop/Continue condition fired: stock S1 restored every material S0 miss, no material-cell direction reversal occurred, and request-scoped transfer overlap was unobservable | A separately reviewed gate establishes a maintainable request-scoped transfer seam or another candidate-owned non-duplicative contract with new preregistered falsification criteria; otherwise stop, narrow, or reselect under D018/D024 |
| D029 | Audit the pinned job-scoped offload failure contract as a load-recovery candidate; exclude the physical block fence | accepted | pin `752a3a5` is confirmed job-scoped and load failures still `assert` on both sync submission and async completion; the generic recompute receiving end exists and is tested but the Offloading Connector has no job-failure -> invalid-blocks bridge; the physical block-reuse fence is upstream-owned (#39186 / #45679) | A controlled fake-worker four-failure-class test proves no leaked job/fence, failed-request recompute, and unaffected unrelated requests; only then may Patch 1 be opened |

## Rejected Directions

### Parallel Autumn-Recruiting Mainlines

Status: `rejected`

Reason: ToolGap-KV is the only active recruiting mainline. Agent KV Regime Lab is
supporting workload infrastructure. NIXL fencing requires an independent failing
safety test before reevaluation. KV State Ledger, deadline-aware control, and
serving hints receive no current implementation time. This is a portfolio decision,
not a claim that those technical topics are unimportant.

### Full AIBrix-Lite Platform as the First Milestone

Status: `rejected`

Reason: gateway, autoscaling, multi-engine management, and KV lifecycle decisions
are independent mechanisms. Platform breadth would hide the owned runtime question.

### vLLM + SGLang + llama.cpp in the MVP

Status: `rejected`

Reason: heterogeneous routing does not help answer retain/offload/recompute
break-even and multiplies integration/testing work.

### Mooncake as a Mandatory llama.cpp Backend

Status: `rejected`

Reason: Mooncake's distributed KV and P/D use cases do not match llama.cpp's
lightweight local-serving role.

### New Learned Predictor as the Main Contribution

Status: `rejected`

Reason: PBKV and other systems already cover prediction-based lifecycle behavior;
model training would add an independent success criterion before runtime evidence.

### Global Exact JCT Oracle

Status: `rejected`

Reason: shared HBM, variable-sized state, transfer bandwidth, and queueing produce
a coupled optimization problem beyond the mainline. Use explicit bounds and small
exact instances instead.

### Core Fork as an Ownership Requirement

Status: `rejected`

Reason: modifying engine core without a missing contract creates maintenance risk.
Ownership is established by runtime semantics, correctness, failure behavior, and
measured hot-path impact.

## Deferred Extensions

| Extension | Why deferred |
|---|---|
| LMCache or Mooncake backend | Requires a measured native-offload limitation |
| Additional NVMe/remote-tier work | vLLM already has native tiering; requires a measured missing contract, not technology coverage |
| Multi-replica routing | Adds metadata consistency and routing trade-offs |
| SGLang adapter | Requires cross-engine fidelity work |
| Predictor training | Adds dataset, model, and drift-evaluation scope |
| Kubernetes/AIBrix deployment | Operational layer does not validate the core mechanism |
| Prometheus/Grafana dashboard | Useful after trace/metric semantics stabilize |

## Decision Update Template

```text
Date:
Decision ID:
New evidence:
Previous assumption:
Updated decision:
Scope impact:
Evidence/URL:
Documents updated:
```

## 2026-07-13 Reshape Record

```text
New evidence:
- Phase 0 scaffolding, seven domain-contract tests, and three validator regression
  tests exist, but no vLLM/GPU evidence exists.
- Direct prior art, especially TokenCake, covers tool-gap-aware proactive offload
  and predictive upload.
- Current vLLM ships native and multi-tier offload capabilities, so the candidate
  must own a narrower integration/correctness/attribution contract.

Previous assumption:
- Dynamic policy superiority was the project-level success condition.

Updated decision:
- CT1 integration, CT2 correctness/recovery, and CT3 measured boundary are the
  unconditional mainline.
- CT4 dynamic policy is Gate B only.
- A Gate B0 fair-static-baseline audit occurs after CT3 and before Gate B; tuned
  TTL is conditional on a real pinned-runtime seam.
- ToolGap-KV is the single recruiting project; alternatives are supporting,
  stopped, or independently gated.

Scope impact:
- Remove policy implementation from Gate A and weeks 3-8.
- Preserve forced/action-only baselines, negative results, and prior-art history.
- Require closed decision cards and organic interview hooks at every phase.
```

## 2026-07-14 Runtime-Ownership Correction

```text
New evidence:
- The original project definition and adversarial review both required a
  candidate-owned in-process lifecycle state machine.
- ARCHITECTURE, NARRATIVE, INTERVIEW_MAP, and correctness gates still assumed
  that ownership, while PROJECT and ROADMAP could be read as allowing a thin
  trace-only integration.

Previous assumption:
- Reducing policy scope and reusing native vLLM offload could also reduce the
  owned runtime to attribution hooks.

Updated decision:
- CT1-CT3 require a candidate-owned logical lifecycle controller for claims,
  epochs, legal transitions, idempotence, stale-completion fencing, action
  orchestration, fallback, cancellation, cleanup, and DecisionTrace.
- vLLM continues to own physical blocks/refcounts, eviction, PagedAttention,
  model execution, and native D2H/H2D movement.
- A trace-only integration or benchmark cannot complete the recruiting runtime
  project. If Gate A finds no non-duplicative owned semantic, stop/reselect.
- Dynamic selection remains conditional CT4; this correction does not restore
  policy work to the unconditional mainline.

Scope impact:
- Gate A must prove a behavior-changing controller vertical slice and a default
  path bypass, not only observed cache outcomes.
- The post-Gate-A contract phase explicitly implements the lifecycle runtime,
  adapters, fallback, cleanup, and race tests.
- A defensible CT1-CT3 plus Gate B0 completion is budgeted at roughly 220-320
  hours; the older eight-week outline is only a happy-path floor.
```

## 2026-07-22 A0.1 Full-Block Stop Record

> Historical record: D026 is preserved below unchanged. Its current status is
> `superseded` by D027; this record remains the source for the original A0.1
> full-span coverage result.

```text
Decision ID: D026

New evidence:
- The final A0.1 run on an NVIDIA A10, vLLM 0.25.1 commit
  752a3a504485790a2e8491cacbb35c137339ad34, and Qwen2.5-7B-Instruct revision
  a09a35458c702b33eeacc393d103063234e8bc28 produced stable R0 token IDs across
  five isolated engines.
- The assistant tool-call semantic span round-tripped exactly, but the measured
  full-block ceiling was 192 while its required end offset was 198. The
  preregistered A0.1 verdict is therefore `serialization_stop`.
- Exact command, environment, raw-bundle hashes, and invalid/provenance history
  are preserved in experiments/0001-mechanism-feasibility/A0.1-results-2026-07-22.md.

Previous assumption:
- If the semantic tool-call tokens round-tripped, A0.2 could test whether stock
  APC/native offload left a candidate-addressable recovery gap.

Updated decision:
- Do not start A0.2, ToolGapController, a custom offload wrapper, or a forced
  retain/offload/recompute runner on this fixture and pin.
- Do not add padding or alter this fixture merely to obtain block alignment.
- A continuation requires a separately reviewed question with its own stop
  condition; this result neither proves a vLLM performance limitation nor
  invalidates all possible tool-call representations.

Scope impact:
- The project has one experimentally validated negative applicability result,
  not a completed lifecycle runtime or a performance claim.
```

## 2026-07-22 A0.1R Stock-APC Admission Record

```text
Decision ID: D027

New evidence:
- A0.1R consumed the frozen A0.1 fixture and the 192-token prefix anchor without
  changing the A0.1 raw bundle or padding the fixture.
- On the NVIDIA A10, the pinned vLLM 0.25.1 commit
  752a3a504485790a2e8491cacbb35c137339ad34, and the pinned Qwen2.5-7B
  revision, three independent cold LLM ordinals each observed R0 cached tokens
  equal to 0 and R1 cached tokens equal to the eligible complete prefix C=192.
- Each ordinal retained LCP=199, semantic_span_equal=true, identical tracked
  input hashes, and a complete locally retained raw bundle. Exact hashes and
  execution boundaries are recorded in
  experiments/A0.1R-partial-block-residual/A0.1R-results-2026-07-22.md.

Previous assumption:
- D026 treated full-span coverage failure (192 < a_end 198) as a false A0.2
  input contract, so it stopped A0.2/A1 on this fixture and pin.

Updated decision:
- Preserve D026's A0.1 full-span coverage result and prohibit fixture padding.
- Treat stock APC admission of the eligible 192-token complete prefix as
  experimentally validated on this fixed no-pressure canonical pair.
- A0.2 may be redesigned and reviewed again, but must not execute until a
  source/runtime audit freezes a supported chunked-prefill scheduler pin and
  reconfirms the accounting mapping for that pin.
- This evidence does not authorize an offload policy, performance claim, or
  candidate-owned lifecycle runtime implementation.

Scope impact:
- The project has one A0.1 negative full-span coverage artifact and one A0.1R
  positive stock-APC admission artifact; they answer different questions.
- The next allowed work is configuration-risk closure followed by reviewed A0.2
  stock-sufficiency experimentation, not A1 or runtime implementation.
```

## 2026-07-23 A0.2 Stock-Sufficiency Record

```text
Decision ID: D028

New evidence:
- After one preserved provenance-invalid attempt, Attempt 2 completed the
  preregistered 3 lengths × 3 M bands × 5 pairs × 2 policies matrix.
- All 90 registered ordinals were valid observations under the same HND layout,
  chunked-prefill pin, block size 16, and explicitly frozen 3151-block GPU KV
  capacity.
- All six target/overload cells produced an S0 missing prefix: three were 5/5
  full recompute and three were 5/5 partial GPU hit.
- The three registered material full-miss cells had Δservice values of
  407.449 ms, 411.405 ms, and 1828.322 ms, all above the 5 ms screening
  threshold.
- In all 15 material pairs, S1 provided external cached-token evidence for the
  missing prefix; there were no unrestored material pairs.
- All three material cells were S1-foreground-faster in 5/5 pairs, so the
  registered foreground-direction reversal did not occur.
- The pinned connector exposes cumulative transfer counters but no
  request-scoped load start/end interval. transfer_overlap_observable=false was
  frozen before the matrix, so Stop 3 and Continue 2 were unavailable.
- No registered Stop or Continue condition fired. The aggregator returned
  inconclusive rather than selecting a favorable post-hoc interpretation.

Previous assumption:
- D027 allowed A0.2 to determine whether stock APC/native offload left a
  candidate-addressable recovery or global-cost gap that justified testing A1.

Updated decision:
- Close A0.2 as an experimentally validated inconclusive gate.
- Do not enter A1 or implement a candidate-owned lifecycle runtime from this
  evidence.
- Do not selectively add runs, redefine the three partial-miss cells as
  material, or treat S1's lower foreground TTFT as a ToolGap performance claim.
- Preserve S0/S1 and the full Attempt 1/Attempt 2 history as stock-baseline and
  negative/undecided evidence.
- Any continuation requires a separately reviewed ticket and a new
  preregistered question. A request-scoped transfer-observability investigation
  or a partial-miss boundary study may be proposed, but neither may
  retroactively convert A0.2 into a pass.
- If no maintainable, non-duplicative candidate-owned lifecycle contract can be
  stated and falsified, apply D018/D024 and stop, narrow, or reselect the
  recruiting mainline.

Scope impact:
- A0.2 capacity-pressure execution is now experimentally validated; its decision
  outcome is inconclusive.
- A1, CT1-CT3 lifecycle runtime, real tool-gap workload claims, and resume
  performance bullets remain roadmap-only and unauthorized.
- The immediate next unit of work is project-direction review, not runtime
  implementation or another GPU sweep.

Evidence/URL:
- experiments/A0.2-stock-sufficiency/
  A0.2-stock-sufficiency-results-2026-07-23.md
- experiments/A0.2-stock-sufficiency/results/attempt-02/
  a02-matrix-summary.json

Documents updated:
- docs/agent-kv/README.md
- docs/agent-kv/ROADMAP.md
- docs/agent-kv/EVALUATION.md
- docs/agent-kv/INTERVIEW_MAP.md
- experiments/A0.2-stock-sufficiency/README.md
```

## 2026-07-24 Pinned Job-Scoped Offload Failure Contract Audit

```text
Decision ID: D029

Title:
- Pinned job-scoped offload failure contract audit: load-recovery candidate;
  physical block fence excluded.

Verified evidence (read at pin 752a3a5, raw source, not report snippets):
- offloading/worker.py: the sync submission path runs
  `success = self.worker.submit_load(...)` / `submit_store(...)` followed by
  `assert success`; `get_finished` carries the comment
  `# we currently do not support job failures` then `assert transfer_result.success`.
  Both the sync-submission and async-completion failure paths therefore crash
  the worker. Store submission asserts as well.
- The state is job-scoped (`_load_jobs`, `_unsubmitted_store_jobs`,
  `_connector_worker_meta = OffloadingWorkerMetadata()`, `mark_completed`,
  `build_connector_worker_meta`); `TransferJob` uses `.src_spec`/`.dst_spec`.
  This confirms the pin is semantically aligned with post-#39186 job-scoping,
  though by Git topology the pin is DIVERGED from the #39186 merge commit, not a
  descendant.
- tests/v1/kv_connector/unit/test_kv_load_failure_recovery.py exercises
  `test_async_load_failure`, `test_sync_load_failure`,
  `test_sync_load_failure_with_shared_blocks`,
  `test_async_progressive_load_failure` via `invalid_block_ids` +
  `kv_load_failure_policy="recompute"` + `failed_recving_kv_req_ids` +
  `RequestStatus.WAITING_FOR_REMOTE_KVS`. The recompute RECEIVING end exists and
  is fully tested, but only for the generic connector path, NOT for the
  offloading connector's job -> invalid-block bridge.
- `TransferJobStatus` carries `pending_count` and success counting but stores no
  load-destination GPU block IDs, so `invalid_block_ids` cannot be derived from
  a job_id alone.

Conclusion:
- The pin is confirmed job-scoped; load failure still asserts (sync and async).
- The generic recompute receiving end already exists, but the Offloading
  Connector lacks the job-failure -> invalid-blocks bridge. This is a real,
  non-duplicative reliability-contract gap.
- Patch 1 is worth doing but has NOT reached the direct-start evidence
  threshold. This decision is an audit plus admission gate, not an approval.

Admission gate (must pass before Patch 1 is opened):
- Build a controlled fake worker and complete four failure-class tests:
  sync submission failure, async completion failure, multi-worker partial
  failure, and store failure discard + cleanup.
- Prove: no leaked job/fence state (`_jobs`, `transfer_jobs`,
  `_block_id_to_pending_jobs` are cleaned), the failed request recomputes, and
  unrelated requests are unaffected.

Minimal patch boundary (when opened):
- Add job-outcome reporting (terminal success/failure, not only a success
  count).
- Save and invalidate the load-destination block IDs so a failed load job can
  produce `invalid_block_ids`.
- On store failure, terminally discard and clean up job/fence bookkeeping.
- NO session epoch and NO ToolGap logical publication gate in the upstream
  patch; the only legitimate scheduler hook is a read-only read of
  scheduler-reduced completion in
  `OffloadingConnectorScheduler.update_connector_output()`.

Layered necessity:
- Patch 1 is a reliability contract (upstream/engine evidence), not ToolGap's
  differentiation and not a dependency of the session-epoch runtime.
- Do not block CT1-CT3 on it. If a CT2 claim asserts offload failure recovery,
  it needs this patch; otherwise delete that claim.

Correction folded in:
- Drop the "no one claimed it" argument. #39732 is an issue with no discussion;
  the load-only, unassigned state carries no signal. Rely instead on the
  assert-still-exists evidence in both the pin and current main.

Evidence/URL:
- vLLM #39186 (job-scoped rewrite, physical fence via _block_id_to_pending_jobs)
- vLLM #45679 (block-reuse fence tests)
- vLLM #19330 (generic recompute receiving end for P/D disagg)
- vLLM #39732 (load-only failure issue, no discussion, unassigned)
- pin 752a3a5 offloading/worker.py and test_kv_load_failure_recovery.py

Documents to update when Patch 1 opens:
- docs/agent-kv/ARCHITECTURE.md (lines 9, 291 already record the boundary)
- patches/README.md (line 12 already records: no Patch 1 until Gate A)
```
