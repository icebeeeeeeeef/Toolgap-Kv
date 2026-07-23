# Ticket 1 研究报告：研发基线与唯一口径

> 对应议题：[锁定项目研发基线与唯一口径](https://github.com/icebeeeeeeeef/Toolgap-Kv/issues/3)
>
> 研究日期：2026-07-18
>
> Claim state：除下文明确指出已经 `shipped` 的引擎无关 Phase 0 合同外，
> 本报告均为 `roadmap`。报告仅完成源码审查；不提升任何 vLLM 集成、
> 生命周期 Runtime、GPU 结果或性能结果的 claim state。

## 供评审的结论

ToolGap-KV 已具备进入 **Gate A Week 1 源码审计** 的规划材料，但没有证据
表明 Gate A 已通过，也没有证据表明 candidate-owned Runtime 已存在。正式研发
起点应冻结为：

1. 保持 CT1 集成 -> CT2 正确性/恢复 -> CT3 性能边界这一无条件主线；CT4 仍须
   等待 Gate B 后才可启动；
2. candidate-owned、进程内的 lifecycle controller 是必选交付物；vLLM 的物理
   KV 平面继续复用；
3. 以 **vLLM `v0.25.1`，commit
   `752a3a504485790a2e8491cacbb35c137339ad34`** 作为第一个可复现的*审计候选*，
   而不是使用会持续变化的 `main` 分支；
4. Gate A 只使用一个确定性的“单次 tool call / tool result / 恢复生成”工作负载；
   `Qwen/Qwen3-4B` 仅为候选模型，必须在记录 Hub revision 与 tokenizer 工件后
   才能成为模型 pin；
5. 由 Gate A 的源码 capability matrix 决定精确 adapter 或最小 patch。**不能**
   预先把原生 KV connector 定性成 ToolGap-KV 的 Runtime。

这里有一个关键的时序修正：Week 1 capability matrix、源码级 fault seam 与精确
patch 边界都是 **Gate A 的交付物**，不是进入 Gate A 的前置条件。若在进入前就
要求它们完成，Gate A 会成为循环论证。进入条件只应包含冻结的范围、provenance
候选和一套能在租用 GPU 前证伪项目的证据协议。

## 当前已正式存在的事实

| 关注点 | 权威文档/工件 | 当前事实 | 允许的表述 |
| --- | --- | --- | --- |
| 领域语言与所有权 | [`CONTEXT.md`](../../CONTEXT.md) | 定义了 authoritative token state、lifecycle claim、controller 所有权、物理平面所有权和四种 claim state。 | Runtime 语义仍是 `roadmap`。 |
| Phase 0 实现 | [`docs/agent-kv/README.md`](../agent-kv/README.md) 与本地测试 | 已声明 7 个领域合同测试和 3 个仓库校验测试；尚无 vLLM 代码或测量。 | 仅引擎无关的 scaffolding 为 `shipped`。 |
| 项目阶段与停止分支 | [`docs/agent-kv/ROADMAP.md`](../agent-kv/ROADMAP.md) | CT1-CT3 无条件推进；Gate A 是两周证伪冲刺；CT4 为条件分支。 | `roadmap`。 |
| 首个可执行证据协议 | [`experiments/0001-mechanism-feasibility`](../../experiments/0001-mechanism-feasibility/README.md) | Schema-v0 规定 retain/gpu-hit、offload/CPU-restore 与 recompute/recompute，但尚无 runner。 | `roadmap`。 |
| 规划跟踪器 | [ToolGap-KV：从 Phase 0 到 Resume Release 的研发基线](https://github.com/icebeeeeeeeef/Toolgap-Kv/issues/2) | Map 将本票定义为首个决策。 | 仅规划。 |
| vLLM 候选 | 本地完整 checkout：`/private/tmp/toolgap-kv-vllm-v0.25.1` | release tag `v0.25.1` 解析为 `752a3a504485790a2e8491cacbb35c137339ad34`。 | 已审计的候选，**尚非**已集成依赖。 |
| Tool-call 工作负载候选 | [Qwen3-4B model card](https://huggingface.co/Qwen/Qwen3-4B/raw/main/README.md) | 模型卡描述了支持 tool/agent 的 4B causal model 与 non-thinking mode；可变的 `main` 不能作为 provenance pin。 | 仅候选。 |

还存在一项仓库卫生前置要求：以上文档目前位于 dirty worktree。首次代码改动或
GPU 运行前，应提交一个有意冻结的 baseline commit，包含经评审的权威文档集合
（或等价地记录它们的 commit hash manifest）。不能以一组未命名的未提交设计文件
复现 Runtime trace。这是 provenance 要求，不意味着应提交任何无关的既有修改。

## 从第一性原理审查上游接缝

问题不在于上游能否复制 KV block——它可以。问题在于这个物理机制是否提供了
ToolGap-KV 必须自有的*逻辑 agent 生命周期*。源码表明二者属于不同层次。

### vLLM `v0.25.1` 已经拥有、且应继续由上游拥有的能力

- 官方 offloading 指南表明，`OffloadingConnector` 可将已完成的 KV block offload
  到 CPU（及可选的更低层），按需将命中内容恢复到 GPU，并使用异步 GPU/CPU DMA。
  它暴露 CPU 容量、block size、eviction policy 和按请求设置的
  `max_offload_tokens` 控制。
  [指南](https://github.com/vllm-project/vllm/blob/v0.25.1/docs/features/kv_offloading_usage.md)
- `KVConnectorBase_V1` 明确是 scheduler/worker 间的 KV transfer API。文档化职责
  包含 matched-token 查找、分配状态更新、worker output、request completion、
  异步 send/receive 与 transfer 可见性；该 API 还显式声明为 experimental、将来可能
  变更。本地审计位置：固定 commit 的
  `vllm/distributed/kv_transfer/kv_connector/v1/base.py` 第 4-38、190-200、542-561 行。
- Scheduler 会在异步 load 无 forward progress 期间预留 block，将 request 置为
  `WAITING_FOR_REMOTE_KVS`，并从 worker 接收 `finished_recving` /
  `invalid_block_ids`。它可以将失效的已加载 block 降级为 recompute，并在 transfer
  未完成时延后物理释放。本地审计位置：
  `vllm/v1/core/sched/scheduler.py` 第 895-955、1526-1534、2084-2115、2485-2521 行；
  `vllm/v1/request.py` 第 323-340 行。

这些恰恰是 ToolGap-KV 应复用的物理数据面原语：block 分配/reference 处理、
异步 D2H/H2D、fault signal 和安全的物理 cleanup。重写它们会形成 broad fork，
也不会增强项目的自有工程主张。

### 源码尚未证明的能力

被审计 connector 的生命周期单位是 vLLM `Request` 与 remote-KV transfer；它没有
证明存在一个公开的逻辑对象，能够：

- 在应用层发出 tool call 后有意进入 idle；
- 将随后新建的 resume request 关联回 `(session, turn, lifecycle epoch)`；
- 将迟到的 tool result 拦截在被替换/取消的 agent turn 之外；
- 在该逻辑 claim 上选择 retain/offload/recompute；
- 证明绕过 candidate 代码会改变生命周期行为，而不只是少打一条日志。

这个缺口尚不足以证明必须 core patch；它只说明最小、可维护的 integration seam
**尚未被证明**。同时它排除了一个过早的设计错误：继承 `KVConnectorBase_V1` 后就
称其为 candidate-owned Runtime，只是在给上游 transfer ownership 改名。其
experimental 状态会令这种捷径尤其脆弱。

源码确实提供了有价值的 Gate A fault 候选：异步 load completion、失效 loaded block，
以及在 block 延迟释放期间的 cancellation。但项目必须先证明 lifecycle epoch 如何
关联到这些真实对象；在此之前，它们只是经源码审计的候选，而不是完成的 fault injector。

## Hugging Face 审查：最小的真实 tool gap

Hugging Face 的 tool-use 文档清楚界定了应用边界：模型请求 tool call，但不执行工具；
应用必须执行 handler，追加 assistant 的 `tool_calls` 消息与 `role: tool` result，
然后再次生成。[Tool-use 指南](https://huggingface.co/docs/transformers/main/chat_extras)
这就是 ToolGap-KV 最小且可辩护的工作负载形态：

```text
生成，直到得到一次 tool call
  -> 持久化 canonical conversation/token 工件
  -> 外部 handler 等待一个可控时长
  -> 追加精确的 tool result
  -> 恢复生成
```

Gate A 只用一个 tool。并行多 tool call 会在项目尚未证明单一 lifecycle epoch 前，
额外引入 tool-call ID、排序与部分结果语义。需要保存 tool schema、assistant tool-call
payload、tool-result payload、rendered chat-template token ID、tokenizer revision 和
model revision。tool result 必须是 canonical message history 中的字符串；精确模板
由模型决定。

`Qwen/Qwen3-4B` 是合理的*候选*：模型卡声明其具有 tool/agent 能力、4B 参数规模，
并可通过 `enable_thinking=False` 关闭 thought content。对 conformance workload 应明确
关闭 thinking，避免变化的 reasoning trace 意外改变恢复前缀。模型卡也表明它有自身的
template 行为，但不会替我们锁定 Hub revision。因此，首次 GPU run 前的 manifest 必须
解析到具体的 Hub commit/SHA，并快照 tokenizer/template。
[模型卡](https://huggingface.co/Qwen/Qwen3-4B/raw/main/README.md)

Hugging Face 证据只能验证应用的 message protocol，不能证明 vLLM KV residency、
transfer completion、cache hit accounting 或任何 latency 结果。

## Gate A 入口合同与 Gate A 交付物的分界

| 进入 Gate A 前 | Gate A Week 1 中 | Week 2 / Gate A 通过时 |
| --- | --- | --- |
| 冻结范围、ownership boundary、claim vocabulary 与 CT1->CT3 顺序。 | 针对候选 tag 建立 capability matrix，并判定 supported seam 或 missing contract。 | 运行最小 candidate-owned vertical slice，并采集至少两条可独立归因的真实路径。 |
| 将 release candidate、model candidate 与 baseline 文档的 commit/hash 记录为候选 provenance。 | 解析真实 request completion、tool wait/resume entry、lifecycle identity mapping、forced action、block ownership、load/store visibility、cancellation 和 default-path bypass。 | 产出固定 build/patch/environment/command、requested->observed trace、output oracle、fault/fallback fixture 和已关闭的 evidence card。 |
| 冻结单工具确定性工作负载语义及要持久化的工件。 | 定义 controller 自有的一次真实 transition 或 fallback，并定义 removal/bypass test。 | 仅此时允许将被实际运行的 integration 标为 `shipped`；不要求 speedup claim。 |

项目在完成中间列前**不应**租用 GPU；也**不能**将一次成功源码阅读视为 Gate A 通过：
通过要求真实 trace、candidate-owned 行为变化和 fault path。

## 保留的预算与阶段顺序

即使上游已有 offload connector，规划预算仍然成立，不应压缩：

| 工作 | 规划投入 |
| --- | ---: |
| Gate A 源码审计与 controller vertical slice | 30-45 小时 |
| Runtime、vLLM adapter 与 executor orchestration | 70-110 小时 |
| Workload/replay、benchmark runner 与 CT3 runs | 70-105 小时 |
| Gate B0、可复现性与面试包装 | 30-60 小时 |
| 核心 CT1-CT3 加 Gate B0 | 220-320 小时 / 11-16 周 |
| Gate B 后的 CT4 | 额外 40-70 小时 / 2-4 周 |

阶段顺序因此为：

```text
冻结 baseline
  -> Gate A Week 1 源码矩阵
  -> Gate A Week 2 三路径 / fault 证据
  -> CT1 自有 lifecycle runtime
  -> CT2 正确性与恢复
  -> CT3 性能边界与全局代价核算
  -> Gate B0 公平 static comparator
  -> Resume Release
  -> 仅在 Gate B 后可选的 CT4
```

## 明确的非结论与停止条件

- 本研究没有产生实际 vLLM integration、Runtime、GPU test、性能结果、模拟结果或
  简历 bullet。
- 研究时的 vLLM `main` 为 `c233d90aa826df072872df47b201450059be8e71`；它是会移动的
  development line，不是选择的 baseline。
- `v0.25.1` 是可审计的起始候选，不是其 extension seam 满足项目 ownership requirement
  的证据。
- 若源码矩阵发现只有 broad scheduler 或 physical-KV fork 才能表达 lifecycle semantics，
  则按既有 Gate A 分支停止/收窄；不能用 connector wrapper 掩盖该不匹配。
- 若 retain 需要这种 broad fork，可从即时实现中移除 retain，保留 offload/recompute
  作为被评估主线；若无法拥有非重复的 lifecycle semantic，则 ToolGap-KV 不再作为
  招聘 Runtime 主线继续推进。

## 复现锚点

```bash
git clone --depth 1 --branch v0.25.1 https://github.com/vllm-project/vllm.git /private/tmp/toolgap-kv-vllm-v0.25.1
git -C /private/tmp/toolgap-kv-vllm-v0.25.1 rev-parse HEAD
# expected: 752a3a504485790a2e8491cacbb35c137339ad34
```

本报告查阅的一手来源：

- [vLLM v0.25.1 源码树](https://github.com/vllm-project/vllm/tree/v0.25.1)
- [vLLM v0.25.1 KV offloading 指南](https://github.com/vllm-project/vllm/blob/v0.25.1/docs/features/kv_offloading_usage.md)
- [vLLM v0.25.1 KVConnector V1 接口](https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/distributed/kv_transfer/kv_connector/v1/base.py)
- [vLLM v0.25.1 scheduler](https://github.com/vllm-project/vllm/blob/v0.25.1/vllm/v1/core/sched/scheduler.py)
- [Hugging Face Transformers tool-use 指南](https://huggingface.co/docs/transformers/main/chat_extras)
- [Qwen3-4B 模型卡](https://huggingface.co/Qwen/Qwen3-4B/raw/main/README.md)
