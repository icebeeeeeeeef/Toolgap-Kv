# ToolGap-KV

ToolGap-KV is the repository codename for **KV Cache Lifecycle Runtime for
Tool-Using LLM Agents**. It investigates when a paused agent request should
retain KV in GPU HBM, offload it to CPU DRAM, or release it and recompute on
resume.

## Status

`Phase 0 / repository initialized`

There is no vLLM integration, GPU result, or measured performance claim yet.
The immediate goal is a source-level capability audit and a three-path mechanism
feasibility experiment.

## Start here

1. Read [`docs/agent-kv/PROJECT.md`](docs/agent-kv/PROJECT.md).
2. Read [`docs/agent-kv/ROADMAP.md`](docs/agent-kv/ROADMAP.md), especially Phase 0.
3. Read [`experiments/0001-mechanism-feasibility/README.md`](experiments/0001-mechanism-feasibility/README.md).
4. Run the local checks:

```bash
make check
```

The local checks do not require a GPU or third-party Python packages.

## Repository layout

```text
docs/agent-kv/                         approved project design and evidence rules
src/toolgap_kv/                        engine-independent Phase 0 contracts
tests/                                 contract tests
configs/phase0.json                    frozen first-experiment defaults
experiments/0001-mechanism-feasibility experiment protocol and future raw data
patches/                               auditable vLLM patch boundary
scripts/check_repository.py            dependency-free repository validation
```

## Scope guard

Initialization deliberately does not implement the lifecycle state machine or
choose a vLLM commit. Those choices depend on the source audit answering whether
current vLLM can expose per-request store, restore, invalidation, and observed
cache outcomes without a broad scheduler fork.
