# External Review Brief: ToolGap-KV after A0.2 and D029

> Status: review input, not an implementation authorization.
>
> Last updated: 2026-07-24

This brief lets a reviewer working only from GitHub evaluate the current project
state without treating local conversation summaries as evidence.

## Review order

1. Read [README.md](README.md), [ROADMAP.md](ROADMAP.md),
   [ARCHITECTURE.md](ARCHITECTURE.md), [EVALUATION.md](EVALUATION.md), and
   [DECISIONS.md](DECISIONS.md).
2. Read the source experiment records:
   [A0.1](../../experiments/0001-mechanism-feasibility/A0.1-results-2026-07-22.md),
   [A0.1R](../../experiments/A0.1R-partial-block-residual/A0.1R-results-2026-07-22.md),
   and [A0.2](../../experiments/A0.2-stock-sufficiency/A0.2-stock-sufficiency-results-2026-07-23.md).
3. Independently inspect the pinned vLLM source and upstream records cited below.

## Project boundary

ToolGap-KV proposes a candidate-owned, **in-process logical lifecycle runtime**
for a tool-using request. It owns logical `(session_id, turn_id, epoch)` identity,
legal transitions, idempotence, cancellation, fallback, cleanup, and
`DecisionTrace`. It must use a maintainable vLLM integration seam; an external
HTTP proxy or trace-only observer is not sufficient evidence of runtime
ownership.

vLLM remains the physical KV data plane: block residency/refcounts, eviction,
PagedAttention, model execution, D2H/H2D, native transfer job reduction, and
physical block-reuse safety. CUDA/kernel work, multi-node work, and a new KV
storage layer are excluded.

The desired logical paths are `retain`, `offload`, and `recompute`. Dynamic
selection is conditional CT4 work; it is not the initial project contribution.

## Evidence ledger

| Item | State | What it establishes | What it does not establish |
|---|---|---|---|
| A0.1 | experimentally validated, negative | Tool-call token semantics aligned, but the original fixture's reusable full-block ceiling was 192 rather than the 198-token semantic end | APC/offload performance or a runtime |
| A0.1R | experimentally validated | Stock APC can materialize the eligible 192-token prefix under the pinned configuration | Pressure behavior, ToolGap benefit, or lifecycle ownership |
| A0.2 Attempt 2 | experimentally validated, `inconclusive` | 90/90 valid capacity-pressure runs; S0 has full/partial misses; S1 restores all three preregistered material full misses | A candidate-owned gap, real tool-gap performance, transfer/QoS causality, or authorization for CT1-CT3 |
| D029 source audit | accepted audit/admission gate | Pin is job-scoped; offloading load failures still assert; generic invalid-block recompute receiver exists; physical block fence is upstream-owned | Approval to implement Patch 1 or a complete runtime |

### A0.2 details that must remain fixed

- Testbed: vLLM `0.25.1`, pin
  `752a3a504485790a2e8491cacbb35c137339ad34`, Qwen2.5-7B-Instruct, NVIDIA A10,
  HND layout, block size 16, frozen GPU KV capacity 3151 blocks.
- Comparison: S0 stock APC versus S1 stock APC plus native CPU
  `OffloadingConnector`.
- Matrix: 3 prefix lengths x 3 pressure bands x 5 pairs x 2 policies = 90 runs.
- Three material full-miss cells had S1 restore coverage, but the pin lacked
  request-scoped load start/end intervals. Thus no restore-versus-active-request
  transfer overlap conclusion is available.
- Three partial-miss cells are hypothesis-generating only. They cannot be
  retroactively promoted to material cells.

D028 closes A0.2. Do not propose selective extra A0.2 runs or use it as a pass
into A1.

## Pinned vLLM audit and Patch 1 candidate

The pin is not a Git descendant of the #39186 merge commit, but its source is
already job-scoped: `TransferJob`, `store_jobs`, `load_jobs`,
`completed_jobs`, `TransferJobStatus`, and `_block_id_to_pending_jobs` exist.
Architectural decisions must follow that source shape rather than the obsolete
request-scoped `reqs_to_store` model.

Pinned source and upstream records to inspect:

- [pin worker.py](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/vllm/distributed/kv_transfer/kv_connector/v1/offloading/worker.py)
- [pin scheduler.py](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/vllm/distributed/kv_transfer/kv_connector/v1/offloading/scheduler.py)
- [pin generic load-recovery test](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/tests/v1/kv_connector/unit/test_kv_load_failure_recovery.py)
- [vLLM #39186](https://github.com/vllm-project/vllm/pull/39186)
- [vLLM #45679](https://github.com/vllm-project/vllm/pull/45679)
- [vLLM #19330](https://github.com/vllm-project/vllm/pull/19330)
- [vLLM #39732](https://github.com/vllm-project/vllm/issues/39732)

At the pin, synchronous submission and asynchronous completion both assert on
transfer failure. `completed_jobs` is a success count reduced across workers;
it is not a failure protocol. The generic scheduler can consume
`invalid_block_ids` and apply recompute, but the Offloading Connector does not
bridge a failed job to the precise destination blocks that must be invalidated.

Patch 1 is therefore a candidate **load-failure recovery** contribution, not a
new physical fence and not ToolGap's differentiation. It may start only after a
controlled fake-worker admission test proves all of the following:

1. synchronous load submission failure;
2. asynchronous completion failure;
3. multi-worker partial success/failure;
4. store failure discard and cleanup.

Those tests must show failed-request recompute/fail behavior, no leaked `_jobs`,
`transfer_jobs`, or `_block_id_to_pending_jobs` state, and no impact on an
unrelated request. If a patch is then necessary, it must be a small Python-level
connector/scheduler contract patch: typed terminal job outcome, exact failed-load
destination block identification, existing recompute/fail routing, and failed
store cleanup. It must not modify CUDA kernels, PagedAttention, refcounts,
physical fences, or inject ToolGap epoch logic into vLLM.

## Questions the reviewer must answer

Classify each conclusion as `confirmed`, `inference`, `unsupported`, or
`contradicted`.

1. Does A0.2's stock S1 coverage make the candidate lifecycle runtime
   unjustified, or is there one remaining non-duplicative, falsifiable lifecycle
   contract worth testing?
2. Is the D029 Patch 1 scope truly minimal and upstream-worthy? Is there a
   supported extension that makes it unnecessary?
3. Is session/epoch logical publication control genuinely separate from vLLM's
   physical block-reuse fence?
4. Should the project stop, narrow to a vLLM reliability contribution, or
   continue under one newly preregistered gate? If continuing, specify exactly
   one question, its metrics, fault injection, Stop/Continue criteria, and
   deliverables.
5. What evidence would be required before any resume or upstream-contribution
   claim is allowed?

The reviewer should prefer a stop/narrow recommendation over inventing a broad
controller. A favorable conclusion must identify an owned runtime transition or
fallback that disappears under a removal/bypass test.
