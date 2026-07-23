# Agent KV / Tool-Call 相关开源工作的可复用性调查

> 调查日期：2026-07-18
> 用途：判断 ToolGap-KV 是否能复用外部项目的结论，从而删减 Gate A 的无效重复工作。
> 证据状态：`roadmap`。本文不将第三方 README、论文结果或上游测试表述为本项目已完成的集成、正确性或性能验证。

## 结论先行

**可以复用实现素材和部分“上游机制存在”的结论；不能复用为 ToolGap-KV 的 Gate A 通过证据。**

最接近的公开项目是 Continuum 的作者仓库 `Hanchenli/vllm-continuum`：它明确是一个
带 Continuum scheduling 的**修改版 vLLM**，可选 LMCache CPU offload，并使用
mini-SWE-agent/SWE-bench workload。它证明“agent tool-gap + KV retain/offload”不是
空想，也能提供 workload 和对照实验的起点；但它不是对本项目固定
`v0.25.1` commit、单 GPU 环境、外置非 fork controller 的证明。

因此，不应重复做已经完成的源码 capability audit，也不应从零写 CPU store/load。
但仍须做一个很小的 local vertical slice，回答候选人自己的唯一问题：

> 在固定 vLLM commit 上，外置 ToolGapController + custom offload wrapper 是否真的能改变
> 一个受控 resume 的行为，并在 controller 被移除时消失？

这不是外部论文、fork 或 README 可以代替的证据。

## 调查范围和方法

- 优先阅读项目所有者的 GitHub 源码仓库、vLLM 官方文档/issue；不以第三方解读作为
  接缝存在的依据。
- 对每项外部工作分别判断：能否复用代码、测试/工作负载、机制结论，及其是否能关闭
  ToolGap-KV 的 Gate A 条件。
- Hugging Face 检索只找到 vLLM 的托管/集成说明，没有找到一个可审计的
  tool-gap lifecycle runtime 实现；因此不把 HF 文档列为 Gate A 依赖。

## 候选工作与边界

| 工作 | 一手证据 | 可复用内容 | 不能复用为本项目结论的原因 |
|---|---|---|---|
| **Continuum preview code** | README 自称为 modified vLLM，提供 `--scheduling-policy continuum`、可选 LMCache CPU offload、mini-SWE-agent/SWE-bench 评测；默认示例为 4 H100。 [仓库](https://github.com/Hanchenli/vllm-continuum) | agent workload 形状、baseline/continuum 对照命令、tool-gap 是真实问题的先验、CPU offload 接入经验。 | 它是 fork，不是 ToolGap-KV 固定 commit 上的小外置 extension；README 自己称 preview code、无 release；其 4 H100 + LMCache 结果不能证明单 GPU、vLLM native offload、controller ownership 或故障语义。 |
| **vLLM 原生 KV offload** | 官方 v0.25 文档支持请求级 `kv_transfer_params.max_offload_tokens`，并明确标注 experimental。 [官方文档](https://docs.vllm.ai/en/v0.25.0/features/kv_offloading_usage/) | 不再自己实现 D2H/H2D、CPU tier、基础 load/store；可直接把官方 per-request selective-offload 用例改成受控 resume fixture。 | “参数存在”不证明 tool return 的 identity/epoch、controller 对行为的 ownership、default-path isolation，且 experimental 接口必须锁定 commit。 |
| **vLLM context-aware retention RFC #37003** | RFC 明确指出 tool-call pause 导致 false eviction，并提出 orchestrator 提供 token-range priority/duration。 [RFC](https://github.com/vllm-project/vllm/issues/37003) | 问题定义、反对 hard pin 的原则、未来 retention API 的评价口径。 | 这是 open RFC/提案，不是已合入的稳定 API；不能据此跳过 source audit 或声称当前 tag 可按 session retain。 |
| **LMCache agent traces** | 官方仓库包含 RepoAgent、mini-SWE-agent、Aider 等 agent trace，并说明可收集/分析 agent trace。 [仓库](https://github.com/LMCache/lmcache-agent-trace) | 后续 CT3 的真实工作负载输入、tool-gap/多轮 prefix 形状、trace 解析脚本思路。 | 它不含 ToolGapController，也不证明任何 vLLM version/connector 的 path attribution；Gate A 的机制 conformance 应先用更小的确定性单工具 fixture。 |
| **NVIDIA Dynamo KVBM** | KVBM 是跨 GPU/host/SSD/remote 的统一 block-memory 层，用 connector 将 vLLM 操作映射到自己的 block lifecycle。 [设计说明](https://github.com/ai-dynamo/dynamo/blob/main/docs/components/kvbm/README.md) | 数据面与控制面分层的反例/边界：可借鉴 event vocabulary，不必重建物理数据面。 | 它拥有独立分布式 KV block manager，范围远大于 ToolGap-KV；接入会把 Gate A 变成多系统集成，掩盖 vLLM native seam 的结论。 |

## 能删减什么，不能删减什么

### 可以删减

1. **不重新发明 CPU offload。** 固定版本的源码审计已经确认应委托 vLLM
   `OffloadingConnector`/CPU tier；只写一个薄 wrapper。
2. **不从大规模 agent benchmark 开始。** Gate A 直接采用上游 CPU restore/recompute
   integration-test 的强制 reset 思路，先在单工具串行 fixture 上证明路径。
3. **不先实现 retention/prediction。** Continuum 和 RFC 都说明该问题有 prior art；
   retain 只保留为共享-prefix `gpu_hit` conformance case，不做 session pin。
4. **不先接 LMCache、Mooncake 或 Dynamo。** 它们是可选的后续数据面依赖，不是验证
   current-vLLM extension seam 的前置条件。

### 仍不能跳过

| 必须保留的验证 | 外部工作为何不能代替 | 最小本地证据 |
|---|---|---|
| fixed-commit 启动与环境 manifest | fork/README 不等于当前 commit 可在目标硬件、模型、PyTorch/CUDA 上运行。 | 一条普通 request 的启动命令和 manifest。 |
| controller-owned transition | 外部项目可能是 fork 内 scheduler policy；本项目要求外置 controller 拥有行为。 | 开/关 controller 的对照：开时受控 resume 有指定 offload/restore/fallback 行为，关时该行为消失。 |
| CPU restore 与 recompute 归因 | 外部的 connector、缓存层、GPU 数和 reset 语义不同。 | `GPU miss + CPU load` 与 `GPU miss + CPU miss` 的独立 trace，含 load bytes/time 与输出 oracle。 |
| default-path isolation | 自定义 envelope/wrapper 的副作用只能在本项目实现里验证。 | 无 envelope 的请求在启用前后走原生路径、输出正确。 |
| 一条故障/fallback 路径 | 第三方成功 benchmark 不会覆盖本项目的 restore failure、取消或 stale completion。 | 注入 restore failure，结果明确为 recompute 或 failure，且记录原因。 |

## 对 Gate A 的工程决策

推荐把外部工作用作**加速器**，而不是“免验证凭证”：

```text
Continuum / LMCache traces
  -> 后续 workload 与 baseline 素材

vLLM official offload docs + upstream integration tests
  -> Week 2 fixture 的起点

ToolGapController + thin custom wrapper on pinned vLLM
  -> 仍需本地验证的 Gate A 核心
```

若这个最小 vertical slice 失败，外部项目并不能证明本项目可行：它们可能通过 fork、
不同 scheduler、LMCache 或更大规模的数据面绕开了同一个限制。失败时应记录精确缺失
契约，再决定是否允许窄 core patch；不应把整个 Continuum fork 引入本项目。

## 可执行的下一步

以 vLLM upstream CPU offload integration test 的三段 reset 逻辑为骨架，新增一个
ToolGap-KV 单工具串行 harness。先只验证 `cpu_restore` 与 `recompute`，并包含
controller bypass / ordinary request 对照 / restore-failure fixture。该范围足以证伪
当前版本的 extension seam；通过前不引入 Continuum scheduler、LMCache 或分布式 backend。
