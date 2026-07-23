# 外层 KV 控制与推理引擎策略冲突：一手资料调查

> 调查日期：2026-07-19
> 用途：回答 ToolGapController 对请求级 KV 意图的表达，是否会与 vLLM 的
> scheduler、prefix cache、offload 和异步执行相冲突，以及其他系统怎样处理。
> 证据状态：`roadmap`。本文是公开一手源码、RFC、issue 与架构文档的调查；不代表
> ToolGap-KV 已实现这些接口，也不代表其在本项目单 GPU testbed 上已通过实验。

## 结论先行

**会冲突；不能让外层 controller 直接拥有或修改引擎的物理 KV 状态。**

公开系统的共同模式不是“外层策略替代 engine policy”，而是：

```text
外层控制面
  -> 发送带身份和约束的 request intent
  -> 引擎在自己的 scheduler / block / transfer 契约内接受、降级或拒绝
  -> 引擎发布实际结果和事件
  -> 控制面只按实际结果推进自己的逻辑状态
```

这个模式同时满足两件事：外层掌握 agent/workflow 才知道的语义，引擎继续掌握
共享 block、资源压力、异步完成和正常请求的正确性。

## 调查问题与范围

本调查不比较论文性能数字，只研究下列问题：

1. 外部 orchestrator/router/cache layer 是否向 engine 提供 KV 策略？
2. 当该策略与物理 cache、异步完成或并行 scheduler 相遇时，谁拥有最终仲裁权？
3. 已出现的错误或设计如何约束 ToolGap-KV？

来源仅限项目维护方的 GitHub 源码、RFC、issue、release 与架构文档。Hugging Face
未发现比这些项目自有资料更直接的接口/冲突语义，故不将 HF 模型卡或二手集成说明作为
结论依据。

## 一手证据

| 系统与证据状态 | 外层能表达什么 | 如何避免与 engine 打架 | 对 ToolGap-KV 的意义 |
|---|---|---|---|
| [vLLM Context-Aware KV-Cache Retention RFC #37003](https://github.com/vllm-project/vllm/issues/37003)（`roadmap`，公开 RFC，尚非本项目 pinned version 的能力） | orchestrator 在 request 上附 token-range 的 priority/duration 和可选 scope | engine 保留 block eviction 执行权；未标注的 block 继续原 LRU；RFC 明确提出“orchestrator defines policy, vLLM executes it” | 最接近本项目的目标分层：Controller 发送 intent，不直接碰 block；普通请求必须无额外语义/成本 |
| [vLLM KV offloading RFC #19854](https://github.com/vllm-project/vllm/issues/19854)（历史设计，描述已形成的 connector 方向） | connector 发起 store/load 及其 metadata | 为使外层数据面可与 scheduler 正确协作，设计要求 worker→scheduler metadata、request block hashes、以及 connector KV events | 不能用 driver 的本地推测代替 engine 事实；Controller 需要可关联的 outcome/event，而不是仅记录“请求过 offload” |
| [vLLM 的 LMCache connector 源码](https://github.com/vllm-project/vllm/blob/main/vllm/distributed/kv_transfer/kv_connector/v1/lmcache_connector.py)（`shipped` upstream code，版本须单独 pin） | connector 集成 LMCache 的 layerwise load/store 与 KV event | 多 worker 的 KV event 先聚合、仅保留 common events；layerwise async synchronization 无法被 CUDA graph 捕获时，connector 要求 piecewise mode | 外层 KV 路径可能改变 engine 的执行模式/开销；必须把 compatibility mode 与其成本列为 manifest 和 CT3 变量 |
| [SGLang PP + HiCache consistency plan #22607](https://github.com/sgl-project/sglang/issues/22607)（高优先级修复计划，非 ToolGap-KV 证据） | L3 external storage prefetch、write-through/load-back | 异步 prefetch 完成与 wall-clock LRU 会让不同 PP rank 的 host tree 分叉，已出现 shape-mismatch crash；方案用跨 rank 的 progress 归约和 leader 决策来同步可见性 | 最强反例：不能让一个 completion 到达后立即、局部地改变共享 cache 可见性；ToolGapController 的旧 epoch completion 只能记 trace/清理，不能直接恢复新 turn |
| [NVIDIA Dynamo architecture](https://github.com/ai-dynamo/dynamo/blob/main/docs/design-docs/architecture.md) 与 [semantic KV metadata backport release note](https://github.com/ai-dynamo/dynamo/releases)（架构/发布事实，不是 ToolGap-KV baseline） | router 基于 KV overlap、load 和 events 做 worker 选择 | 存储事件面负责 state visibility；KVBM 负责 reuse/eviction/offload/recall；当 pinned vLLM 缺少 routing 所需 semantic event metadata 时，Dynamo backport 一个局部 upstream patch | 控制面可消费 KV events，但不应自行宣称 residency；若缺失的是一个精确 metadata contract，窄 patch 有正当性，不能据此重写 scheduler |

### 1. vLLM RFC：外层提供 hint，engine 执行物理策略

RFC #37003 的关键不是其 priority 算法，而是职责划分：agent orchestrator 知道 session
和 token range 的未来价值，vLLM 知道 block pool 的真实压力与 eviction。它把前者表达为
`RetentionDirective`，把后者保留在 engine 内；无 directive 的 block 保持既有 LRU。

这支持下列原则，但要注意 RFC 仍为 `roadmap`，不能作为 v0.25.1 已有 API：

```text
hint/request != force
unannotated/default path must remain native
engine-owned eviction must not be reimplemented in the orchestrator
```

### 2. vLLM connector / LMCache：异步外层路径会改变 engine 的执行约束

vLLM 的 offloading 设计显式需要 worker 向 scheduler 回传 metadata，并需要 KV events
来让外部组件看到 cache insertion/deletion。LMCache connector 更具体地显示了两条约束：

- 多 worker event 不能各自当作全局事实，connector 通过 aggregator 仅保留 common
  events；
- layerwise load/store 的异步同步无法进入 CUDA graph，因而要求 piecewise CUDA graph
  mode。

这不是“集成插件天然无损”的证据，反而说明集成会改变可用优化与性能边界。ToolGap-KV
不能只报告 cache hit；还必须测普通请求以及 active-request 的 queue/TTFT/尾延迟。

### 3. SGLang HiCache：局部异步 completion 直接改共享状态会造成正确性故障

SGLang 的 PP + L3 HiCache 计划记录了一个具体失效链：不同 pipeline rank 的 external
prefetch 先后完成，分别改变本地 host tree；随后 prefix match、LRU victim、host pressure
继续分叉，最终出现 shape mismatch crash。其方案不是让每个 prefetch thread 独自重试，
而是对 progress/完成度做跨 rank 同步，并把部分 scheduler 决策统一由 leader 下发。

该场景比 ToolGap-KV 的单 GPU Gate A 更复杂，不能照搬通信实现；但其不变量可直接复用：

```text
异步物理 completion 不自动等价于逻辑 lifecycle completion。
只有经过 identity/epoch/visibility 检查的 completion 才能影响 resume。
```

### 4. Dynamo：控制面消费事实，数据面执行物理决策

Dynamo 将 request plane、control plane、storage/events plane 分开：router 用 KV overlap 和
load 做选择；KV Events 传播可见性；KVBM 执行 block reuse、eviction、offload/recall。
其 release note 还记录了一个合理的局部 backport：因为 pinned vLLM 缺少 hybrid model 的
semantic cache-group metadata，Dynamo backport 上游 event-metadata patch 供 router 索引。

这个例子给出的 patch 标准是：**补一个被上层安全消费的事实字段**，而不是让 router
接管 vLLM block manager。

## 对 ToolGap-KV 的设计约束

### A. 将 controller 的输出改称为“请求意图”

Controller 不应说“把我的 KV 驱逐/搬到 CPU”，而应提交以下最小 envelope：

```text
{ lifecycle_id, epoch, requested_action, compatibility identity }
```

其中 `requested_action` 是 `retain`、`offload` 或 `recompute` 的受控测试请求；它不是
对 vLLM block/refcount 的命令。Gate A 的固定版本 adapter 只能在其支持的 seam 内执行或
降级。

### B. adapter 必须把实际结果回传给 controller

Gate A 的 DecisionTrace 至少应有：

```text
requested_action
observed_action = gpu_hit | cpu_restore | recompute | rejected
fallback_reason
lifecycle_id + epoch
engine request id
cache/transfer provenance available at the pinned seam
```

Controller 只在 `epoch` 有效、结果与允许 fallback 相容时推进状态。尤其是旧 completion
只能被标为 stale 并清理；不能触发新 turn 的 resume。

### C. 默认路径隔离是正确性条件，不是性能优化

```text
request has no toolgap envelope
  -> adapter delegates stock vLLM behavior
  -> no controller action, no lifecycle-state mutation
```

Gate A 必须验证 Controller enable/disable 下普通请求的输出与可用路径指标。若 connector
要求改变 CUDA graph 或全局 offload 配置，必须记录为测试环境变化；该实验不可以声称
“普通路径零影响”。

### D. Gate A 与 CT3 的边界

| 阶段 | 可以回答 | 不能回答 |
|---|---|---|
| Gate A 单工具、串行、quiescent fixture | metadata 能否让受控 request 走可归因路径；controller removal 后该行为是否消失；故障是否显式 fallback | controller 策略会否提升全局吞吐；是否挤压 active batch；多 agent 是否安全共享 HBM |
| CT3 压力实验 | 受控 store/load/recompute 对 active request、带宽、queue、p95/p99 的影响；一个负收益区 | 生产普适最优或动态策略优势，除非 Gate B 另行通过 |

## 推荐的新增验证项

在既有 Gate A 规格中保留下列条目：

1. **ordinary-path isolation**：无 envelope 的普通 request 在 Controller on/off 下输出
   等价；记录 cache/transfer 相关指标，不将“未观测到差异”误写成零开销。
2. **requested-to-observed matrix**：每个受控 fixture 都记录请求动作、实际路径和允许
   fallback；没有理由的差异即失败。
3. **controller bypass**：移除 envelope 或 bypass Controller 后，受控路径消失；否则
   Controller 只是 trace observer。
4. **stale completion**：旧 epoch 的 store/load completion 不得恢复新 resume；必须有
   trace 和确定性测试。
5. **CT3 interference test**：至少一个 active decode/HBM pressure 负载，分别报告
   resumed request 与 active request 的 queue、store/restore、prefill、first token 和
   p95/p99；明确一个 controller action 反而更差的区域。

## 对 patch 决策的影响

本调查不要求现在改 vLLM。只有在 unmodified-vLLM failing test 表明缺少下列之一时，
才考虑窄 patch：

```text
1. 可关联到 engine request 的 outcome / semantic cache metadata；或
2. request-scoped、不会破坏共享 block 所有权的 cache lookup/admission contract。
```

“让 vLLM 原生理解完整 agent workflow/tool orchestration”不是窄 patch。若它是唯一
可行路径，则应收窄为 offload/recompute conformance，或拒绝该 vLLM 版本作为项目主线。

## 可用于面试的结论

> 外层 controller 不和 engine 争夺 block ownership。它利用 agent 语义提交带 epoch 的
> action intent；engine 在资源与共享-cache 约束下执行、降级或拒绝，并回传实际路径。
> 我用 requested/observed/fallback trace 和普通路径隔离证明该分层没有把策略愿望伪装成
> 物理事实；性能冲突留给压力实验量化，而不是在设计阶段假定不存在。
