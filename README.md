# ToolGap-KV

ToolGap-KV is the repository codename for **KV Cache Lifecycle Runtime for
Tool-Using LLM Agents**. It investigates when a paused agent request should
retain KV in GPU HBM, offload it to CPU DRAM, or release it and recompute on
resume.

## Status

`Phase 0 / repository initialized`

The engine-independent Phase 0 event/trace contracts, frozen experiment inputs,
repository validator, seven domain-contract tests, and three validator regression
tests are `shipped` (ten local tests total). There is no pinned vLLM integration,
real runtime lifecycle mechanism, GPU result, simulated result, or measured
performance claim yet; those remain `roadmap`.

The immediate goal is Gate A: a source-level capability audit followed by one
pinned-vLLM lifecycle-controller vertical slice and three-path attribution
experiment.

## Start here

1. Read [`CONTEXT.md`](CONTEXT.md) for canonical domain language; claim-state
   rules live in [`docs/agent-kv/README.md`](docs/agent-kv/README.md).
2. Read [`docs/agent-kv/FIRST_PRINCIPLES.md`](docs/agent-kv/FIRST_PRINCIPLES.md)
   for the recruiting objective and scope gates.
3. Read [`docs/agent-kv/PROJECT.md`](docs/agent-kv/PROJECT.md) and
   [`docs/agent-kv/ROADMAP.md`](docs/agent-kv/ROADMAP.md).
4. Read [`experiments/0001-mechanism-feasibility/README.md`](experiments/0001-mechanism-feasibility/README.md).
5. Run the local checks:

```bash
make check
```

The local checks do not require a GPU or third-party Python packages.

## Repository layout

```text
docs/agent-kv/                         approved project design and evidence rules
CONTEXT.md                             stable domain vocabulary and claim states
src/toolgap_kv/                        engine-independent Phase 0 contracts
tests/                                 contract tests
configs/phase0.json                    frozen first-experiment defaults
experiments/0001-mechanism-feasibility experiment protocol and future raw data
patches/                               auditable vLLM patch boundary
scripts/check_repository.py            dependency-free repository validation
```

## Scope guard

Initialization deliberately does not yet implement the runtime lifecycle state
machine, dynamic policy, or choose a vLLM commit. Gate A determines the concrete
vLLM object and extension seam for the state machine; it does not make candidate
ownership of lifecycle semantics optional. Full CT1-CT3 completion requires the
smallest candidate-owned, in-process controller for epochs, transitions,
fallback, cancellation, cleanup, and DecisionTrace while reusing vLLM's block
manager and native tensor-transfer data plane. A trace-only adapter does not pass.
