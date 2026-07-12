# ToolGap-KV Project Initialization Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the approved ToolGap-KV roadmap into a clean, self-checking repository that is ready for the Phase 0 vLLM source spike without pretending the runtime integration already exists.

**Architecture:** Preserve the approved design under `docs/agent-kv/`, keep the executable code limited to engine-independent Phase 0 contracts, and place all experiment inputs under a numbered experiment directory. A standard-library validation command checks repository structure and JSON inputs before any GPU work begins.

**Tech Stack:** Python 3.10+, standard library, `unittest`, JSON, Make, Git.

---

### Task 1: Establish repository boundaries

**Files:**
- Create: `README.md`
- Create: `AGENTS.md`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `Makefile`

- [x] **Step 1:** Document the project as roadmap/Phase 0 work and link the approved design.
- [x] **Step 2:** Record collaboration and evidence rules in `AGENTS.md`.
- [x] **Step 3:** Configure a dependency-free Python package and deterministic `make check` entrypoint.
- [x] **Step 4:** Run `make check`; expected result is a non-zero exit until Tasks 2 and 3 exist.

### Task 2: Define the engine-independent Phase 0 contract

**Files:**
- Create: `src/toolgap_kv/__init__.py`
- Create: `src/toolgap_kv/phase0.py`
- Create: `tests/test_phase0.py`

- [x] **Step 1:** Write tests for lifecycle action parsing, event invariants, and trace accounting.
- [x] **Step 2:** Run `python3 -m unittest discover -s tests -v`; expected result is failure because `toolgap_kv.phase0` does not exist.
- [x] **Step 3:** Implement immutable standard-library contracts with explicit validation.
- [x] **Step 4:** Re-run unit tests; expected result is all tests passing.

### Task 3: Create Experiment 0001 inputs and repository validation

**Files:**
- Create: `configs/phase0.json`
- Create: `experiments/0001-mechanism-feasibility/README.md`
- Create: `experiments/0001-mechanism-feasibility/manifest.json`
- Create: `experiments/0001-mechanism-feasibility/workload.json`
- Create: `experiments/0001-mechanism-feasibility/raw/.gitkeep`
- Create: `patches/README.md`
- Create: `scripts/check_repository.py`

- [x] **Step 1:** Encode only frozen Phase 0 defaults; mark the vLLM revision as blocked on source audit rather than inventing a commit.
- [x] **Step 2:** Add a deterministic workload containing GPU-hit, CPU-restore, and recompute cases with per-run cache salts.
- [x] **Step 3:** Implement a standard-library repository checker that loads every JSON file through the Phase 0 contracts and verifies required paths.
- [x] **Step 4:** Run `make check`; expected result is unit tests passing and `repository check: ok`.

### Task 4: Initialize and verify Git state

**Files:**
- Modify: repository metadata only.

- [x] **Step 1:** Run `git init -b main`.
- [x] **Step 2:** Run `git diff --check`; expected result is no whitespace errors.
- [x] **Step 3:** Run `make check`; expected result is success.
- [x] **Step 4:** Inspect `git status --short` and confirm only intended initialization files are present.

## Self-review

- Scope is limited to initialization and Phase 0 contracts; it does not claim vLLM integration.
- The approved project documents cover architecture, evaluation, roadmap, decisions, and interview boundaries.
- The target vLLM commit remains intentionally unpinned until the hook-capability audit.
- No GPU result, runtime patch, or performance claim is created by this plan.
