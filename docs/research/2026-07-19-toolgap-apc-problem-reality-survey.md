# ToolGap 是否仍是现实问题：APC、原生 Offload 与项目动机复核

> 调查日期：2026-07-19
> Claim state：`roadmap`。本文是源码/官方文档调研与待执行实验设计；不声称 ToolGap-KV 已完成 vLLM 集成、GPU 运行或性能验证。
> 决策用途：在继续实现 ToolGapController 前，判断「tool gap 导致的 KV 恢复」是否仍有可寻址的问题空间，以及项目应对哪个基线负责。

## 结论先行

**Tool gap 是真实的工作负载形态，但不自动等于一个尚未被当前 vLLM 解决的性能问题。**

对一个标准的工具调用回合，应用必须在模型输出 tool call 后执行外部工具，并将
assistant tool-call 消息和 tool result 追加到历史，再发起后续生成。这确实会形成一个
新的推理请求，而非同一 request 内的原生暂停/恢复。[Hugging Face tool-use
guide](https://huggingface.co/docs/transformers/main/chat_extras) 对该应用协议有直接说明。

但 vLLM 的 Automatic Prefix Caching（APC）会对新请求的相同 token 前缀查找并复用
完整 KV block；固定的 `v0.25.1` V1 配置默认启用 APC。因此，在 GPU 没有压力、历史重渲染
后 token 前缀保持一致的场景，**stock vLLM 已经会自动承担大部分 tool-return resume 的
prefill 复用**。这时「让 tool gap 的 KV 不丢」不是一个可归因于 ToolGapController 的问题。

问题只在下列交集里成立：

```text
工具调用后确有后续 resume
  ∧ resume 前的历史能重现足够长的相同 token prefix
  ∧ 该 prefix 在 resume 前已被 GPU APC 驱逐，或 GPU tier 无法容纳它
  ∧ native CPU offload / 默认 LRU 不能以同等或更低全局代价处理该 miss
  ∧ 生命周期语义驱动的动作能改善这一结果，而不是只记录它
```

这不是「APC 使项目失效」的结论；它把项目动机收窄为：

> **在有 HBM 竞争的 tool-using agent workload 中，验证 stock APC 与 native offload
> 何时已足够；仅在它们不足时，验证一个候选拥有的 lifecycle runtime 能否以不接管
> vLLM 物理 KV 数据面的方式，安全地表达并归因生命周期相关动作及其全局代价。**

在得到真实比较前，不应把项目表述为“解决 tool gap 的 KV 丢失”，更不能假设
`retain` 是可强制的物理保证。

## 0. RFC #37003 是路线分流证据，不是背景脚注

[RFC #37003](https://github.com/vllm-project/vllm/issues/37003) 的核心不是“再做一个
cache policy”，而是给 orchestrator 一个 engine-owned retention priority/duration
contract，由 scheduler 仲裁共享 block 的最终去留。这是本项目路线 C（窄引擎契约）的
上游版本；它**不是**把完整 agent tool-wait/resume orchestration 放入 vLLM 的 broad
route B。

因此正确的项目叙事是条件性的：

> 上游正在探索 scheduler 级 retention intent。ToolGap-KV 先验证，应用内、引擎外的
> lifecycle layer 能否借现有 request-scoped seam 对支持的 offload/recompute 情形表达
> 足够的 intent、保持 lifecycle correctness，并不需要 broad fork。若它足够，说明对该
> pinned workload 无需等待或改写 engine；若它不够，精确的 failing test 则是 RFC 式窄
> retention API 的动机证据，而不是扩张为 agent scheduler fork 的理由。

这里“足够”不能预设为“与 RFC retention priority 等价”：当前 pinned seam 若没有该
priority contract，ToolGap-KV 只能诚实地报告此缺口。

## 1. Gate A0.1：token round trip 是第一道存在性闸

工具调用的最小应用流程是：

```text
history H
  -> 请求 R0，模型生成 assistant tool_call
  -> 应用执行外部工具（tool gap）
  -> H' = H + assistant tool_call + tool result
  -> 新请求 R1，模型继续生成
```

Hugging Face 的官方示例明确要求应用处理 tool call，并将它作为 `assistant` 消息、将结果
作为 `tool` 消息追加后再生成。[官方指南](https://huggingface.co/docs/transformers/main/chat_extras)
这证明 tool gap 在应用层存在；它**没有**证明某种 KV 驻留策略更快。

对于 R1，`H + assistant tool_call` 是 R0 已处理 token 序列的候选前缀。因此若以下条件均成立，
APC 可直接跳过这段的 prefill：

1. R1 的聊天模板、tokenizer、模型/KV layout、tool schema 与 cache-isolation 参数保持兼容；
2. 历史的重新序列化产生与 R0 相同的 token IDs；
3. 该段落到完整 block 边界，且 block 尚在 APC 中。

vLLM 官方 APC 设计说明：block hash 同时依赖父前缀 hash、该 block 的 token IDs 以及
LoRA、多模态输入或 cache salt 等 extra hashes；它只缓存完整 block。
[官方设计文档](https://docs.vllm.ai/en/stable/design/prefix_caching/)

这不是众多观测指标之一，而是 ToolGap-KV 的第一道存在性闸。必须比较 R0 的实际处理
token 序列与 R1 rendered history 中、第一枚 tool-result token 之前的 token 序列：

- 若最长共同前缀覆盖 canonical assistant tool-call 的最后一个可复用完整 block，APC
  复用问题才有意义；
- 若它在 tool-call 序列化附近普遍提前截断，问题是 canonical serialization / template /
  parser compatibility，lifecycle runtime 无法让不相同的 KV 变为可复用 KV。应停止或
  重新选择为 serialization 项目，不能把它包装成 eviction 优化。

只有这个 gate 通过后，才记录 **`cached_prefix_tokens / resume_prompt_tokens`** 来衡量 APC：

- 不完整尾 block 不会被 APC 复用；
- 即便整个 prompt 命中，vLLM 仍须为 logits 重算最后一个 token，且 block 对齐可能导致
  重算多于一个 token；
- 若 tool-call 输出被 parser/canonical-history/chat-template 重新序列化为不同 token，
  APC 的可复用前缀会在第一个差异处截断。

这些判断来自“hash 依赖 exact token IDs”的工程推论，不是本项目已测事实；必须把
R0 的 token IDs 与 R1 的最长共同 token prefix 写入 raw evidence。

## 2. 为什么 APC 仍不等于 agent-aware retention

APC 的缓存对象是全局、内容寻址的完整 block，不是 agent session。

固定 `v0.25.1` 源码中，完成请求会释放其 block；引用数归零的、有 hash 的 block 会回到
free queue，成为未来分配时可驱逐的候选。新请求命中时才会被 `touch`、提高 refcount 并从
free queue 移除。见 [KVCacheManager](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/vllm/v1/core/kv_cache_manager.py#L206-L244)、
[BlockPool](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/vllm/v1/core/block_pool.py#L43-L50)
和 [free/touch 路径](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/vllm/v1/core/block_pool.py#L600-L635)。

由此得到两件同时为真的事：

- **低压力时**：已完成 request 的相同完整前缀通常仍可作为 APC 候选；ToolGapController
  不应声称自己创造了这次复用。
- **竞争时**：工具等待中的 session 没有活动 request 引用，APC 不知道它“很可能很快回来”或
  “重算代价很大”。它可以被全局 LRU 回收。此时才存在 lifecycle metadata 可能有价值的缺口。

vLLM 的 [Context-Aware KV-Cache Retention API RFC #37003](https://github.com/vllm-project/vllm/issues/37003)
正是为让 orchestration 层传递 token-range priority/duration 而提出，并把 agentic 工具等待下的
false eviction 作为动机。它仍是 **Open RFC**，不是已合入 API，也不是对本项目目标硬件/工作负载的
性能证明；其中引用的百分比和论文结果不能当作 ToolGap-KV 的实验结论。

## 3. 原生 offload 再次缩小了缺口

当前官方 [KV Offloading Usage Guide](https://docs.vllm.ai/en/latest/features/kv_offloading_usage/)
将 `OffloadingConnector` 定义为对 prefix cache 的扩展：完成的 KV block 可以复制到 CPU tier，
下层命中后按需恢复到 GPU。它还提供 experimental 的请求级
`kv_transfer_params.max_offload_tokens`，以限制某个请求可 offload 的前缀范围。

**术语陷阱：swap 不等于 offload connector。** 固定 `v0.25.1` 的文档写明，V1 不再使用
V0 中“request 因 preemption 而 swap 到 CPU”的 `--swap-space` 路径。
[固定版本 metrics 说明](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/docs/design/metrics.md#L511-L514)
这不否定独立的 KVConnector/OffloadingConnector CPU store/load tier；S1 使用的是后者，
绝不能在报告或面试中称为 preemption swap。

固定 `v0.25.1` 的源码审计也已确认 CPU store/load、异步完成和 load failure -> recompute/fail 的
物理路径存在，但没有 tool-call wait、tool-result continuation、`session/turn/epoch` 等逻辑语义。
[固定版本审计](2026-07-18-vllm-v0.25.1-gate-a-source-audit.md)

所以必须比较三类基线，而不是把“全重算”当作唯一 stock 对手：

| 配置 | 回答的问题 | 不是何物 |
| --- | --- | --- |
| S0：stock APC，关闭 KV offload | APC 单独已复用多少 resume prefix，压力何时导致 GPU miss | 不应被称为“无缓存” |
| S1：stock APC + native CPU offload | 原生下层是否已足以承接 GPU miss，以及代价 | 不含 ToolGap 生命周期决策 |
| T：ToolGap lifecycle runtime + 允许的薄 wrapper | 仅生命周期 metadata/动作是否使结果或安全性产生可观测差异 | 不能接管 block/refcount/驱逐/DMA |

一个 APC-off 的实验可作为机制 sanity check，但不是实际系统的公平基线。若 S1 与 T 的结果相同，
则不能把原生 offload 已提供的收益归因给 ToolGapController。

## 4. 对项目动机的纠正

旧的、过强表述是：

> Tool gap 会让 KV 丢失；因此需要一个 Controller 决定 retain/offload/recompute。

推荐采用的可证伪表述是：

> Tool-result 恢复会以新 request 重新进入 vLLM。APC 可复用精确且仍驻留的完整前缀，native
> offload 可为部分 GPU miss 提供 CPU tier。项目要先刻画这些默认机制在 agent tool-gap 和
> HBM 竞争下的有效边界；只有存在默认机制不能处理、且生命周期语义能安全改变结果的区域，
> 才构建/保留 candidate-owned lifecycle runtime。

这保留了一个真实的工程问题：**全局内容缓存不知道 logical agent lifecycle**。但它拒绝两个没有
证据的承诺：

1. 每个 tool gap 都需要控制器；
2. Controller 可以保证某个 session 的 KV 驻留在 HBM。

项目的 candidate-owned 价值也应相应收窄：它拥有 identity、epoch、合法 transition、异步完成
fencing、fallback、cancel/cleanup 和 `requested -> observed -> fallback` 归因；vLLM 仍拥有物理
block residency、refcount、eviction、scheduler 与 D2H/H2D。这与 [CONTEXT.md](../../CONTEXT.md)
的现有 ownership 边界一致。

## 5. 必须先做的 Gate A0：问题存在性实验

这一步在任何 Controller/runtime 实现之前运行，且全部使用 pin 后的 unmodified vLLM。

### Gate A0.1：先过 token round-trip，才允许测 eviction

- 保存 R0 实际 processed token IDs、R1 rendered token IDs、tool schema、assistant
  tool-call payload、tool result、tokenizer/template/model revision 与 cache salt。
- 仅比较到 R1 的第一枚 tool-result token 之前；检查最长共同前缀是否覆盖 assistant
  tool-call 的最后一个可复用完整 block。
- 不通过时立即停止/重选 ToolGap-KV runtime：这不是低 hit rate，也不是 Controller 的
  fallback 场景。

### Gate A0.2：预注册 stock-adequacy 假设，而不是 fishing expedition

主假设不是“总能找到 T 赢的点”，而是：在预注册的 target pressure band 中，stock APC
的可复用前缀会低于 token-round-trip 所给出的上限，且 S1 的 CPU transfer/recompute
代价与 S0 可区分。T 不参加这一步，因此这个假设不预设 ToolGap 会赢。

在第一条 S0/S1 比较 trace 前，manifest 必须冻结：

```text
M = active_unique_KV_bytes / usable_HBM_bytes
M 的 low / target / overload bands
L 的全部 prefix-length points，G 的全部 tool-gap points
background arrival/concurrency、CPU-tier capacity、repetitions
primary metrics、continue/stop interpretation
```

数值可由一次不观察 S0/S1 胜负的容量/bytes-per-token calibration 得出；一旦比较开始，
不得移动 band 或挑选事后好看的 cell。当前尚未 pin 模型、硬件和 capacity，故此刻虚构具体
阈值会违反 preregistration；冻结数值是 Gate A0 的首个可审查产物。

### 工作负载与控制变量

- 单工具调用，串行 canonical history；保存 R0、R1 的 rendered prompt token IDs 与模型、tokenizer、
  chat-template、tool schema、cache salt 等 provenance。
- 扫描 `L`（恢复前稳定前缀/KV 大小）、`G`（tool gap）、`P`（背景并发/HBM pressure）。
- 对每个 `(L, G, P)` 运行 S0 与 S1；保持模型、GPU memory budget、并发/arrival、CPU tier 容量和
  sampling 参数一致。需要 APC-off 仅作为校验，不作为胜负比较对象。

### 每个 resume 的必要记录

```text
最长共同 token prefix、resume prompt tokens、cached tokens、recomputed tokens
GPU APC hit/miss 及可获得的 eviction/block 证据
CPU store/load bytes 与 transfer time（S1）
resume queue delay、prefill time、resume TTFT
active-request queue delay、TTFT/P99、throughput 或 Goodput
输出正确性 oracle 与运行 provenance
```

不能仅由端到端时间猜测 `gpu_hit`、`cpu_restore` 或 `recompute`；必须使用引擎事件、token accounting
和 transfer evidence 归因。

### 结果如何裁决项目

| Gate A0 结果 | 正确决策 |
| --- | --- |
| S0 在声明的目标压力下已高比例复用 prefix，S1 无额外价值，且 active workload 未受害 | 当前 workload 中没有可寻址的 ToolGap-KV 优化问题；不继续把它包装成“解决 KV 丢失”的 runtime 项目。 |
| GPU miss 会发生，但 S1 已在公平配置下与任何 T 方案等价 | 原生 APC+offload 已覆盖收益；T 最多做生命周期可观测性/正确性实验，不得宣称性能优化。 |
| 存在可重复区间：S0 miss，S1 受限，而 T 以明确的 request-scoped intent 获得更低 resume 成本且不伤害 active requests | ToolGap 具有现实工程问题空间；进入 CT1/CT2/CT3，且收益必须只对该区间和环境表述。 |
| 想获得收益必须接管 block manager、refcount、全局 eviction 或 scheduler | 外置 runtime 主线不成立；要么以一个具体 failing test 证明并评估窄 patch，要么停止/换题，不能把 broad fork 伪装成适配层。 |

## 6. 本次调研的最终判断

**现实性：有条件成立，尚未被本项目证实。**

APC 不能被忽略：它默认开启、恰好匹配 tool-return 中“旧历史是新历史前缀”的结构，并且会让低压力
场景的项目收益趋近于零。原生 offload 又可能覆盖一部分压力场景。

但 APC/offload 也不具备 agent session、tool wait、future resume、epoch 或 session-level priority
的语义；在高竞争和长上下文时，默认 LRU 是否做出错误的逐出选择是一个合理但尚未测量的假设。上游
仍在以 RFC 讨论该接口，说明缺口具有工程相关性，而非已经有稳定原生解。

故下一项不是实现状态机，也不是改写 vLLM，而是 Gate A0。它应先决定：这个项目是

```text
真实的 lifecycle-aware KV control gap
    或
stock APC/offload 已足够的负结果与项目收窄/停止依据。
```

两种结果都比预设“tool gap 必然需要一套 KV runtime”更诚实。

## 一手来源

- [vLLM Automatic Prefix Caching design](https://docs.vllm.ai/en/stable/design/prefix_caching/)（当前官方机制说明；只用来说明 APC 语义，不替代固定版本实验）
- [vLLM v0.25.1 CacheConfig](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/vllm/config/cache.py#L91-L95)（固定基线默认 APC）
- [vLLM v0.25.1 KVCacheManager](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/vllm/v1/core/kv_cache_manager.py#L206-L244) 与 [BlockPool](https://github.com/vllm-project/vllm/blob/752a3a504485790a2e8491cacbb35c137339ad34/vllm/v1/core/block_pool.py#L600-L635)（固定基线的 lookup/free/touch 语义）
- [vLLM KV Offloading Usage Guide](https://docs.vllm.ai/en/latest/features/kv_offloading_usage/)（当前官方 offload 行为和 experimental per-request cap）
- [vLLM RFC #37003](https://github.com/vllm-project/vllm/issues/37003)（上游问题定义与拟议 API；Open RFC，不是完成能力）
- [Hugging Face Tool use guide](https://huggingface.co/docs/transformers/main/chat_extras)（工具调用/追加历史的应用协议）
