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

No action dominates across all hardware and workload regimes.

## 2. Precise Problem Statement

For each tool-wait event, choose `retain`, `offload`, or `recompute` to improve
agent resume latency and system goodput while respecting HBM, transfer, fairness,
and correctness constraints.

The choice is made without knowing the exact future tool duration, cancellation
outcome, queue state, or competing memory demand.

## 3. Falsifiable Question

> Under which values of restore/recompute cost ratio, active KV working-set
> pressure, arrival load, gap duration, and resume probability does a dynamic
> lifecycle policy materially outperform a tuned static TTL without causing
> unacceptable tail latency or scheduler overhead?

This question is intentionally narrower than building a general inference
gateway or distributed KV store.

## 4. Hypothesis and Causal Chain

### Hypothesis

A hardware-calibrated policy can outperform one fixed TTL when the workload
contains multiple decision regimes and when runtime pressure changes enough to
alter the cheapest lifecycle action.

### Causal Chain

```text
tool waits make useful KV temporarily idle
    -> concurrent agents create HBM pressure
    -> retain/offload/recompute have different resource costs
    -> those costs vary with hardware, request state, and queue pressure
    -> a calibrated runtime policy can choose lower-cost actions
    -> less avoidable recompute or transfer reduces resume TTFT and SLO misses
```

If the best static TTL performs nearly as well as the strongest credible
hindsight bound, the hypothesis is rejected and the project becomes a
measurement study rather than an adaptive-policy claim.

## 5. First-Principles Cost Model

The initial model is deliberately transparent:

```text
C_retain = HBM opportunity cost(bytes, gap, pressure)

C_offload = T_store(bytes, contention)
          + P(resume) * T_restore(bytes, contention)
          + failure and queue penalties

C_recompute = P(resume) * T_prefill(tokens, batch, load)
```

The runtime chooses the feasible action with the lowest estimated cost, then
records both the estimate and observed outcome. The model must be calibrated on
the actual testbed; hardware names are not substitutes for measured curves.

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

1. Implement a request-level lifecycle state machine inside the serving process.
2. Measure prefill, store, restore, and pressure-dependent cost curves.
3. Implement one transparent cost-aware policy and fair static baselines.
4. Record decision-level traces that explain every action and result.
5. Exercise cancellation, duplicate resume, transfer failure, and fallback.
6. Identify positive and negative operating regions on a real GPU testbed.
7. Produce a reproducible report and, where appropriate, an upstream issue or PR.

## 8. Non-Goals

The mainline does not attempt to:

- train or modify the base LLM;
- invent attention kernels or replace PagedAttention;
- build a general-purpose distributed KV store;
- reproduce all of InferCept, Continuum, PBKV, or Astraea;
- claim production validation from a single-node testbed;
- use multiple engines merely for technology coverage;
- claim a first or novel lifecycle mechanism without a fresh literature audit.

## 9. Success Conditions

The project is successful as a runtime project when it provides:

```text
one pinned and reproducible vLLM integration
one owned in-process lifecycle state machine
one calibrated policy with bounded hot-path overhead
fair static and action-only baselines
deterministic decision traces
positive and negative workloads
failure-path tests
real-testbed measurements with an explicit validity boundary
```

The dynamic policy does not need to win everywhere. A credible failure-domain
map is more valuable than a selectively reported maximum speedup.

## 10. Stop and Pivot Conditions

Stop expanding the adaptive-policy mainline when any of these holds:

1. Current vLLM APIs cannot express the required lifecycle semantics without a
   large, unstable fork.
2. One action dominates across all reachable cost regimes on available hardware.
3. Repeated experiments cannot isolate policy effects from run-to-run noise.
4. A tuned static TTL closes nearly all useful gap to the credible hindsight bound.
5. A new upstream implementation makes the owned mechanism redundant before the
   project has meaningful evidence.

Valid pivots include an offload/recompute boundary study, a retention API
contribution, a deterministic agent workload harness, or a negative-result
measurement report.

## 11. Project Scale

These are roadmap estimates, not completed work:

| Level | Scope | Approximate engineering magnitude |
|---|---|---|
| Calibration | One engine, one model, minimal hook, one A/B | Two-week go/no-go sprint |
| MVP | Single node, HBM+DRAM, one policy, baselines, replay | Several engineer-months |
| Research-grade | Reliability, bounds, multiple workloads/hardware | Roughly 6-10 engineer-months |
| Distributed extension | Multi-tier, multi-replica, routing | Separate multi-engineer effort |
| Production platform | HA, multi-tenancy, upgrades, operations | Team-scale program, not a resume mainline |
