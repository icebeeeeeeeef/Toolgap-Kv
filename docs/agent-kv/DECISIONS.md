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
| D004 | Start with a transparent analytic policy | accepted | Easier attribution and lower scope than prediction training | Calibration error is proven to require learned prediction |
| D005 | Prefer official runtime extension points to a core fork | accepted | Correct abstraction is stronger than patch volume | Required semantics or observability are missing |
| D006 | Treat retention as an interface risk | accepted | Proposed vLLM implementation is not stable mainline | A supported retention contract is verified on pinned mainline |
| D007 | Use tuned static TTL as the primary adaptive-policy challenger | accepted | Prevents winning only against weak LRU | Static TTL cannot be implemented fairly on target runtime |
| D008 | Include negative workloads and stop conditions | accepted | Optimization is workload-dependent | Never; this is an evidence invariant |
| D009 | Label execution and workload provenance separately | accepted | Real GPU execution does not make a synthetic workload production traffic | Never; only labels may change with evidence |
| D010 | Avoid first/novel mechanism claims | accepted | InferCept, Continuum, PBKV, and Astraea occupy the space | A fresh exhaustive review supports a precise claim |
| D011 | Run a calibration sprint before committing the full roadmap | accepted | Hardware, API, and repeatability are unresolved hard gates | Sprint completed with go/no-go evidence |
| D012 | Define runtime ownership by semantics and correctness, not core diff size | accepted | A real in-process plugin may own critical behavior without a broad fork | Implementation remains outside the serving process |
| D013 | Keep SGLang out of MVP | accepted | Cross-engine work requires independent fidelity and evidence | A specific radix-vs-block hypothesis survives Phase 2 |
| D014 | Do not make full PBKV reproduction mandatory | accepted | Predictor and engine fidelity would dominate scope | Original artifact becomes easy to replay as an optional calibration anchor |
| D015 | Use small exact optimization and feasible hindsight carefully | accepted | Global JCT oracle is coupled and potentially intractable | A tighter, validated scalable bound becomes necessary |
| D016 | Treat multi-tier/distributed platform work as separate extensions | accepted | Each can independently succeed or fail | Main lifecycle mechanism has complete evidence |
| D017 | Generate resume bullets only from an evidence ledger | accepted | Prevents roadmap-to-achievement inflation | Never |

## Rejected Directions

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
| NVMe/remote tier | Adds independent admission, transfer, and failure questions |
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
