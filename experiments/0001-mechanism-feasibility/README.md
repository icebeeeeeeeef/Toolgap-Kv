# Experiment 0001: Mechanism Feasibility

## 当前执行入口

本目录的两个前置实验 harness 顺序不可颠倒：

1. [A0.1 token round-trip 规格](A0.1-token-roundtrip-spec.md)：实现真实 R0/R1 采集、
   reproducibility preflight、冻结的 span adapter 与不可变 artifact；只有 `pass` 才能继续。
2. [A0.2 stock-sufficiency 规格](A0.2-stock-sufficiency-spec.md)：在 A0.1 的实际 pass
   artifact 上实现 stock S0/S1 workload、calibration 与 observability preflight。

### 2026-07-22 A0.1 执行记录

[A0.1 结论](A0.1-results-2026-07-22.md)已在真实 A10 GPU、固定 vLLM commit 和 Qwen
revision 上完成。最终 v2 artifact 为 `serialization_stop`：tool-call semantic span 的 token
逐 ID 相等，但其末端未被可复用的完整 16-token block 覆盖。因此 A0.2 没有启动，A1
controller 也没有获得继续权限。原始 bundle 本地保存在 `raw/a0.1/`（被 Git 忽略），结论
文档保存哈希、命令、环境和范围。

本 README 其余内容描述的是**后续 A1** 的 forced-path / candidate-owned runtime contract。
在 A0.1、A0.2 都给出 Continue verdict 前，不得以它为由开发 ToolGapController、custom
offload wrapper、fault injection 或 forced-path runner。A0.2 的 Stop / Inconclusive 都会终止
或缩窄 A1，而不是把 A1 实现当作默认下一步。

## Question

Can one pinned vLLM build reliably and observably produce these three paths for
the same model, prompt shape, block configuration, HBM budget, and server flags?

1. `gpu_hit`: prefix blocks remain resident and the resume request hits GPU KV.
2. `cpu_restore`: D2H store completes, GPU KV is unavailable, and resume performs
   a CPU hit followed by H2D restore.
3. `recompute`: both GPU and CPU copies are unavailable and resume performs full
   prefill.

These files are the schema-v0 nominal input and evidence contract for two-week
Gate A. A0.1 now has a narrow real-GPU negative applicability result; it still
does not validate an A1 mechanism, attribution, or a performance improvement.

This is **Gate A1**, not the earlier applicability decision. Before these forced
fixtures or any ToolGapController code, Gate A0 must pass two checks: (1) the
canonical tool-call history round-trips to a sufficiently long exact R0/R1 token
prefix; (2) stock APC and stock APC plus native CPU offload leave a preregistered
candidate-addressable recovery gap. A token mismatch is a serialization/
compatibility branch, and stock sufficiency is a stop/narrow branch; neither may
be relabeled as a successful forced cache path.

Gate A must execute these cases through a minimal candidate-owned, in-process
lifecycle-controller vertical slice. A hook that only observes vLLM-owned
behavior cannot pass even if its traces are accurate. The controller may reuse
vLLM's physical block/refcount, eviction, and D2H/H2D implementations.

## Current contract-readiness gap

The shipped engine-independent `DecisionTrace` validates token accounting but
does not yet enforce every legal fallback. Schema v0 intentionally freezes only
the three nominal conformance pairs:

```text
retain -> gpu_hit
offload -> cpu_restore
recompute -> recompute
```

Do not express a fallback by changing one of those expected pairs. The Week 1
capability audit must identify the real failure seam and allowed outcome, then
add a separate fault/fallback fixture plus validation before the Week 2 run. In
runtime traces, `requested != observed` remains legal only with a non-empty,
source-audited fallback reason and evidence of the path actually taken. The exact
allowed reasons must not be invented before the source audit.

Schema version 0 uses `queue_timing` as an evidence obligation, not as a claim
that a suitable vLLM timestamp already exists. The capability audit must resolve
it to concrete enqueue/dispatch timestamps or record why the seam is not
observable. An unavailable-reason artifact preserves a negative result, but it
does not satisfy the Gate A pass condition that queue time be separable.

## Before renting a GPU

Complete every Week 1 capability item in
[ROADMAP.md](../../docs/agent-kv/ROADMAP.md), including a vLLM hook-capability
matrix that answers:

- how tool-wait and tool-result/resume enter the runtime;
- how a forced nominal action is expressed for conformance testing;
- how session, turn, and lifecycle epoch correlate when resume is a new request;
- how ordinary requests bypass the candidate-owned control path;
- where request completion releases block references;
- whether CPU store is proactive or eviction-triggered;
- how a new request triggers CPU load;
- which event proves asynchronous store/restore completion;
- whether a CPU copy can remain while the GPU entry is invalidated;
- whether both tiers can be invalidated to force recomputation;
- how session, turn, and lifecycle epoch map to real block outcomes.
- which real transition or fallback the candidate controller owns and how
  ordinary requests bypass it;
- which behavior disappears when that controller is removed or bypassed.

Only after these are answered should `manifest.json` receive an exact vLLM
commit and patch hash.

## Inputs

- `../../configs/phase0.json`: frozen experiment defaults.
- `manifest.json`: provenance and pinning state.
- `workload.json`: deterministic action cases and required observations.

The current cases are hand-authored mechanism probes, not replayed agent traffic.
They contain no injected tool-gap or arrival distribution and cannot support a
production-workload or scheduler-representativeness claim. CT3 workload
provenance is added separately under the rules in
[EVALUATION.md](../../docs/agent-kv/EVALUATION.md).

## Outputs

Future runs write immutable artifacts below `raw/`, which is ignored except for
its directory marker. A completed run must also record an environment manifest,
launch command, per-run DecisionTrace, output token hash, and variance summary.

## Pass gate

- every schema-v0 nominal run follows its exact requested-to-observed pair;
- a separate source-audited fault/fallback fixture exists and every disagreement
  names an allowed fallback and proves its actual path;
- the exercised fault cannot silently reuse failed materialization and ends in
  explicit recompute or failure;
- CPU restore proves GPU miss plus CPU hit;
- recompute proves GPU miss plus CPU miss;
- token accounting is complete;
- greedy output has no unexplained difference;
- queue, transfer, prefill, and first-token timing are separable;
- the required engine change is maintainable and auditable.
- at least one lifecycle transition or fallback is enforced by candidate-owned
  in-process code, and a removal/bypass test distinguishes behavior from logging;
- one integration alternative is rejected with source or trace evidence;
- the first decision card links the exact patch, trace, command, and validity boundary.
