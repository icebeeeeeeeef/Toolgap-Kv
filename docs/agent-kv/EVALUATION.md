# Evaluation Plan

> Status: `roadmap`
>
> No GPU, simulator, or current-vLLM result exists yet. This file defines future
> evidence; examples and expected boundaries are not measurements.

## 1. Evaluation Objective

First determine whether a candidate-owned lifecycle controller over current vLLM
can enforce paths that are real, observable, safe, and attributable. Then map
retain/offload/recompute boundaries. Evaluate dynamic selection only after Gate B
in [ROADMAP.md](ROADMAP.md).

The evaluation must separate:

```text
mechanism conformance and attribution
owned-controller transition and bypass conformance
correctness and fallback
mechanism overhead
hardware transfer/compute ratio
memory-pressure effects
workload provenance
queueing and concurrency effects
```

## 2. Pre-Registered Hypotheses

### Gate A H1: Requested and Observed Paths Are Distinguishable

For one pinned vLLM build, at least CPU restore and full recompute, and preferably
GPU hit, can be forced and attributed through runtime evidence rather than inferred
from end-to-end latency alone. At least one lifecycle transition or fallback is
enforced by candidate-owned in-process code; bypassing that code removes the
behavior while leaving the default request path unchanged.

### Gate A H2: Fallback Is Explicit and Safe

A requested/observed mismatch is accepted only with an allowed fallback reason.
At least one restore or lifecycle failure safely recomputes or explicitly fails,
without silently reusing the failed materialization. Broader late-completion,
request-resurrection, hang, and capacity-cleanup coverage belongs to CT2/DC7.

### CT2 H3: Lifecycle Races Are Fenced by the Owned Controller

Illegal transitions, duplicate resume/completion, stale epochs, cancel during
transfer, and repeated cleanup are rejected or handled idempotently. Capacity
returns to baseline and ordinary requests do not enter candidate-owned state.

### Gate A H4: Timing Is Decomposable

Queue, store, restore, prefill, and first-token time can be separated on the real
path with complete token/block accounting and an output correctness check.

### CT3 H5: Transfer/Recompute Boundaries Are Measurable

Context/KV size and one pressure variable produce a reproducible cost or dominance
boundary, including an action that loses and active-request guardrails.

### Gate B0 H6: Multiple Decision Regimes Exist

At least two reachable regimes prefer different actions. This is unknown until
CT3 evidence exists; failure retires dynamic-policy work without invalidating
CT1-CT3.

### Conditional Gate B H7: Dynamic Selection Adds Net Value

A transparent selector improves the preregistered metric over tuned static and
action-only baselines on a separate test split without unacceptable decision
overhead, p95/p99 regression, or hidden executor differences.

## 3. Environment Manifest

Every real-system result must record:

```text
GPU model, count, memory, clocks or power limits
CPU model, sockets, cores, NUMA placement
RAM capacity and measured bandwidth if available
PCIe/NVLink/C2C topology
storage used by any lower tier
OS, kernel, driver, CUDA/ROCm
vLLM commit and local patch hash
model and tokenizer revision
KV dtype and attention backend
parallel configuration
all relevant vLLM flags
```

## 4. Baseline Definitions

### Default LRU / Recompute

Use the engine's documented default cache/preemption behavior. Record any hidden
offload or preemption behavior so the baseline does not gain an unreported action.

### Tuned Static TTL

Attempt this only in the post-CT3 Gate B0 admission audit and only when the pinned
runtime exposes fair TTL/retention semantics over the same executors. Tune on a
separate calibration split, report all candidates and the selected value, and do
not tune on the final test set. If a fair TTL seam does not exist, use the
strongest action-only/static substitute and preserve the missing-contract result.

### Soft Retention

Paused agent KV receives the highest available retention priority, but a documented
safety valve permits eviction when active allocation would otherwise fail. Do not
call this `always-retain`.

### Always Offload

Every eligible paused request is offered to the CPU tier subject to the same tier
capacity and failure semantics as the other candidate paths.

### Cost-Aware Dynamic Policy

Conditional on Gate B. It uses the same executors as static/action-only baselines;
only the decision rule changes. Before Gate B it is not an implementation target.

### Optional Paper-Inspired Policies

Use names such as `MinWaste-inspired` or `PBKV-inspired` unless implementation
fidelity is independently established. Record all semantic deviations.

## 5. Workload Dimensions

The benchmark generator must control:

```text
prompt and accumulated context length
generated tokens per turn
tool-gap duration distribution
resume and cancellation probability
shared-prefix ratio
number of turns
arrival process and concurrency
tenant/session mix
SLO target
```

Required workload classes:

| Workload | Purpose |
|---|---|
| Shared system/tool schema | Demonstrate reusable-prefix pressure |
| Multi-turn tool agent | Exercise repeated wait/resume transitions |
| Long-context resume | Increase recomputation cost |
| Short unique prompts | Negative case where transfer may be wasteful |
| Long non-repeating prompts | Negative case for cache reuse |
| Cancellation-heavy | Test wasted stores and cleanup |
| Burst load | Test pressure adaptation and tail latency |
| Distribution shift | Test calibration and prediction robustness |

Public traces may calibrate distributions, but sanitized traces that omit exact
tokens cannot be described as exact production replay.

Hugging Face agent trajectories such as
[AgentSuite/BFCL_V4-trajectories](https://huggingface.co/datasets/AgentSuite/BFCL_V4-trajectories)
may seed real turn, message, and tool-call structure. Their dataset cards do not
establish wall-clock tool latency, engine scheduler timing, GPU KV state, or
production arrival processes. Injected gaps, arrivals, cancellation, or pressure
must therefore be labeled `trace-derived synthetic` and calibrated against at
least one local real-vLLM trace.

## 6. Metrics

### User and Agent Metrics

```text
resume TTFT p50/p95/p99
end-to-end agent job completion time
time per turn
SLO attainment and Goodput@SLO
cancellation completion latency
```

`Goodput@SLO` means the number of completed agent jobs per unit time whose
declared latency metric satisfies the pre-registered SLO. The latency metric and
threshold must be fixed before the final test run.

### Serving Metrics

```text
requests/s
prompt and generation tokens/s
running and waiting requests
preemption count and duration
GPU KV usage
CPU tier usage
```

### Lifecycle Metrics

```text
retain/offload/recompute action counts
request-level and token-level cache hits
prefill tokens avoided or repeated
D2H/H2D bytes and latency
restore failures and fallback count
decision latency
estimated cost versus observed cost
action-switch and hysteresis counts
```

## 7. Hardware-Normalized Axes

Absolute latency is not portable. Report at least these ratios:

```text
R = T_restore / T_recompute
M = active_KV_working_set / usable_HBM
U = arrival_rate / measured_sustainable_service_rate
```

Where useful, add store cost, cancellation probability, and transfer utilization
as separate axes. Do not claim that restricting `gpu_memory_utilization` emulates
another GPU architecture; it only controls pressure on the same system.

## 8. Cost Microbenchmarks

Measure before evaluating policies:

1. Prefill latency over token length and batch/load.
2. D2H store latency over KV bytes and concurrent transfers.
3. H2D restore latency over KV bytes and concurrent transfers.
4. Lifecycle-controller overhead with the owned path bypassed and enabled;
   selector overhead is added only if CT4 opens.
5. HBM pressure effects on admission, preemption, and active decode.

These curves must come from the same engine path used by the end-to-end tests.

## 9. Conditional Hindsight References and Bounds

This section is Gate B-only and not required for the core CT1-CT3 work sample.
Do not implement an optimizer merely to make the evaluation look complete.

### Local Clairvoyant Lower Bound

Reveal the true gap and resume outcome for one event, choose the cheapest isolated
action, and ignore shared capacity. This is optimistic and generally infeasible.

### Exact Small-Instance Optimization

For a documented proxy objective, solve a small capacity-constrained trace exactly
with integer optimization. The objective, time representation, shared-block
assumptions, and transfer constraints must be explicit.

### Feasible Hindsight Heuristic

Produce an integral, capacity-feasible action plan for larger traces and replay it
in the real runtime. It is a strong comparator but not necessarily optimal.

### Reporting Rules

- A feasible heuristic is not an oracle or an upper bound.
- An LP relaxation of a maximization objective is an upper bound on proxy saving,
  not a replayable plan.
- Report LP/IP gap on small instances before using the LP bound at scale.
- Separate optimizer-model error from real-system queueing and transfer effects.
- Use compressed event boundaries where possible instead of arbitrary time slots.

## 10. Statistical Protocol

1. Run a variance pilot before fixing the number of repetitions.
2. Separate warmup from measured runs and clear state consistently.
3. Randomize or rotate policy order to reduce temporal bias.
4. Preserve per-run results; do not report only an aggregate.
5. Report medians and tail quantiles with uncertainty intervals where justified.
6. Investigate outliers before excluding them; publish exclusion rules.
7. Use separate tuning and test workloads.

## 11. Negative-Result Rules

The CT1-CT3 report must include applicable conditions where:

```text
offload is slower than recompute
retention harms active goodput
transfer contention reverses a decision
```

At Gate B0, include where the strongest fair static baseline wins. If Gate B then
opens, additionally include calibration shifts and regions where policy overhead
exceeds saved work. A dynamic policy that cannot disable itself or fall back in
these regions is not production-shaped.

## 12. Evidence Ledger

Maintain one row per material claim:

| Claim | State | Owned artifact | Environment/workload | Raw evidence | Validity boundary |
|---|---|---|---|---|---|
| Phase 0 event/trace contracts pass local tests | `shipped` | `src/toolgap_kv/phase0.py`, `tests/test_phase0.py` | Dependency-free local checks | `make check` | No vLLM behavior or performance |
| Canonical single-tool history does not provide a fully reusable APC block through the assistant semantic end | `experimentally validated` (negative) | `scripts/run_a01.py`, [A0.1 result report](../../experiments/0001-mechanism-feasibility/A0.1-results-2026-07-22.md) | One hand-authored fixture; Qwen2.5-7B-Instruct revision `a09a35458c702b33eeacc393d103063234e8bc28`; vLLM `0.25.1` commit `752a3a504485790a2e8491cacbb35c137339ad34`; NVIDIA A10 | Local ignored bundle `experiments/0001-mechanism-feasibility/raw/a0.1/a01-20260721T190035Z-span-v2/`; tracked SHA-256 list in report | `semantic_span_equal=true`, but ceiling `192 < a_end 198`; no APC hit/miss, CPU restore, lifecycle-runtime, or performance inference; blocks A0.2 on this pin/fixture |
| Candidate controller owns lifecycle semantics | `roadmap` | Future lifecycle runtime, adapter, removal/bypass and transition tests | Pinned vLLM plus deterministic event fixtures | `[future path]` | Audited paths and failures only |
| Three real lifecycle paths are attributable | `roadmap` | Experiment 0001 + future integration | `[pinned environment/workload]` | `[future raw path]` | Single pinned testbed |
| Restore failure safely falls back | `roadmap` | Future state-machine/adapter test | Deterministic fault injection | `[future path]` | Tested failure modes only |
| Transfer/recompute boundary is measured | `roadmap` | Runtime integration + benchmark | `[future hardware/workload]` | `[future path]` | Declared regimes only |
| Strongest fair static baseline is established | `roadmap`, Gate B0 | Future baseline ledger + shared executors | Separate tuning/test workloads | `[future path]` | TTL only if the pinned seam is fair |
| Dynamic selector beats the Gate B0 baseline | `roadmap`, Gate B only | Future selector + shared executors | `[future hardware/workload]` | `[future path]` | Only if Gate B opens |

Do not remove placeholders until evidence exists.

## 13. Decision-Card Closure

A measurement closes a decision card only when it records:

```text
the decision and at least two alternatives
the falsifiable expectation registered before measurement
the exact changed mechanism and attribution method
real measurement or deterministic fault evidence
the selected and rejected alternatives
one losing or applicability boundary
owned artifacts and one reproduction command
claim state and testbed/workload provenance
organic interview hooks supported by the decision
```

Artifact count, code size, or documentation length cannot substitute for a closed
card. The registry lives in [INTERVIEW_MAP.md](INTERVIEW_MAP.md).

## 14. Allowed Result Language

Good:

> On `[hardware]` with `[model]` under a trace-derived workload, the policy
> reduced `[metric]` by `[value]` relative to a separately tuned static TTL.

Not allowed:

> The system solves production Agent KV-cache management.

The latter exceeds the tested environment, workload provenance, and scale.
