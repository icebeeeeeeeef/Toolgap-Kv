# Roadmap

## 1. Roadmap Principles

1. Evidence precedes feature expansion.
2. One deep lifecycle mechanism is the mainline.
3. Every phase has a go/no-go gate.
4. Negative results are valid deliverables.
5. Multi-engine, multi-tier, and distributed work are separate extensions.
6. No milestone may be described as complete before its artifacts are verified.

## 2. Phase 0: Calibration Sprint

### Purpose

The sprint does not attempt to prove the final policy. It tests whether the
project is feasible on the available hardware and current vLLM architecture.

### Required Work

1. Record the GPU, CPU, RAM, NUMA, PCIe topology, driver, CUDA/ROCm, and storage.
2. Pin and build one vLLM commit from source.
3. Run a supported model with automatic prefix caching and native CPU offload.
4. Add one minimal in-process decision/metrics hook.
5. Build one deterministic tool-wait workload with fixed prompt, gap, and resume.
6. Run `recompute` and `always-offload` A/B paths.
7. Measure `T_prefill(tokens)`, `T_store(bytes)`, and `T_restore(bytes)`.
8. Write a one-page result with commands, raw data paths, variance, and patch size.

### Deliverables

```text
environment manifest
pinned dependency commit
reproducible launch command
minimal runtime patch or plugin
one DecisionTrace schema and sample
raw A/B result
cost-curve plot or table
go/no-go decision
```

### Go Conditions

Continue when all are true:

- lifecycle and offload events are observable;
- A/B behavior is reproducible enough to attribute differences;
- current hooks can express the required behavior with a maintainable change;
- at least two reachable regimes favor different actions, or a credible path to
  such regimes exists on a second hardware configuration;
- failures do not silently corrupt or reuse incompatible KV.

### Pivot Conditions

| Observation | Pivot |
|---|---|
| Retention is not expressible without a broad fork | Offload/recompute study or minimal retention API contribution |
| One action dominates every reachable regime | Hardware boundary measurement study |
| Static TTL is already near the credible bound | Static-policy measurement and failure-domain report |
| Runs are too noisy to attribute decisions | Fix harness and instrumentation before policy work |
| Hardware cannot run a representative model/context | Reduce model only for plumbing; rent a validation GPU or change project scope |

## 3. Phase 1: Minimum Credible Runtime

### Scope

```text
one vLLM commit
one local serving instance
GPU HBM + CPU DRAM
one model family
deterministic tool-wait workload
```

### Implementation

1. Lifecycle state machine with epochs and legal transitions.
2. DecisionTrace integrated with real block and transfer outcomes.
3. Retain, offload, and recompute executors.
4. Baseline policies:
   - default LRU/recompute;
   - tuned static TTL;
   - soft retention;
   - always offload;
   - analytic cost-aware policy.
5. Cancellation, duplicate resume, and transfer-failure fallback tests.
6. Reproducible benchmark runner and environment manifest.

### Exit Gate

The phase exits only when the policy's selected action can be traced to measured
inputs and the actual runtime outcome can be attributed to that action.

## 4. Phase 2: Research-Grade Single-Node System

### Policy and Calibration

- pressure-dependent HBM opportunity cost;
- transfer contention measurement;
- online correction of profiler prediction error;
- bounded hysteresis to avoid action thrashing;
- explicit fallback when confidence is low.

### Evaluation

- shared system prompt workload;
- multi-turn agent workload;
- long-context resume workload;
- low-reuse and cancellation-heavy negative workloads;
- load and distribution-shift sweeps;
- at least two materially different hardware cost regimes if feasible.

### Offline References

- local clairvoyant lower bound;
- exact small-instance integer optimization under a documented proxy model;
- feasible hindsight heuristic for larger traces;
- real-system replay of the feasible plan.

These references are not called a global optimal oracle unless their assumptions
and optimality are actually proven.

### Reliability

- cancellation during store/restore;
- backend restart and stale metadata;
- tier capacity exhaustion;
- incompatible cache identity;
- partial transfer failure;
- deterministic race reproduction and regression tests.

### Exit Gate

Publish the dynamic-policy claim only when it beats the tuned static baseline in
pre-registered positive regions, does not hide losses in negative regions, and
keeps decision overhead within the declared budget.

## 5. Phase 3: Independent Extensions

Each item below is an independent subproject with its own baseline and evidence.

### Multi-Tier Storage

Add NVMe or remote KV storage, admission, promotion/demotion, transfer scheduling,
and tier-level observability. LMCache or Mooncake may be evaluated as dependencies.

### Multi-Replica Routing

Add session affinity, cache locality, queue pressure, stale metadata reconciliation,
and route-decision traces across vLLM replicas.

### Cross-Engine Study

Add SGLang only when an explicit question requires comparing radix-node and
block-level lifecycle semantics. Maintain a deviation ledger; do not label a
simplified port as a reproduction of the original system.

### Prediction

Add duration or resume prediction only when the analytic policy has a measured
error source that prediction can address. Prediction accuracy is not itself a
serving objective.

## 6. Phase 4: Production Platform Direction

This is a team-scale roadmap, not the personal-project mainline:

```text
multi-tenant quota and fairness
HA metadata and reconciliation
Kubernetes deployment and autoscaling
rolling engine upgrades and compatibility
security and isolation
fleet-level cost accounting
on-call diagnostics and runbooks
```

Without production traffic or a representative cluster, these features may be
implemented as engineering exercises but cannot support production claims.

## 7. Cut Order

If scope must shrink, remove work in this order:

1. cross-engine comparison;
2. PBKV-inspired or learned prediction baseline;
3. large-instance LP relaxation;
4. NVMe/remote tiers;
5. multi-replica routing;
6. orchestration and dashboards.

Do not cut deterministic replay, negative workloads, failure tests, or the tuned
static baseline. They are core evidence rather than optional polish.

## 8. Milestone Evidence Table

| Milestone | Required evidence | Allowed claim state |
|---|---|---|
| Design only | Reviewed docs | `roadmap` |
| Plumbing complete | Tests and one real request trace | `shipped` for plumbing only |
| A/B complete | Raw runs and environment manifest | `experimentally validated` for that environment |
| Trace/optimizer only | Replay or solver artifacts | `simulated` |
| Multi-hardware validation | Separate manifests and raw runs | `experimentally validated` within tested regimes |
| Resume bullet | Claim-to-artifact mapping | Only verified statements |
