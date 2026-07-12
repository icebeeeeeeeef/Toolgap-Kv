# Evaluation Plan

## 1. Evaluation Objective

Determine when lifecycle decisions improve real agent-serving outcomes and when
the simplest static policy is sufficient.

The evaluation must separate:

```text
policy quality
mechanism overhead
hardware transfer/compute ratio
memory-pressure effects
workload provenance
queueing and concurrency effects
```

## 2. Pre-Registered Hypotheses

### H1: Multiple Decision Regimes Exist

Retain, offload, and recompute each minimize cost in at least one reachable
combination of context length, tool gap, resume probability, and resource pressure.

### H2: Dynamic Policy Beats One Fixed TTL Selectively

The dynamic policy improves resume TTFT or Goodput@SLO over the best tuned static
TTL in heterogeneous or shifting workloads, not necessarily in stationary ones.

### H3: Hardware Changes the Boundary

A faster GPU may make recomputation cheaper, a faster host link may make offload
cheaper, and larger HBM may make retention cheaper. The policy's action regions
should move consistently with measured cost curves.

### H4: Pressure Matters

Isolated request latency is insufficient. An action that helps one request may
hurt system goodput through HBM occupancy, transfer contention, or blocked decode.

### H5: Failure Safety Is Measurable

Transfer and lifecycle failures must fall back without incorrect KV reuse,
request resurrection, silent hangs, or unexplained completion changes.

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

Tune TTL on a separate calibration split. Report both the default candidate TTLs
and the selected value. Do not tune on the final test set.

### Soft Retention

Paused agent KV receives the highest available retention priority, but a documented
safety valve permits eviction when active allocation would otherwise fail. Do not
call this `always-retain`.

### Always Offload

Every eligible paused request is offered to the CPU tier subject to the same tier
capacity and failure semantics as the dynamic policy.

### Cost-Aware Dynamic Policy

Uses the same executors as the static baselines. Only the decision rule changes.

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
4. Scheduler/decision overhead with the policy disabled and enabled.
5. HBM pressure effects on admission, preemption, and active decode.

These curves must come from the same engine path used by the end-to-end tests.

## 9. Hindsight References and Bounds

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

The report must include conditions where:

```text
static TTL wins
offload is slower than recompute
retention harms active goodput
prediction or calibration shifts
transfer contention reverses a decision
policy overhead exceeds saved work
```

A dynamic policy that cannot disable itself or fall back in these regions is not
production-shaped.

## 12. Evidence Ledger

Maintain one row per material claim:

| Claim | State | Owned artifact | Environment/workload | Raw evidence | Validity boundary |
|---|---|---|---|---|---|
| Dynamic policy lowers p95 resume TTFT by `[X]` | Not measured | Policy + harness | `[hardware/workload]` | `[path]` | `[scope]` |
| Restore failure falls back without corruption | Not implemented | State-machine test | Fault injection | `[path]` | Tested failure modes only |
| Static TTL approaches hindsight bound | Not measured | Optimizer + replay | `[trace]` | `[path]` | Proxy assumptions |

Do not remove placeholders until evidence exists.

## 13. Allowed Result Language

Good:

> On `[hardware]` with `[model]` under a trace-derived workload, the policy
> reduced `[metric]` by `[value]` relative to a separately tuned static TTL.

Not allowed:

> The system solves production Agent KV-cache management.

The latter exceeds the tested environment, workload provenance, and scale.
