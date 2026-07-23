# Serving / KV Cache 前沿项目方向：从 45 篇文章到可证伪项目

> **历史研究输入，不是现行路线图。** 2026-07-13 的后续项目裁决已由
> [`docs/agent-kv/DECISIONS.md`](../agent-kv/DECISIONS.md) 取代本文的组合推荐：
> ToolGap-KV 是唯一当前秋招主线；Agent KV Regime Lab 只作为其 workload
> harness；NIXL fencing 不是自动备选，只有独立的未修改-vLLM safety failing
> test 才能触发重新评审；其余候选当前不投入。保留本文用于线索、反例和
> 历史决策审计，不按本文末尾建议执行。

> 日期：2026-07-13（Asia/Shanghai）
> 范围：只讨论 AI Infra 推理团队中的 Serving、KV Cache、控制面与数据面；不把 kernel、算子、编译器或推理引擎核心实现作为主项目。
> 证据状态：本文分别使用 `roadmap`、`shipped`、`experimentally validated`、`simulated`，不把上游 PR、论文实验和本地实现混为一谈。

## 结论先行

如果只选一个高上限的探索，我推荐先做一个 **10 个工作日的可证伪 spike**，而不是直接承诺完整项目：

**NIXL KV Handoff Fencing & Conformance：验证 P/D handoff 在 duplicate、stale、reordered completion 与 crash 下是否需要 per-handoff epoch、去重 quorum 和双边 terminal ledger。**

这里必须先承认 prior art：vLLM NIXL 已经实现 source lease、heartbeat、completion/expiry reclaim、compatibility hash，以及“接收完成后才恢复调度”；SGLang KV-Canary 已实现真实 KV byte 校验和 corruption fault injection。因此下面这些不能再被包装成新贡献：

- “首次为 P/D 加 lease”；
- “首次做 compatibility manifest”；
- “首次校验真实 KV bytes”；
- “首次对 KV 做 fault injection”。

仍值得验证的窄缺口来自当前 NIXL completion 语义：producer 侧按通知计数等待 heterogeneous-TP consumer 完成，但公开实现中没有明显的 per-handoff epoch、显式 sender identity set 或 deduplicated quorum。duplicate/stale ack 是否可能造成提前释放或 ABA，需要在目标 commit 上先复现，不能在复现前声称是 bug。

这个项目的主故事不是“我让吞吐提高了多少”，而是：

> 我针对一个真实 connector 的 handoff completion 协议做了对抗验证；如果 stale/duplicate/ABA 安全缺口成立，我用 epoch-fenced structured ack、唯一 consumer quorum 和双边资源账本修复并证明它；如果缺口不成立，我公开负结果并终止机制创新主张。

这比再做一个 cache-aware router 或 L2 cache clone 更窄，也更诚实。它是一个**条件性推荐**：先过复现门，再立项。

## 阅读结果与证据边界

- 45/45 个微信链接均已取得正文；其中 1 篇初次触发微信验证页，切换移动端访问后成功取得。
- 全部文章来自 `Miracle Farms`，发布时间覆盖 2026-05-11 至 2026-07-13。
- 文章不是 45 个独立方向。大量日报复述同一批上游变化；如果按链接数量投票，会系统性高估热门主题。
- 因此本文先逐篇建证据卡，再按“独立机制”去重，最后回到论文、官方文档、release、Issue/PR 验证。
- 微信文章负责提供线索和解释，不作为“上游已实现”的最终证据。详细逐篇账本见同目录的 `2026-07-13-wechat-ai-infra-article-ledger.md`。

## 第一性原理筛选器

一个适合你的项目，不应该从“最近什么最热”出发，而应同时满足以下约束：

1. **目标岗位拥有这个问题。** Serving/KV 团队会维护它；不是 CUDA/kernel/compiler 团队的主责。
2. **存在清晰的缺失契约。** 不是把成熟项目缩小重写，而是上游接口、评测或失败语义仍有空白。
3. **结果可证伪。** 要能定义错误率、SLO attainment、recovery time、orphan bytes、重算率或仿真误差，而不只展示架构图。
4. **可以分阶段建立证据。** 先 `simulated`，再接真实公开 extension point 得到 `experimentally validated`；没有 GPU 结果时不声称性能完成。
5. **个人可完成核心闭环。** 不能把 RDMA 集群、异构 GPU 或修改多个引擎核心当作 Phase 0 前提。
6. **面试时能深入追问。** 至少能讨论 state machine、ownership、backpressure、failure recovery、consistency、metrics 与 trade-off。
7. **最小侵入。** 优先 connector、event API、gateway/EPP、sidecar 或 replay adapter；只有证明缺少契约后才考虑小型可审计 core patch。

## 45 篇文章去重后的七条主线

### 1. KV 正从本地内存优化升为分布式基础设施

文章反复出现 LMCache P2P/多节点、Mooncake Store HA/tenant quota/tiered scheduling、NIXL telemetry、vLLM 对象存储 offload、Ray KV-aware routing。共同变化不是“缓存更大”，而是 KV 开始拥有：

- 独立地址空间；
- 跨实例位置与 tier；
- metadata HA；
- tenant quota；
- event/index；
- lifecycle 与 consistency 问题。

上游证据包括 [LMCache v0.5.0](https://github.com/LMCache/LMCache/releases/tag/v0.5.0)、[Mooncake event-driven tiered scheduler](https://github.com/kvcache-ai/Mooncake/pull/2550)、[Mooncake strict multi-tenant quota](https://github.com/kvcache-ai/Mooncake/pull/2612) 和 [Ray 2.56.0](https://github.com/ray-project/ray/releases/tag/ray-2.56.0)。这些属于上游 `shipped`，不代表本地项目已实现。

**项目含义：** 再做一个简单的 GPU→CPU→disk cache 已不新；真正的空白转向一致性、治理、事件契约与故障恢复。

### 2. KV handoff 的一级问题从带宽变成语义边界

异构 P/D 文章给出了最重要的新抽象：`Runtime KV State` 不只是 K/V tensor，还包括 model/adapter identity、token range、position state、layout、precision、partition、residency、capacity reservation 和 ownership。

[异构推理设计空间论文](https://arxiv.org/abs/2606.29708)把差异分成两类：

- hard gate：model、adapter、token range、position state、runtime schema 不兼容时，必须 reroute 或 recompute；
- transformable differences：layout、partitioning、numerical representation 可通过显式 transformation plan 处理。

文章还引用 [vLLM NIXL lease renewal](https://github.com/vllm-project/vllm/blob/d272418f459a82e1012b60116ac00659a7017cde/docs/design/nixl_kv_cache_lease.md)：decode 排队期间通过 heartbeat 延长 source KV lease；decode crash 后停止续约，使 source 可以提前回收。

正确性验证也已进入引擎内部：[SGLang KV-Canary core PR #26808](https://github.com/sgl-project/sglang/pull/26808)、[fault injection PR #26816](https://github.com/sgl-project/sglang/pull/26816) 和 [真实 KV byte verification PR #26817](https://github.com/sgl-project/sglang/pull/26817) 均已 merged。这证明 KV correctness 不是虚构需求；同时也划出本项目的差异边界——不复制 attention forward 内的 canary，而是验证跨 worker handoff 的 manifest、ownership、commit 与 recovery。

**项目含义：** “传输成功但解释错误”是比网络报错更危险的 failure；这正是 KV boundary contract 的立项依据。

### 3. KV transfer 开始承接 deadline 与 QoS

Mooncake TENT 已不只是静态 data mover。官方 [TENT overview](https://github.com/kvcache-ai/Mooncake/blob/main/docs/source/design/tent/overview.md)明确描述动态 transport selection、slice spraying、telemetry 和 partial failure handling。

2026-07 的最新变化更关键：

- [deadline-aware RFC #2519](https://github.com/kvcache-ai/Mooncake/issues/2519)仍为 open；
- [EDF dispatch PR #2763](https://github.com/kvcache-ai/Mooncake/pull/2763)已 merged；
- [deadline-infeasible drop PR #2764](https://github.com/kvcache-ai/Mooncake/pull/2764)已 merged。

但 PR #2764 明确把真实 bandwidth provider 接线，以及 vLLM/SGLang 的 local-decode 行为留在 scope 外。也就是说，policy core 是 `shipped`，端到端 serving 闭环仍是 `roadmap`。

**项目含义：** 可做的不是复制 EDF，而是研究 serving scheduler 与 transfer admission 之间谁拥有 deadline、如何估算 laxity、何时 transfer/compress/recompute。

### 4. Agentic workload 使 cache value 与 recency 脱钩

Agent 文章共同描述了 WORM、多轮高前缀重叠、tool wait、subagent termination、reasoning block 和 compaction 后废弃状态。传统 LRU 看“最近访问”，但系统真正需要看“未来是否仍有生命周期价值”。

NVIDIA 官方文章 [Full-Stack Optimizations for Agentic Inference with NVIDIA Dynamo](https://developer.nvidia.com/blog/full-stack-optimizations-for-agentic-inference-with-nvidia-dynamo/)把这个信息断层落为 `nvext.agent_hints`，并明确称它是仍在演进的 v1 API。文章公开讨论 priority、TTL/token ranges、session tagging、ephemeral KV 和 workflow-aware prefetch。

这也不是一块无人区。[InferCept](https://arxiv.org/abs/2402.01869) 已研究 tool/API interception 期间的 preserve/swap/discard/recompute，[Continuum](https://arxiv.org/abs/2511.02230) 已做 tool-duration-aware TTL，[Astraea](https://arxiv.org/abs/2512.14142) 已做 I/O-wait 与 memory-pressure-aware 生命周期调度，[KVFlow](https://arxiv.org/abs/2507.07400) 和 [PBKV](https://arxiv.org/abs/2605.06472) 已覆盖 workflow-aware eviction/prefetch 及 future-reuse prediction。因此“让 tool-wait cache 活久一点”“动态 TTL”或“workflow-aware prefetch”都不能作为新机制首创；推荐项目必须落在真实 connector 的 handoff fencing 与 failure conformance，而不是重复这些策略。

**项目含义：** harness-to-serving contract 是前沿，但不能自封“标准”。个人项目应先证明哪些 hint 对 workload 有稳定价值，再讨论协议。

### 5. Agentic benchmark 仍缺公共负载与统一退化指标

综述文章中的十篇 2026 论文没有使用统一 trace。暴露出的现象包括：

- middle-phase thrashing；
- tool wait 导致活跃性与 cache value 脱钩；
- KV 命中率上升反而让 storage NIC 先饱和；
- workflow SLO 与单调用 TTFT/TPOT 失焦；
- failure agent 比 success agent 消耗更多轮次与上下文。

可参考 [CONCUR](https://arxiv.org/abs/2601.22705)、[DualPath](https://arxiv.org/abs/2602.21548)、[HexAGenT](https://arxiv.org/abs/2605.16637) 和 [Agentic AI Workload Characteristics](https://arxiv.org/abs/2605.26297)。论文结果属于各自条件下的 `experimentally validated`，不能直接外推为通用收益。

**项目含义：** 一个公开、可重放、能生成 thrashing/tool-wait/fan-out/failure 的 trace harness，本身有项目价值，但必须连接至少一个真实 serving backend，否则容易停留在数据生成器。

### 6. 多级 KV 的竞争从策略转向调度、粒度与仿真

HiSim、CacheFlow、ContiguousKV、KVDrive 分别揭示：

- 配置搜索需要离散事件仿真；
- cache recovery 可联合 compute 与 I/O 调度；
- token selection 和 block I/O 的粒度错配会制造读放大；
- 多层存储的价值取决于 working set 相对 HBM 的相变点。

其中 [Tair HiSim 官方博客](https://www.alibabacloud.com/blog/alibaba-cloud-tair-kvcache-simulation-analysis-high-precision-computational-and-caching-simulation-design-and-implementation_603164)给出高保真仿真的方法论，但文章指出整体开源状态与跨引擎保真度仍不清楚。

**项目含义：** cross-engine simulator 是可行保底方向；但必须用真实 engine trace 校准，否则只是“用模型证明自己的模型”。

### 7. 一批热点应作为知识储备，而不是主项目

- unified block pool、MHA/MLA/Mamba cache layout：更接近 engine core；
- KV pruning、sparse attention、INT2/INT4 role-aware quantization：需要模型质量与 kernel 路径；
- CXL、RDMA multi-rail、scale-up fabric、ZCube topology：依赖昂贵硬件；
- speculative decoding scheduler、CUDA graph、draft weight hot update：进入 engine scheduler/runtime；
- 再做一个普通 cache-aware router：Ray、Dynamo、llm-d、SGLang Gateway、AIBrix 已很拥挤。

这些内容适合做源码阅读、实验 baseline 或面试追问，不适合作为个人主项目的差异化核心。

## 候选项目排名

评分 1–5；总分不是客观真理。第一项的“缺口”尚待复现，所以不把它和已经确定的工程问题混为一谈。

| 类型 | 方向 | 岗位贴合 | 缺口/差异化 | 个人可做 | 可测量 | 风险 |
|---|---|---:|---:|---:|---:|---|
| 高上限探索 | NIXL per-handoff fencing + conformance | 5 | 5（若可复现） | 3 | 5 | 缺口可能不存在 |
| 稳健方向 | KV State Ledger：事件滞后、reconciliation、false-locality | 5 | 4 | 4 | 5 | 容易退化成 router wrapper |
| 稳健方向 | Agent KV Regime Lab：真实 trace、容量相变、负收益区 | 5 | 4 | 5 | 5 | simulator 必须校准 |
| 稳健方向 | Deadline-aware transfer-vs-recompute controller | 5 | 5 | 3 | 5 | 网络与估计误差较高 |
| 次选方向 | Harness–Serving Contract + conformance | 5 | 4 | 4 | 5 | 容易自创无采用协议 |

## 推荐探索的精确定义

### 不做什么

- 不重新设计通用 `RuntimeKVStateManifest`；NIXL 已有 deployment compatibility hash 和 runtime validation。
- 不重新发明 source lease/heartbeat/reclaim；[vLLM PR #41383](https://github.com/vllm-project/vllm/pull/41383)及其 [lease design](https://github.com/vllm-project/vllm/blob/main/docs/design/nixl_kv_cache_lease.md) 已覆盖。
- 不做全量 KV checksum；SGLang KV-Canary 已覆盖真实字节验证。
- 不首期同时接 vLLM、SGLang、LMCache、Mooncake；只 pin 一条 vLLM NIXL 路径。

### 候选缺口

当前公开 NIXL completion notification 使用 request 标识和 world size，producer 侧等待足够通知后释放 source blocks。需要验证：

```text
duplicate completion
stale completion from a previous handoff
retry reusing a logical request id
reordered heartbeat and completion
heterogeneous TP partial completion
```

是否可能让“通知计数达到阈值”早于“唯一 consumer 集合真正完成”。这是一个候选 ABA/去重问题，不是已确认漏洞。

若缺口成立，最小机制是 versioned structured ack：

```text
HandoffAck {
  handoff_id
  epoch
  state_version
  consumer_rank
  manifest_hash
  terminal_status
}

producer release condition:
  unique(consumer_rank) == expected_consumer_set
  AND epoch/state_version match current handoff
  OR lease expires
```

producer 与 consumer 同时输出可关联的 terminal ledger，证明一个 handoff 只有一个安全终态，并能对 source pinned bytes 与 destination reserved bytes 做双边核账。

### 最小真实集成点

- pin 到含 vLLM PR #41383 的 commit；
- 只做 `1P + 1D`，优先利用 NIXL TCP fallback，不把 RDMA 当 Phase 0 前提；
- 复用 `KVConnectorBase_V1` 的 scheduler/worker seam；
- patch 控制在 NIXL `metadata.py`、`pull_worker.py`，必要时加 `pull_scheduler.py` 与 tests；
- 若必须大改 scheduler/attention hot path 才能阻止 KV 暴露，先证明缺少 hook，再决定是否提交一个极小 upstream seam，不能直接 core fork。

### 首批 fault matrix

1. duplicate completion；
2. stale epoch completion；
3. heartbeat/completion 乱序；
4. decode 在 local reservation 后、commit 前 crash；
5. manifest hash mismatch；
6. retry 与旧 handoff 同时到达。

核心不变量：

- first decode token 前完成 fencing/validation；
- producer 不因重复或旧 ack 提前释放；
- 一个 handoff 只有一个 terminal outcome；
- lease deadline 加容差后 source pinned bytes 与 destination reserved bytes 均归零，或进入显式安全 recompute。

### 10 个工作日 kill gate

- **K0 prior-art kill：** 若目标版本已有 per-handoff epoch、deduplicated consumer quorum、pre-consume validation 和双边 terminal ledger，撤销新机制主张，只保留 upstream conformance tests。
- **K1 reproduction kill：** 10 个工作日内无法在未修改 vLLM 上复现至少一个安全相关 gap，终止 protocol novelty；timeout 或性能下降不能冒充 safety gap。
- **K2 seam kill：** fencing 需要 attention/scheduler 大改、长期 core fork，或无法控制在 connector 层三个生产文件内，终止当前方案。
- **K3 admission kill：** 无法证明 validator 位于 `finished_recving` 与恢复调度之间，即 first decode token 之前，不能声称 `unsafe_consume_total=0`。
- **K4 differentiation kill：** 实验只重复验证现有 lease timeout 或 Canary corruption 时，项目降级为 `KV transfer conformance suite`。
- **K5 evidence kill：** 四周仍无真实 `1P + 1D` connector artifact，只能标 `simulated`，停止扩展 cross-engine 与更多 fault。

### 成立后的证据路线

Phase 0（10 个工作日）：源码/测试审计、未修改版本 fault reproduction、负结果或最小 failing test。此时仍是 `roadmap`/`simulated`，不能说 bug 已证实。

Phase 1（两周）：structured ack + epoch fencing + unique-rank quorum + terminal ledger；跑 duplicate/stale/reorder/crash 测试。只有真实 connector test 通过后才标 `experimentally validated`。

Phase 2（两周）：小规模 serving workload，报告无故障 p95 TTFT overhead、fault 下 premature free/orphan bytes/recompute outcome。metadata gate 的 overhead 若大于 `max(2%, 1ms)`，或引入全量 KV hash 成为 hot-path 主成本，则实现失败。

## 四个更稳健的备选方向

### 备选 A：KV State Ledger + Reconciliation

消费 vLLM KVEvents/connector metrics，维护 prefix/block 的 location、tier、owner 与 last-observed epoch，重点做：

- event loss、duplicate、reorder 和 process restart；
- request-history inferred locality 与 precise event index 的偏差；
- reconciliation、event lag、false-locality rate；
- 每次 routing/admission 的 DecisionTrace。

硬停止线：如果它只包了一层现有 router，不能比 request-history baseline 更准确地解释位置与错误路由，就不成立。

### 备选 B：Agent KV Regime Lab

用真实 agent trace 重放 tool wait、fan-out、failure/retry、compaction 与 working-set 相变，扫描 HBM/DRAM/NVMe、concurrency 和 tier policy，输出 TTFT/TPOT/JCT、cache hit、extra prefill、NIC 与 migration cost surface。

必须校准至少一个真实 engine/backend；如果 simulator 跨 workload 的误差无法稳定进入可用区间，就明确降级为 comparative replay benchmark，不能声称容量预测器。

### 备选 C：Agentic Serving Hint Gateway + Trace Benchmark

做一个 OpenAI-compatible gateway，把 harness 已知但 engine 看不见的事实转成结构化 hint：

- session / branch / subagent id；
- interactive vs background priority；
- expected output length；
- tool-wait ETA；
- persistent/ephemeral token ranges；
- retention TTL；
- compaction / subagent termination 事件。

后端 adapter 可以对接 Dynamo `nvext.agent_hints`、GAIE EPP metadata 或自定义 replay backend。

必须先做 benchmark，再做协议。止损条件：如果只能定义漂亮 schema，却无法证明至少两个 hint 在真实/仿真 workload 上改善 cache retention 或 workflow SLO，就不要把它包装成“标准”。

### 备选 D：Deadline-aware Transfer-vs-Recompute Controller

做 serving scheduler 与 transfer layer 之间的 cross-layer controller：

```text
TTFT budget
  -> queue/prefill estimate
  -> transfer deadline
  -> bandwidth/laxity estimate
  -> transfer / reorder / drop / local recompute
```

Phase 0 用 trace-driven simulator 对比 FIFO、priority、EDF、least-laxity 和 recompute fallback；Phase 1 再对接 Mooncake TENT。项目价值不在重写已 merged 的 EDF，而在补齐上层 deadline 生成、真实 bandwidth bridge、误判成本和端到端 SLO 闭环。

硬件风险较高，所以排在主推荐之后。

## 明确不建议作为新的主项目

1. **从零实现 LMCache/Mooncake。** 规模失控，最后只能做缩水 clone。
2. **再做一个普通 prefix-aware router。** 市场拥挤，除非拥有新状态或新 SLO 契约，否则只是策略换权重。
3. **把 KV 压缩/稀疏化作为主线。** 没有模型质量评估、kernel 和多模型验证，结论站不住。
4. **CXL/RDMA/scale-up 硬件项目。** 没有稳定硬件实验条件时只能做纸面设计。
5. **speculative decoding scheduler。** 已进入 engine scheduler、CUDA graph 和 model-specific path，不符合“不要深入引擎组”的边界。
6. **纯 simulator。** 如果四周内无法用真实引擎校准，必须停止扩功能；否则会变成自洽但不可验证的模型。

## 最终判断

这批文章给出的最新方向不是一个新的 cache 算法，而是 KV Cache 的系统身份发生了变化：

```text
tensor buffer
  -> engine-local block
  -> cross-instance cache object
  -> distributed state with location, quota and HA
  -> versioned boundary object with owner, deadline and recovery
```

最后一跳也不是无人区：lease、compatibility hash、KV-Canary、deadline admission、event index 和 harness hints 都已有实现。真正可能留下的创新通常窄到一个 connector protocol invariant，而不是一套宏大的新 KV 架构。

所以最值得先做的是 **10 天 falsification spike**：验证 NIXL handoff 是否真的缺 per-handoff epoch 与去重 quorum。成立就做最小 fencing patch；不成立就记录负结果并转向 KV State Ledger、Agent KV Regime Lab 或 deadline controller。这个止损机制本身，比一开始宣布“我要做统一 KV 生命周期平台”更符合项目构建的第一性原理。
