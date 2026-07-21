# ToolGap-KV Domain Context

This glossary defines stable project language. Technical behavior remains subject
to the claim states and evidence linked from `docs/agent-kv/`.

## Project Identity

- **KV Cache Lifecycle Runtime for Tool-Using LLM Agents** is the descriptive
  project name used for recruiting and unfamiliar readers.
- **ToolGap-KV** is the repository codename.
- **Tool gap** is the interval between an LLM segment emitting a tool call and a
  later segment receiving the tool result.

## State and Lifecycle

- **Authoritative state** is the exact token history plus a compatible model,
  tokenizer, template, and runtime identity.
- **KV materialization** is derived state in GPU or lower-tier memory. It may be
  retained, moved, invalidated, or recomputed from authoritative state.
- **Lifecycle claim** is a logical session/turn/epoch interest in preserving or
  recovering compatible KV. It does not imply that the session physically owns
  shared, content-addressed prefix blocks. The pinned-vLLM source audit must
  determine the real block, reference, and residency contracts.
- **Lifecycle runtime/controller** is the candidate-owned, in-process control
  module that owns lifecycle claims and epochs, legal transitions, idempotence,
  stale-completion fencing, requested-action orchestration, fallback,
  cancellation, cleanup, and DecisionTrace. It does not move tensors itself.
- **Physical KV data plane** is the vLLM-owned implementation for shared block
  residency and reference counting, eviction, PagedAttention, model execution,
  and native D2H/H2D movement. ToolGap-KV adapts this plane rather than replacing
  it.
- **Requested action** is the action requested by the experiment or selector:
  `retain`, `offload`, or `recompute`.
- **Observed action** is the data path proven by runtime evidence: `gpu_hit`,
  `cpu_restore`, or `recompute`.
- **Fallback reason** explains why observed execution differs from the requested
  action. A difference without an allowed, recorded fallback is a contract failure.
- **DecisionTrace** is the structured causal record connecting lifecycle identity,
  requested action, observed path, fallback, token/block accounting, timings, and
  outcome. It is an output of the lifecycle contract, not a substitute for the
  controller that enforces that contract.

## Evidence Units

- **Decision card** records one engineering choice: context, alternatives,
  falsifiable expectation, observation, decision, rejected alternatives, and
  applicability boundary.
- **Closed decision card** additionally links a real measurement or deterministic
  fault result, exact owned artifacts, and one reproduction command. Reading or
  design alone cannot close a card.
- **Evidence pack** is the supporting patch or extension, tests, raw trace or
  benchmark result, decision/incident note, reproduction command, and validity
  boundary for a card.
- **Testbed provenance** names the real engine commit, patch hash, model revision,
  hardware, flags, workload source, and run protocol. `Real testbed` describes
  provenance; it is not a claim state.

## Claim States

The canonical definitions and maintenance rules live in
[`docs/agent-kv/README.md`](docs/agent-kv/README.md). The glossary mirrors their
names here so domain language remains readable; if wording ever diverges, the
project documentation definition governs.

- `roadmap`: planned or proposed; not implemented.
- `shipped`: implemented and exercised in the stated system.
- `experimentally validated`: measured under a declared environment and workload.
- `simulated`: supported only by replay, trace, optimizer, cost model, or simulator,
  with calibration limits stated.

One artifact may use different states on different axes. For example, execution
may be `experimentally validated` on a single GPU while the workload remains
`trace-derived synthetic` and the scale remains explicitly non-production.
