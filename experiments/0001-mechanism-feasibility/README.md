# Experiment 0001: Mechanism Feasibility

## Question

Can one pinned vLLM build reliably and observably produce these three paths for
the same model, prompt shape, block configuration, HBM budget, and server flags?

1. `gpu_hit`: prefix blocks remain resident and the resume request hits GPU KV.
2. `cpu_restore`: D2H store completes, GPU KV is unavailable, and resume performs
   a CPU hit followed by H2D restore.
3. `recompute`: both GPU and CPU copies are unavailable and resume performs full
   prefill.

This experiment validates mechanism and attribution. It does not evaluate a
dynamic policy.

## Before renting a GPU

Complete a vLLM hook-capability matrix that answers:

- where request completion releases block references;
- whether CPU store is proactive or eviction-triggered;
- how a new request triggers CPU load;
- which event proves asynchronous store/restore completion;
- whether a CPU copy can remain while the GPU entry is invalidated;
- whether both tiers can be invalidated to force recomputation;
- how session, turn, and lifecycle epoch map to real block outcomes.

Only after these are answered should `manifest.json` receive an exact vLLM
commit and patch hash.

## Inputs

- `../../configs/phase0.json`: frozen experiment defaults.
- `manifest.json`: provenance and pinning state.
- `workload.json`: deterministic action cases and required observations.

## Outputs

Future runs write immutable artifacts below `raw/`, which is ignored except for
its directory marker. A completed run must also record an environment manifest,
launch command, per-run DecisionTrace, output token hash, and variance summary.

## Pass gate

- requested and observed actions agree for every non-fallback run;
- CPU restore proves GPU miss plus CPU hit;
- recompute proves GPU miss plus CPU miss;
- token accounting is complete;
- greedy output has no unexplained difference;
- queue, transfer, prefill, and first-token timing are separable;
- the required engine change is maintainable and auditable.
