# 微信 AI Infra 文章逐篇证据台账：Serving / KV Cache 项目方向

> **历史研究输入，不是现行路线图。** 本文完整保留 45 篇文章提供的线索、
> 候选方向和当时排序，用于审计研究过程；其“最有价值候选”已被后续组合裁决
> 取代。当前只有 ToolGap-KV 是秋招主线，Agent KV Regime Lab 仅作为 workload
> harness，其他候选不投入。以
> [`docs/agent-kv/DECISIONS.md`](../agent-kv/DECISIONS.md) 和
> [`docs/agent-kv/ROADMAP.md`](../agent-kv/ROADMAP.md) 为执行依据。

> 日期：2026-07-13
> 仓库证据状态：`roadmap`（这是外部文章与一手来源研究，不是本仓库的 GPU 实验结果）
> 范围：用户给出的 45 篇公众号文章；定位于 AI Infra 推理团队的 serving、KV cache、调度、数据面与控制面，主动排除以 kernel、算子实现、引擎核心改造为主体的项目。
> 原文覆盖：`45/45 readable`；每篇正文均已离线抽取并阅读。
> 证据纪律：下文“文章称/文章报告”的数字是二手材料转述；除非显式写为“上游 shipped”或“论文 experimentally validated”，不得视为本仓库验证结果。

## 结论先行

这 45 篇文章给出的最强共同信号不是“再做一个 KV 淘汰算法”，而是：**KV cache 正从 engine 内部张量变成 serving 系统的有状态数据面**。随之出现的工程缺口是状态事实表、生命周期/所有权契约、deadline 与 traffic class、故障恢复、租户隔离、可观测性和 workload-regime 校准。

对求职项目而言，最值得做的不是复刻 Mooncake/LMCache，也不是深入 MLA、稀疏 attention 或 CUDA/CuTe kernel，而是在现有 vLLM/SGLang/LMCache/Mooncake extension seam 上做一个能被推理 serving 团队审查的控制面或验证工具。尤其要避开以下重复主张：

- InferCept 已覆盖 tool interception 期间 preserve/swap/discard；Continuum 已覆盖 tool-duration-aware TTL；Astraea 已覆盖 I/O wait + pressure-aware KV 管理。不能再声称“首次对 agent tool gap 动态选择 retain/offload/recompute”。
- vLLM APC、SGLang RadixAttention、TRT-LLM reuse 已覆盖 exact prefix cache；LMCache/Mooncake/HiCache 已覆盖多级或远端 KV。不能把“有一个 L2/L3”当作项目贡献。
- vLLM/SGLang router、AIBrix、Preble 与 llm-d 已覆盖 cache-aware routing。新项目必须证明自己改善了**物理 residency 事实精度、事件滞后、SLO 或故障语义**，而不是只换一个打分公式。

## 最有价值的五个候选主题

| 排名 | 候选项目 | 为什么现在成立 | 最小可交付与硬停止线 |
|---|---|---|---|
| 1 | **KV State Ledger：事件驱动的缓存事实与决策追踪层** | 多篇文章反复指向“谁拥有 KV、它在哪里、何时失效”；llm-d 已证明 KVEvents 路径存在，但 near-real-time index 仍有丢事件、乱序、重启恢复与事实漂移问题。 | 订阅 vLLM KVEvents/connector metrics，维护 per-block/per-prefix 状态机，输出 DecisionTrace、event lag、reconciliation、false-locality rate；若无法比 request-history router 更准确地解释路由结果，则停止。 |
| 2 | **Deadline-aware KV Admission：传输/重算的 SLO 可行性层** | TENT/MFS 表明排序只在可行性过渡区有效；“能搬”不等于“来得及”。这是 serving 调度与数据面之间的窄而真实接口。 | 不改传输 kernel，只实现 laxity/MLU 估计、admit/drop/fallback、traffic class 与 trace replay；必须报告 deadline 松/紧两端的零收益负区域。 |
| 3 | **Agent KV Regime Lab：真实 agent trace 的缓存退化与容量仿真** | 文章显示 84.6–99.5% 的理论跨轮复用可在容量压力下骤降；HiSim 闭源/生态绑定，且合成 benchmark 容易给出反方向结论。 | 公开 trace schema、failure amplification、working-set sweep、HBM/DRAM/NVMe cost surface、tuned static baseline；若 simulator 对目标环境 TTFT/throughput 误差不能稳定进入可用区间，则只保留 replay/benchmark。 |
| 4 | **Harness–Serving Contract：让 agent 显式表达 prefix 与生命周期** | Dynamo 的 agent hints、Claude/Codex 的稳定 prefix、Responses/Anthropic 流事件都说明主要损失常来自 harness 与 serving 的信息断桥。 | 定义 engine-agnostic hints（stable-prefix boundary、session/workflow id、reuse domain、deadline、retention intent）及 vLLM/SGLang adapter；若需要修改 engine core 才能表达，缩成协议与 capability probe。 |
| 5 | **KV Boundary & Correctness Verifier：跨 P/D、tier、格式和租户的契约测试** | 异构 P/D、FP8/FP16、offload、共享池把 silent corruption、stale block、tenant leakage 的风险放大；当前性能 benchmark 多、契约测试少。 | 构造 hash/salt/shape/role/tier/lease/failure matrix，验证 output hash、cache attribution、store/load completion、restart/reconcile；不做量化 kernel，只验证边界。 |

## 逐篇台账（按用户提供顺序）

### 01. [今日焦点：推测解码集体生产化，KV cache 向统一 block 池重构](https://mp.weixin.qq.com/s/X2N-buuH_e-d6Ra9T_HhPg)

- 元数据：Ethan，Miracle Farms，2026-07-13 08:32；状态：`readable`。
- 文章主张/机制/证据：四引擎为推测解码补 CUDA graph、scheduler reserve、fallback 与热更新；KV 内部表示趋向 draft、混合 attention、RL rollout 可共享的统一 block pool。文章举 SGLang draft-extend graph 约占 4.5GB 且配套 kill-switch，说明“默认路径”需要可回退运维能力。
- Serving/KV 判断：统一 block 生命周期、显存核算和回退可观测性高度相关；CUDA graph 和 speculative kernel 本身越过本研究的引擎/算子边界。
- 项目假设：做 **block-pool capability/pressure probe**，比较不同运行特性开启后可用 KV blocks、OOM fallback 与请求级影响，不实现 speculative kernel。主线来源为文章链接的 [vLLM PR #44455](https://github.com/vllm-project/vllm/pull/44455) 与 SGLang PR；PR 状态需 pin commit 再核对。

### 02. [Mooncake TENT 的服务质量三轴：KV 传输从优先级排序走向 deadline 契约](https://mp.weixin.qq.com/s/kykc4vqpQzopvVuCTbLCqQ)

- 元数据：Ethan，Miracle Farms，2026-07-08 22:45；状态：`readable`。
- 文章主张/机制/证据：TENT 将 QoS 从 priority 扩展为顺序、deadline、traffic class；用 MLU/可行性判断 admit 或 drop。文章转述 MFS 的 TTFT SLO 达成率 1.2–2.4×；H20/CX-7 的 1MB sweep 中，500μs 多数可行、100μs 几乎不可行，EDF 只在约 200μs 过渡区有杠杆。
- Serving/KV 判断：这是最贴近 serving control/data-plane seam 的方向；不要求写 RDMA kernel。数字来自论文/PR 环境，不能泛化。
- 项目假设：实现 trace-driven deadline admission + recompute fallback，核心指标为 feasibility precision、deadline miss、wasted bytes、fallback cost 与 Goodput@SLO。Primary trace：[Mooncake TENT RFC #2519](https://github.com/kvcache-ai/Mooncake/issues/2519)、[PR #2763](https://github.com/kvcache-ai/Mooncake/pull/2763)、[PR #2764](https://github.com/kvcache-ai/Mooncake/pull/2764)、[MFS](https://arxiv.org/abs/2603.17456)。

### 03. [今日焦点：KV/传输层正在长成一套分布式存储](https://mp.weixin.qq.com/s/jk0iAyX5HbDrLRA3g9vTLw)

- 元数据：Ethan，Miracle Farms，2026-07-08 08:53；状态：`readable`。
- 文章主张/机制/证据：Mooncake/LMCache/NIXL 同时补 HA、多租户配额、可观测性；SGLang 先捕获 CUDA graph 再核算 KV pool，文章称旧式静态预留误差可到每 GPU 约 10GB。
- Serving/KV 判断：真正机会是存储控制面的 reconciliation、quota、recovery 与 capacity accounting；CUDA graph 捕获实现属于引擎内部，可只消费其结果。
- 项目假设：做 **KV control-plane conformance suite**：节点重启、event loss、quota exhaustion、stale metadata、partial store/load。Primary trace：[LMCache v0.5.1](https://github.com/LMCache/LMCache/releases/tag/v0.5.1)、[Mooncake PR #2687](https://github.com/kvcache-ai/Mooncake/pull/2687)。

### 04. [异构 P/D 推理的边界：算力、格式与 KV 所有权](https://mp.weixin.qq.com/s/Wc9YGtrLhI_cb1m7OP2gNA)

- 元数据：Ethan，Miracle Farms，2026-07-03 23:52；状态：`readable`。
- 文章主张/机制/证据：异构 P/D 的核心不只是硬件 FLOPS，而是 KV representation、placement、lease/ownership 和接收端可消费性。文章举同一 P:D split 仅改 KV representation，SLA break point 可差 10×，并给出 BF16/FP8/AWQ 的场景性数据。
- Serving/KV 判断：契约、lease、格式验证高度相关；硬件 kernel/量化算子越界。文章明确反对把某组硬件结果当通用最优。
- 项目假设：做 **KV boundary manifest + verifier**，覆盖 dtype、shape、TP layout、model/adapter identity、salt、lease epoch 与 output hash。Primary trace：[vLLM NIXL KV lease design](https://github.com/vllm-project/vllm/blob/d272418f459a82e1012b60116ac00659a7017cde/docs/design/nixl_kv_cache_lease.md)、[SGLang PD docs](https://github.com/sgl-project/sglang/blob/ff1fc1fbdff315fe44b9431ca5aae00d7bd7f733/docs/advanced_features/pd_disaggregation.md)。

### 05. [AI Infra 月报｜6 月：KV Cache 升维为独立基建层，工程化全面收敛](https://mp.weixin.qq.com/s/VCHNj0Tuz0hl7o9Gw826nA)

- 元数据：Ethan，Miracle Farms，2026-07-03 12:32；状态：`readable`。
- 文章主张/机制/证据：从约 1800 条仓库事件选取十大变化，判断 6 月的主线是 KV cache 独立基建化、DSv4 适配和低精度正确性风险；属于趋势汇总，不是独立实验。
- Serving/KV 判断：支持“运维与正确性成为主战场”的方向判断，但不能用事件数量证明生产成熟。
- 项目假设：建立 **upstream capability ledger**，按 shipped/roadmap/closed PR/experiment 分类跟踪 KV 能力，自动生成 pinned-build capability matrix。Primary trace：[LMCache v0.5.0](https://github.com/LMCache/LMCache/releases/tag/v0.5.0)、文章列出的 Mooncake/SGLang/vLLM PR。

### 06. [AI Infra 早报｜MoE 通信容错、KV Cache 基建化与 Agent 安全收紧](https://mp.weixin.qq.com/s/VY1vRKZ9dKsqrVFRREGy6w)

- 元数据：Ethan，Miracle Farms，2026-07-01 08:13；状态：`readable`。
- 文章主张/机制/证据：把 MoE 容错、KV 集群共享、agent 最小权限视为同一“生产就绪”转折；KV 侧以 Mooncake 集群能力为证据。
- Serving/KV 判断：KV 的安全域、租户配额、fail-closed 语义有价值；MoE 通信实现和 agent 权限系统不是本项目主线。
- 项目假设：做 **multi-tenant KV reuse-domain audit**：cache_salt、namespace、quota、authorization、cross-tenant collision 与 fail-closed tests。Primary trace：[vLLM APC cache_salt 文档](https://docs.vllm.ai/en/stable/design/prefix_caching/)、[Mooncake PR #2612](https://github.com/kvcache-ai/Mooncake/pull/2612)。

### 07. [DSpark：推测解码开始把验证预算交给调度器](https://mp.weixin.qq.com/s/d2y2lpDELe0ZeFqcSsAZvg)

- 元数据：Ethan，Miracle Farms，2026-06-29 13:17；状态：`readable`。
- 文章主张/机制/证据：DSpark 用半自回归 draft 与置信度校准，让 scheduler 随并发调整验证 token budget。文章转述 accepted length 提升约 16.3%–30.9%，中等 SLA aggregate throughput 约 51%–52%；661%/406% 是严格 SLA 边界的名义比值，文章也警告不可当常规收益。
- Serving/KV 判断：核心启发是“动态预算应受 SLO/队列约束”，但实现 draft/verify 属于引擎核心。
- 项目假设：把同样思想用于 **KV transfer budget controller**：并发升高时缩短预取/传输预算，比较 static budget 与 calibrated controller，不碰 speculative kernel。Primary trace：[DSpark paper](https://arxiv.org/abs/2606.19348)、[DeepSpec repo](https://github.com/deepseek-ai/DeepSpec)。

### 08. [AI Infra 早报｜KV Cache 的系统化时刻：从本地加速技巧到分布式存储原语](https://mp.weixin.qq.com/s/Izy4C7WD3tUbinfPCBEUuw)

- 元数据：Ethan，Miracle Farms，2026-06-24 07:59；状态：`readable`。
- 文章主张/机制/证据：LMCache v0.5.0 引入 P2P 分布式能力，Mooncake 补多租户运维，文章将其视为 KV 从单机技巧到存储原语的门槛；没有本地复验数据。
- Serving/KV 判断：P2P/remote tier 本身已 shipped，机会在一致性、故障与观测，而非重新实现存储。
- 项目假设：做 **P2P KV chaos/reconciliation harness**：peer disappear、partial transfer、duplicate event、version skew、cold restart。Primary trace：[LMCache v0.5.0](https://github.com/LMCache/LMCache/releases/tag/v0.5.0)、Mooncake PR #2492/#2512/#2550。

### 09. [AI Infra 早报｜投机解码 EAGLE3 拐点与 KV 卸载运维化](https://mp.weixin.qq.com/s/8M-syqXw7ZXlMPFriGPbfw)

- 元数据：Ethan，Miracle Farms，2026-06-22 08:32；状态：`readable`。
- 文章主张/机制/证据：EAGLE3 在多引擎适配，KV offload 同期补 metrics 和 race fix；以“有指标、有竞态修复”推断生产使用正在发生。
- Serving/KV 判断：offload 的 store/load latency、bytes、race、dropped/evictable blocks 是强观测面；EAGLE3 算法越界。单个 PR 不能证明普遍生产部署。
- 项目假设：统一 vLLM/LMCache/Mooncake 的 **offload telemetry schema**，输出 action attribution、queue/D2H/H2D、tier hit、race/fallback。Primary trace：文章列出的 Mooncake PR #2536 与 SGLang/vLLM PR。

### 10. [推理引擎之后：LLM Serving Control Plane 的生态位战争](https://mp.weixin.qq.com/s/7jswyf-6l9KkeukGZxKrMA)

- 元数据：Lychee & Ethan，Miracle Farms，2026-06-19 22:20；状态：`readable`。
- 文章主张/机制/证据：GAIE、AIBrix、llm-d/KServe、vLLM Production Stack、Dynamo、SGLang Gateway 争夺 KV/负载/拓扑/生命周期状态的解释权；Gateway 从 URL router 变成 inference scheduler。
- Serving/KV 判断：高度匹配就业方向，且不要求深入引擎；但“生态位战争”是作者综合判断，不是可验证性能结论。
- 项目假设：做 **engine-neutral KV State Ledger + Endpoint Picker**，以 llm-d precise index 为强基线，专攻 event lag、reconciliation 和 routing explanation。Primary trace：[GAIE InferencePool](https://gateway-api-inference-extension.sigs.k8s.io/api-types/inferencepool/)、[AIBrix Router](https://aibrix.readthedocs.io/latest/designs/aibrix-router.html)、[SGLang Model Gateway](https://github.com/sgl-project/sglang/blob/main/docs/advanced_features/sgl_model_gateway.md)。

### 11. [今日焦点：DeepSeek V4 生态冲刺与 KV Cache 架构定版](https://mp.weixin.qq.com/s/jPgkcUV_-m0fiAcR9jgp-g)

- 元数据：Ethan，Miracle Farms，2026-06-18 09:48；状态：`readable`。
- 文章主张/机制/证据：多框架 DSv4 适配、分布式 cache 架构和低精度路线同时收敛；文章报告 cudagraph 扩大捕获改善 TTFT 近 28%、metadata cache 再改善 2%–4%、FP16 Key + FP8 Value 省约 30% 传输，但均绑定具体 PR/环境。
- Serving/KV 判断：架构/格式协商相关；DSv4 kernel 与量化实现越界。
- 项目假设：实现 **KV format negotiation/capability handshake**，验证 sender/receiver 支持矩阵、fallback 与 silent mismatch。Primary trace：文章链接的 LMCache PR #3277/#3662、Mooncake PR #2405/#2496。

### 12. [AI Infra 早报｜推理与训练基础设施的抽象层级集体跃迁](https://mp.weixin.qq.com/s/j1ey-IYG9zYnFos3bocrYA)

- 元数据：Ethan，Miracle Farms，2026-06-17 07:47；状态：`readable`。
- 文章主张/机制/证据：parser 声明式化、精度策略细化、MoE 调度建模化体现基础设施抽象上移；KV 不是主体。
- Serving/KV 判断：API/parser contract 对 tool event 正确性有相邻价值；训练精度和 MoE kernel 越界。
- 项目假设：做 **streaming tool-event protocol conformance**，将 parser 结果、prefix stability 与 KV hint 关联；若无法形成跨 engine 可复用测试，则不作为主项目。Primary trace：文章列出的 SGLang/vLLM parser PR。

### 13. [Mooncake 的新角色：AI 推理的物流系统](https://mp.weixin.qq.com/s/tLc1XTbDzAuHfk9Q9MDKuQ)

- 元数据：Ethan，Miracle Farms，2026-06-16 21:59；状态：`readable`。
- 文章主张/机制/证据：Mooncake 从 KV store 延展为 transfer + storage + failure handling 的公共数据面。文章转述 610 条 agent trace 上 hit rate 1.7%→92.2%、throughput 3.8×、P50 TTFT 46×，以及 4×200G/8×400G RoCE 的 87/190GB/s；都是项目方特定环境数据。
- Serving/KV 判断：适合作为 backend，而非重造；真实缺口是 control plane 对其状态、故障和 QoS 的消费。
- 项目假设：构建 **Mooncake/LMCache backend-neutral observability adapter**，验证 backend swap 是否保持相同 request-level semantics。Primary trace：[Mooncake FAST'25 paper](https://www.usenix.org/conference/fast25/presentation/qin)、[Mooncake Store design](https://github.com/kvcache-ai/Mooncake/blob/d0e4b6a029ab38827b872087025f621d7e432e1b/docs/source/design/mooncake-store.md)。

### 14. [KV Cache 池化的南向选择：scale-up 内存语义的收益边界](https://mp.weixin.qq.com/s/sGU3Pvolu3tMlRGnRLv9lQ)

- 元数据：Lychee & Ethan，Miracle Farms，2026-06-11 11:55；状态：`readable`。
- 文章主张/机制/证据：Beluga/ShadowServe 等显示小粒度 demand fetch 的控制开销可能主导，内存语义适合异步小访问，北向网络仍适合同步大块交接。文章转述 16KB RDMA 10.55μs 中约 75% 为同步/控制，cache-hit TTFT 1.36s vs 13.0s，但 cold advantage 仅 1.24×。
- Serving/KV 判断：启发是按 access shape 选择 transport；CXL/fabric 实现越界且硬件依赖强。
- 项目假设：做 **transport-shape classifier/replay**，以 size、deadline、reuse、overlap window 选择 northbound bulk 或 southbound fine-grained path；无目标硬件时只做 simulated/trace validated。Primary trace：文章列出的 Beluga/ShadowServe 论文与 [vLLM Ascend issue #2470](https://github.com/vllm-project/vllm-ascend/issues/2470)。

### 15. [AI Infra 早报｜投机解码成为引擎标配，KV Cache 走向分层架构](https://mp.weixin.qq.com/s/3Q35YgaIuEWczkOJj279-g)

- 元数据：Ethan，Miracle Farms，2026-06-11 08:07；状态：`readable`。
- 文章主张/机制/证据：LMCache GDS tier、vLLM Marconi admission、Mooncake batch lookup 分别回答“怎么存、存什么、怎么查”，组合成 HBM/NVMe/remote 分层雏形；cuFile/GDS 依赖特定硬件。
- Serving/KV 判断：多 tier 与 admission 已有 prior art；新价值在策略可解释、成本面与错误域。投机解码部分越界。
- 项目假设：做 **tier policy DecisionTrace**，每次 admission/eviction/promotion 记录预计收益、实际 reuse 与 regret，并以 LRU/ARC/tuned TTL 为基线。Primary trace：[LMCache PR #3589](https://github.com/LMCache/LMCache/pull/3589)、[vLLM PR #37898](https://github.com/vllm-project/vllm/pull/37898)、[Mooncake PR #1834](https://github.com/kvcache-ai/Mooncake/pull/1834)。

### 16. [大规模分布式推理的调度层（上）：KV cache 如何把负载均衡变成状态局部性问题](https://mp.weixin.qq.com/s/y16BVIGa1yJNnB_joEwPVg)

- 元数据：Lychee & Ethan，Miracle Farms，2026-06-08 21:06；状态：`readable`。
- 文章主张/机制/证据：调度需联合 cache locality 与 load；文章引 llm-d 估算 hit/miss 可差约一个数量级，并转述 MiMo 路由 L2 hit +25%、input throughput +30%、长请求 P90 TTFT -30%。这些数字绑定各自系统。
- Serving/KV 判断：高度匹配 router/control plane；简单 prefix-hash/Po2/least-request 已是现成基线。
- 项目假设：比较 request-history heuristic 与 KVEvents precise index 的 **false-locality rate、event lag 和 tail TTFT**，目标是解释什么时候“精确索引”的维护成本值得。Primary trace：[llm-d KV cache wins](https://llm-d.ai/blog/kvcache-wins-you-can-see)、[vLLM Router](https://github.com/vllm-project/router)、[llm-d router](https://github.com/llm-d/llm-d-router)。

### 17. [大规模分布式推理的调度层（下）：从相位、区域到学出来的路由](https://mp.weixin.qq.com/s/Os25vHMp0OnvWJTmLZwuOQ)

- 元数据：Lychee & Ethan，Miracle Farms，2026-06-09 07:30；状态：`readable`。
- 文章主张/机制/证据：agent 多轮高命中将 PD 瓶颈移到 storage I/O；PPD 对 append-prefill 选择 decode-local 或 prefill，文章称 transfer load -75%；DualPath 利用 decode 侧闲置路径，论文报告在线约 1.96×。
- Serving/KV 判断：相位感知路由有价值，但“学习式”不应默认优于 tuned heuristic；跨域/异构结果不可外推。
- 项目假设：做 **phase-aware router replay**，状态只用可观测的 append tokens、resident KV、queue、NIC utilization；先验证可解释 heuristic，再决定是否需要 learned policy。Primary trace：文章列出的 [DualPath](https://arxiv.org/abs/2602.21548) 与 PPD 研究。

### 18. [从 KV Cache 底座到推理统一数据面：Mooncake 的架构演化、生态落地与选型](https://mp.weixin.qq.com/s/HMz1efOlji8C_dNcNNvHSg)

- 元数据：Lychee & Ethan，Miracle Farms，2026-06-02 15:38；状态：`readable`。
- 文章主张/机制/证据：Mooncake 的 TransferEngine、Store、Conductor/indexer、权重与 KV 传输正在汇合为数据面。文章区分论文 simulation/production trace，并指出 capability list 与可直接启用之间还有分支状态差距。
- Serving/KV 判断：选型应把 Mooncake 当 backend/data plane，不是完整策略层；Conductor 的未来能力不能写成 shipped。
- 项目假设：做 **backend capability matrix + live probe**，核对目标 commit 的 store/load、replication、L3、metrics、failure semantics，避免按 README 推断能力。Primary trace：[Mooncake repo](https://github.com/kvcache-ai/Mooncake)、[Conductor architecture](https://github.com/kvcache-ai/Mooncake/blob/94b9a6bc3ee7c4cb343cf433c2742b1d8c7560c2/docs/source/design/conductor/conductor-architecture-design.md)。

### 19. [今日焦点：KV Cache 三层进化——正确性、存储、精度并行推进](https://mp.weixin.qq.com/s/rGSZI0xOK_5nxRuKz-g8pg)

- 元数据：Ethan，Miracle Farms，2026-06-01 08:02；状态：`readable`。
- 文章主张/机制/证据：SGLang KV-Canary、Mooncake/LMCache 多租户存储、TRT-LLM NVFP4 同时推进，说明竞争从吞吐/延迟扩展到 correctness、reuse、precision。
- Serving/KV 判断：正确性验证是低越界、高可信度项目；实现 NVFP4 kernel 越界。
- 项目假设：做 **KV Canary cross-tier suite**：随机采样 cache hit，比较 cached vs recompute logits/output hash，注入 stale/corrupt/wrong-tenant blocks，报告 silent-corruption detection。Primary trace：文章列出的 [SGLang PR #26808](https://github.com/sgl-project/sglang/pull/26808) 与 LMCache v0.4.6。

### 20. [今日焦点：推理栈的抽象升级——MLA 插件化、CuTe DSL 标配化与 KV Cache 策略表达](https://mp.weixin.qq.com/s/6VH-YOh559ffeK6RDcaoqA)

- 元数据：Ethan，Miracle Farms，2026-05-29 08:06；状态：`readable`。
- 文章主张/机制/证据：MLA backend registry、CuTe DSL kernel 与 per-request OffloadPolicy 同时出现；KV 侧的关键是 host-tier waste metrics、BLOCK/REQUEST policy 和 lifecycle hook。
- Serving/KV 判断：per-request policy/metrics 是合适 extension seam；MLA/CuTe kernel 是明确越界项。
- 项目假设：围绕 vLLM native hook 做 **request-level cache intent adapter**，接受 workload hint 并输出 actual action；先确认 [PR #43205](https://github.com/vllm-project/vllm/pull/43205) 是否进入目标版本，未合入则降级为 capability probe，不 fork core。

### 21. [Agentic 推理的性能重构：KV Cache 与系统调度的十个新判断](https://mp.weixin.qq.com/s/a-U86GDVuzdLdtq3ql4I6A)

- 元数据：Lychee & Ethan，Miracle Farms，2026-05-29 07:30；状态：`readable`。
- 文章主张/机制/证据：agent 是状态累积 workload，不是更长 chat。文章综述称跨轮可复用输入 84.6%–99.5%，但缓存容量压力可令 hit rate 从近 100% 跌到 40% 以下；失败 run 的上下文高 15%–40%，容量需求可能被低估 1.5–2×。
- Serving/KV 判断：这是 benchmark/容量规划最重要的证据；数字来自不同论文，不能拼成单一 workload 的因果链。
- 项目假设：做 **failure-aware agent KV benchmark**，保留工具失败、重试、context growth、working-set phase transition；指标含 request/token hit、prefill avoided、NIC、tier migration、JCT 和 Goodput@SLO。Primary trace：文章列出的十篇 arXiv 工作，尤其 2605.26297/2605.26289。

### 22. [LMCache 在 AMD MI300X 上的部署实录：Agent 负载下的 KV Cache 分级策略](https://mp.weixin.qq.com/s/jmebOTDb4779d7aGZ-KCLw)

- 元数据：Ethan，Miracle Farms，2026-05-27 21:25；状态：`readable`。
- 文章主张/机制/证据：2×MI300X、739 条 agent trace 显示“regime 决定一切”；文章称同步 CPU 写会串行 GPU pipeline，1K/2K 热缓存加速 2.0×/10.7×，但 L2 价值主要在 working set 超出 HBM 后防止断崖退化。
- Serving/KV 判断：强烈支持跨硬件/working-set cost surface；不支持“LMCache 默认有收益”。
- 项目假设：做 **cross-vendor regime map**，变量为 context、working set、concurrency、async/sync store、interconnect；必须保留 cache 无收益/负收益区域。Primary trace：[LMCache AMD benchmark](https://blog.lmcache.ai/en/2026/05/12/benchmarking-lmcache-for-multi-turn-agentic-workloads-on-amd-mi300x/)。

### 23. [SGLang 分层稀疏注意力：把 KV Cache 从容量扩展推进到按需加载](https://mp.weixin.qq.com/s/HwFjsnEr0kvcanEXXIWl5g)

- 元数据：Ethan，Miracle Farms，2026-05-26 08:57；状态：`readable`。
- 文章主张/机制/证据：完整 KV 留在 CPU/remote，GPU 维护 Top-k 的 2–4× LRU hot window，相邻 step Top-k 重叠 80%–90%，只增量加载；文章转述 DeepSeek V3.2 单请求 GPU KV 约 8GB→200MB、吞吐 2–3×。
- Serving/KV 判断：数据面调度/观测相关，但 Top-k selector、sparse attention/I/O kernel 深入引擎与算子，不适合作为主项目。
- 项目假设：只做 **sparse-KV demand-fetch trace analyzer**，研究 hot-window miss、bytes、stall 与 tier sizing；若必须实现 selector/kernel 才能拿到数据，放弃。Primary trace：文章列出的 [SGLang HiCache best practices](https://docs.sglang.ai/advanced_features/hicache_best_practices.html) 与 sparse-attention 论文。

### 24. [vLLM、SGLang 与 TensorRT-LLM 的服务 API 兼容层设计](https://mp.weixin.qq.com/s/kEPD-M96dMV3OU6DDbdWlw)

- 元数据：Ethan，Miracle Farms，2026-05-25 23:30；状态：`readable`。
- 文章主张/机制/证据：“OpenAI compatible”不覆盖 Responses 状态链路、Anthropic Messages、typed SSE 与 tool events；应把兼容拆成 schema、stream、parser、behavior 四层。
- Serving/KV 判断：这是 serving API 层，低越界；与 KV 的连接在 session identity、prefix stability、tool boundary 和 lifecycle hints。
- 项目假设：做 **agent API + KV hint conformance proxy**，记录原始 SSE、session/workflow id、stable-prefix boundary 与 cache outcome；模型行为与协议搬运必须分开验。Primary trace：[vLLM OpenAI server docs](https://docs.vllm.ai/en/latest/serving/openai_compatible_server/)、SGLang/Anthropic serving source、TRT-LLM openai_server source。

### 25. [NVIDIA Dynamo 的 Agentic 推理架构：当 Harness 开始向推理引擎「显式传话」](https://mp.weixin.qq.com/s/kT3DWbCuf-VcD-zJB5hZDA)

- 元数据：Ethan，Miracle Farms，2026-05-25 16:20；状态：`readable`。
- 文章主张/机制/证据：WORM agent workload 需要 KV-aware routing、retention 和 harness hints；文章转述同 worker 后续调用 hit 85%–97%、四 teammate aggregate 97.2%，以及一个不稳定 prefix header 令 52K prompt TTFT 912ms→168ms 的案例。
- Serving/KV 判断：强烈支持 harness–engine contract；这些是 NVIDIA 特定部署，不是通用承诺。
- 项目假设：定义 **portable agent hints envelope**，在 Dynamo `nvext`、vLLM/SGLang adapter 间映射，验证 stable-prefix、ephemeral reasoning、tool-wait、deadline 是否能提升可解释命中而不泄漏租户信息。Primary trace：[Dynamo agentic optimization](https://developer.nvidia.com/blog/full-stack-optimizations-for-agentic-inference-with-nvidia-dynamo/)、[Dynamo repo](https://github.com/ai-dynamo/dynamo)。

### 26. [今日焦点：推理引擎 Kernel Fusion 系统性收敛，KV Cache 进入多级分层时代](https://mp.weixin.qq.com/s/j6iDsxZZJ5C4Tv9oKqRDaQ)

- 元数据：Ethan，Miracle Farms，2026-05-25 08:00；状态：`readable`。
- 文章主张/机制/证据：多框架在 kernel fusion 与 GPU→CPU→storage tiering 上趋同；属于仓库事件趋势判断，无独立 benchmark。
- Serving/KV 判断：多级分层相关；kernel fusion 越界。
- 项目假设：以 vLLM native offload、SGLang HiCache、LMCache 为三套 backend，做 **same-trace tier semantics comparison**，重点比较 hit 定义、completion、promotion 和 failure，而不是峰值带宽。Primary trace：[vLLM KV offloading guide](https://docs.vllm.ai/en/v0.25.0/features/kv_offloading_usage/)、[SGLang HiCache](https://docs.sglang.ai/advanced_features/hicache.html)。

### 27. [CacheFlow：KV Cache 恢复的三维并行调度——从二选一到多维度分解](https://mp.weixin.qq.com/s/Grh2fs9kYoOQuE4XOmpOVw)

- 元数据：Ethan，Miracle Farms，2026-05-24 14:46；状态：`readable`。
- 文章主张/机制/证据：CacheFlow 用 token/layer/GPU 三维双指针并行 compute 与 I/O，batch 级按剩余重算成本分配 I/O。论文环境报告 TTFT -10%–62%；batch 2→8 时相对 per-request 1.6×→2.6×。
- Serving/KV 判断：调度思想相关，但 layer/GPU 恢复实现可能侵入 engine；不能把论文结果当 current vLLM 能力。
- 项目假设：先做 **trace-level compute/load co-scheduler simulator**，用真实 measured cost curves 验证是否存在稳定收益；若落地要求大 fork，则止于 simulator/benchmark。Primary trace：[CacheFlow](https://arxiv.org/abs/2604.25080)、[Cake](https://arxiv.org/abs/2504.10455)。

### 28. [ContiguousKV：消除 KV Cache 剪枝与 I/O 的粒度错配](https://mp.weixin.qq.com/s/L2bvEBVFbJPnEpu6MUb0GA)

- 元数据：Ethan，Miracle Farms，2026-05-24 11:35；状态：`readable`。
- 文章主张/机制/证据：token-level selection 与 64-token I/O chunk 产生最高 56× read amplification；ContiguousChunk 用 16-token 统一 selection/storage/eviction 粒度，并用跨层相似性预取。文章报告 I/O 占 >65%，Qwen2.5-7B 每 16-token chunk 约 448KB。
- Serving/KV 判断：统一粒度是有价值的接口设计启发；剪枝、attention selection 进入算法/引擎深水区。
- 项目假设：做 **granularity mismatch analyzer**，输入 engine block、storage object、transport fragment、request prefix shape，输出 amplification 与推荐配置；不实现 pruning。Primary trace：[ContiguousKV](https://arxiv.org/html/2601.13631v1)。

### 29. [KVDrive 论文阅读：当 KV Cache 管理从算法问题变成系统问题](https://mp.weixin.qq.com/s/sVUqw48VArwh2b1MNmUgLA)

- 元数据：Ethan，Miracle Farms，2026-05-24 02:07；状态：`readable`。
- 文章主张/机制/证据：滑动窗口 cache、elastic pipeline、DRAM/SSD tier 将重点从 selection accuracy 移到 selection/fetch scheduling。论文环境称 selection+fetch 接近 decode 50%，6.25% sparse budget 下每 step H2D >500MB→<12.5MB，吞吐 1.74×。
- Serving/KV 判断：系统 pipeline/tier sizing 相关；attention-signal selection 和 sparse compute 越界。
- 项目假设：做 **offload pipeline stall profiler**，分解 select/fetch/compute overlap，并验证 SSD layout/async prefetch 的 operating region；不复刻稀疏算法。Primary trace：[KVDrive](https://arxiv.org/abs/2605.18071)。

### 30. [Tair-KVCache-HiSim：把 KV Cache 配置从试错变成仿真优化](https://mp.weixin.qq.com/s/A1QuFiLsOBTGf4ThX0DZeA)

- 元数据：Ethan，Miracle Farms，2026-05-23 18:26；状态：`readable`。
- 文章主张/机制/证据：HiSim 用 workload generator、global router、instance simulator 与 BatchRunnerEstimator 在 CPU 上估 TTFT/TPOT/throughput/hit；项目方报告 batch estimator 4.24% 误差、端到端 TTFT 3.25%–10.75%，但文章指出开源状态、支持矩阵和生态绑定未回答。
- Serving/KV 判断：仿真/容量规划高度相关；39 万倍成本数字依赖计价口径，不能直接复用。
- 项目假设：做开源 **Agent-KV replay simulator**，优先复现 workload regime/negative region，GPU 校准只做少量锚点；若跨负载误差不可控，明确定位为 comparative simulator。Primary trace：[Alibaba Cloud HiSim post](https://www.alibabacloud.com/blog/alibaba-cloud-tair-kvcache-simulation-analysis-high-precision-computational-and-caching-simulation-design-and-implementation_603164)。

### 31. [TRT-LLM KV Cache 存储池：读懂 NVIDIA 对推理内存的显式建模](https://mp.weixin.qq.com/s/jfKPZtv74nTCogoAx1jQfQ)

- 元数据：Ethan，Miracle Farms，2026-05-22 11:36；状态：`readable`。
- 文章主张/机制/证据：TRT-LLM 用 block、role、tier、fragment 显式表达缓存；不同模型 100K KV 约 2.4GB–25.4GB，sender/receiver 并行布局不同时 block 还要 fragment/format。
- Serving/KV 判断：明确的数据模型有利于跨节点契约，但复刻 TRT-LLM C++ manager 会深入 engine core。
- 项目假设：抽取 **cross-engine KV manifest vocabulary**（block/role/tier/fragment/layout/epoch），用于 trace、验证和 adapter，不做新的内存池。Primary trace：[TRT-LLM kvCacheManager.h](https://github.com/NVIDIA/TensorRT-LLM/blob/66988254ed3f84aa4684c6423c63f81ddd134da3/cpp/include/tensorrt_llm/batch_manager/kvCacheManager.h) 及 cacheFormatter/transferManager 源码。

### 32. [今日焦点：KV Cache 复用四框架同日落地，推理引擎进入缓存利用率竞争](https://mp.weixin.qq.com/s/XAPjcr5WPl-cj025FGHivA)

- 元数据：Ethan，Miracle Farms，2026-05-22 10:42；状态：`readable`。
- 文章主张/机制/证据：TRT-LLM、SGLang、TokenSpeed、Mooncake 在 API、设备传输和 reuse 上同期更新，作者判断竞争轴转向 cache utilization；这是事件聚合，没有统一 workload 实验。
- Serving/KV 判断：支持统一 cache outcome 指标的必要性；“同日 PR”不能证明架构定局。
- 项目假设：建立 **cross-engine cache metrics semantics**，区分 request hit、token hit、prefix matched、prefill avoided、tier hit 与 end-to-end benefit，防止不同框架 hit rate 横向误读。Primary trace：文章列出的 TRT-LLM/SGLang/Mooncake PR。

### 33. [vLLM KV Cache 类型体系拆解：一个抽象统一十种缓存规格](https://mp.weixin.qq.com/s/deCbrWYOL2HChR3J1P3twA)

- 元数据：Ethan，Miracle Farms，2026-05-21 21:55；状态：`readable`。
- 文章主张/机制/证据：vLLM 以统一 KVCacheSpec/manager 处理 full attention、MLA、hybrid/linear state 等不同增长语义；五模型 100K KV 相差约十倍。
- Serving/KV 判断：容量模型与 scheduler admission 相关；实现新 attention spec 越界。
- 项目假设：做 **model-derived KV capacity calculator + admission audit**，从 config/engine metadata 推导 bytes/token、page size、state growth，并与 runtime occupancy 对账。Primary trace：[vLLM kv_cache_interface.py](https://github.com/vllm-project/vllm/blob/87e31455b/vllm/v1/kv_cache_interface.py) 与各模型官方 config。

### 34. [ZCube 把 PD 分离推理的网络瓶颈变成拓扑问题](https://mp.weixin.qq.com/s/VvV3NODE-GOq61cXwfJ-Yw)

- 元数据：Ethan，Miracle Farms，2026-05-21 16:37；状态：`readable`。
- 文章主张/机制/证据：Z.ai 称只改网络拓扑得到吞吐 +15%、TTFT P99 -40.6%、网络成本 -33%；32 卡 ablation 中 100→200Gbps 吞吐 +19%。文章明确不能外推到所有 PD 集群。
- Serving/KV 判断：拓扑感知 placement/router 相关；网络架构实现与交换芯片越界。
- 项目假设：做 **topology-aware KV placement simulator**，以 measured link matrix、KV bytes、deadline 评估 placement；没有同级硬件就只能标 `simulated`。Primary trace：[Z.ai ZCube report](https://z.ai/blog/zcube)、SIGCOMM 2025 论文入口。

### 35. [SGLang KV Cache 存储池架构：七种类型的内存公式与跨模型对比](https://mp.weixin.qq.com/s/Ye7PaAds_HqPExysf8ohIw)

- 元数据：Ethan，Miracle Farms，2026-05-21 15:17；状态：`readable`。
- 文章主张/机制/证据：从 SGLang memory pool 源码推导 MHA/GQA/MLA/SWA/indexer 等布局；文章称五款 MoE 100K KV 约 2.4–25.4GB，MLA 相对 MHA 可有 7–15×量级压缩，取决于模型。
- Serving/KV 判断：适合容量/调度工具，不适合写 pool/kernel。
- 项目假设：将 vLLM/SGLang/TRT-LLM 的内存公式统一到 **capacity model schema**，对照实测 occupancy，定位 allocator overhead、graph reserve 与 fragment gap。Primary trace：SGLang `memory_pool.py`、`pool_configurator.py` 与模型官方 config。

### 36. [昇腾 KV Pool 阅读：vLLM Ascend 如何把 Mooncake 接成硬件亲和的数据面](https://mp.weixin.qq.com/s/VylIUYhfltoSJ2Qm-jxUmA)

- 元数据：Ethan，Miracle Farms，2026-05-20 14:35；状态：`readable`。
- 文章主张/机制/证据：AscendStoreConnector 把调度接口与 Mooncake/Memcache/Yuanrong backend 分离，平台层保留 HCCN/FabricMem 亲和优化；部署需要明确版本、segment 1GB 对齐等条件。
- Serving/KV 判断：connector seam 与 capability negotiation 高度相关；昇腾算子/传输内核越界。
- 项目假设：做 **connector contract test kit**，同一组 reserve/register/store/load/free/restart tests 跑不同 backend，验证“通用层能用、平台层用好”的边界。Primary trace：[vLLM Ascend KV Pool docs](https://github.com/vllm-project/vllm-ascend/blob/215028c0bd9411224227ac87d420402b5f4d463b/docs/source/user_guide/feature_guide/kv_pool.md)、`ascend_store_connector.py`。

### 37. [SGLang 部署方式、KV Cache 调参与最佳实践](https://mp.weixin.qq.com/s/ejrMy_nhoE2goPO62BV04A)

- 元数据：Ethan，Miracle Farms，2026-05-20 12:19；状态：`readable`。
- 文章主张/机制/证据：先识别 workload reuse shape，再联合 KV pool、RadixAttention、chunked prefill、scheduler conservatism、HiCache page size；文章给出 5–8GB 余量等经验值和 FP4/FP8 理论容量比。
- Serving/KV 判断：可做自动诊断/调参，但经验值不能当普适规则；量化 kernel 越界。
- 项目假设：做 **SGLang deployment linter + trace recommender**，所有建议必须标 evidence/assumption，并用小规模 replay 验证；不直接自动修改生产配置。Primary trace：[SGLang hyperparameter tuning](https://docs.sglang.ai/advanced_features/hyperparameter_tuning.html)、HiCache/PD/server arguments 官方文档。

### 38. [CXL + KV Cache：长上下文推理的下一层内存系统](https://mp.weixin.qq.com/s/t7OxP98nDeDDCeiuwnXnGA)

- 元数据：Ethan，Miracle Farms，2026-05-19 14:11；状态：`readable`。
- 文章主张/机制/证据：CXL 适合 HBM 放不下、NVMe 又太慢的“温层”，前提是软件显式做 placement/admission；文章建议以 32K+、hit≥50%、TTFT P95 改善且 TPOT P95 劣化≤5% 作为 PoC 门槛。
- Serving/KV 判断：有硬件条件才可 experimentally validated；无 CXL 设备不应包装为完成项目。
- 项目假设：若有设备，做 **warm-tier PoC + negative regions**；否则做 hardware-agnostic tier interface/simulator，不以 CXL 为主标题。Primary trace：[CXL Consortium](https://computeexpresslink.org/about-cxl/) 与文章列出的 Beluga/CXL 论文。

### 39. [今日焦点：KV Cache 落磁盘三级闭环 + Blackwell MoE Dense GEMM 首次工程解析](https://mp.weixin.qq.com/s/jkMpykanYabbpX5QJoxxlQ)

- 元数据：荔枝不耐思，Miracle Farms，2026-05-17 09:03；状态：`readable`。
- 文章主张/机制/证据：LMCache/vLLM/Mooncake 令 GPU→CPU→SSD tier 进入工程路径；Blackwell MoE 优化是另一条越界主线。文章没有统一 workload 下的三层收益数据。
- Serving/KV 判断：三级 tier 已不是空白；有价值的是 disk promotion、persistence、restart 和 read amplification。
- 项目假设：做 **disk-tier persistence/failure benchmark**，覆盖 write completion、process restart、disk corruption、fragmentation、cold/warm TTFT 与 endurance bytes。Primary trace：LMCache v0.4.5 及文章列出的 PR #2902/#3171/#3227/#3299。

### 40. [KV Cache 前缀匹配的设计分野：SGLang、vLLM 与 TensorRT-LLM 怎么定义“命中”](https://mp.weixin.qq.com/s/GciJebFszheSqU-s3yZPMQ)

- 元数据：Lychee & Ethan，Miracle Farms，2026-05-16 11:02；状态：`readable`。
- 文章主张/机制/证据：SGLang radix tree 支持 token 级节点分裂；vLLM 链式 hash 只命中完整 block；TRT-LLM key 还编码 LoRA/multimodal/tenant/SWA，并在 C++ 用 claim 避免 TOCTOU。文章举 2048-token prefix TTFT 450→95ms 的外部数据。
- Serving/KV 判断：最重要的是“命中语义”和隔离，不是宣称某结构绝对最好。
- 项目假设：做 **cross-engine prefix-hit oracle**，给定 tokenization、block size、salt/tenant、adapter、partial block，预测理论/实际命中并验证 discrepancy。Primary trace：[vLLM APC docs](https://docs.vllm.ai/en/stable/design/prefix_caching/)、[SGLang paper](https://arxiv.org/abs/2312.07104)、TRT-LLM source。

### 41. [生产级 Agent 的 Token 经济学：Claude Code 为什么必须围绕 KV Cache 设计](https://mp.weixin.qq.com/s/bfp07rP1OYSd3XCUtVvjjQ)

- 元数据：Lychee & Ethan，Miracle Farms，2026-05-14 17:12；状态：`readable`。
- 文章主张/机制/证据：agent 要稳定 prefix、把动态工具/状态放尾部、监控 cache break、在 compaction 时显式破坏缓存。文章引用 Claude cache read/uncached 输入价差 10×，以及约 90% cache break 来自 server routing/eviction 的项目观察。
- Serving/KV 判断：非常适合 harness/serving seam；价格会变化且不同 provider cache 语义不同，需 live verify。
- 项目假设：做 **cache-break observability proxy**，关联 prompt diff、routing、eviction、compaction、provider usage，输出 cause attribution；不要把 provider response cache 与 engine KV 混为一谈。Primary trace：[Anthropic prompt caching docs](https://platform.claude.com/docs/en/docs/build-with-claude/prompt-caching)、[LMCache docs](https://docs.lmcache.ai/)。

### 42. [今日焦点：KV Cache Offload 跨框架打通，推测解码升格为系统组件](https://mp.weixin.qq.com/s/YyH_pQ_0EizW6G7tBJcviw)

- 元数据：荔枝不耐思，Miracle Farms，2026-05-13 10:56；状态：`readable`。
- 文章主张/机制/证据：LMCache/TRT-LLM/vLLM/Mooncake offload 链路密集修复，作者以“能被修”推断真实使用；没有跨框架同口径实验。
- Serving/KV 判断：适合 conformance/interoperability，投机解码实现越界。
- 项目假设：维护 **offload interop regression suite**，按版本记录已知错误、completion semantics、metrics contract 和 fallback；目标是避免升级后 silent recompute 被误记为 cache hit。Primary trace：文章列出的 LMCache PR #3038/#3120 与 TRT-LLM PR。

### 43. [TensorRT-LLM 如何管理 KV Cache：优先级淘汰、硬件级卸载与事件驱动的集群路由](https://mp.weixin.qq.com/s/YSIQ8W-pORR9YKeLYDSAZA)

- 元数据：Lychee & Ethan，Miracle Farms，2026-05-13 00:54；状态：`readable`。
- 文章主张/机制/证据：TRT-LLM 以 128-token block、priority/duration、host offload、cache events 和 Dynamo routing 显式定价 cache。文章转述 priority eviction hit +20%，GB200/DeepSeek 分离式吞吐 1.4–1.8×；均为 NVIDIA 场景。
- Serving/KV 判断：事件驱动路由与优先级 contract 有价值；GH200/GB200 hardware path 和 compiled layout 不适合主项目。
- 项目假设：对比 **priority hint vs observed residency/reuse**，量化 hint calibration、event lag、false retention 和 active-request harm。Primary trace：[TRT-LLM KV cache docs](https://nvidia.github.io/TensorRT-LLM/latest/features/kvcache.html)、[Dynamo TRT-LLM KV transfer](https://docs.nvidia.com/dynamo/latest/backends/trtllm/kv-cache-transfer.html)。

### 44. [vLLM 如何管理 KV Cache：从 vLLM 本地 Block 管理到跨实例缓存池](https://mp.weixin.qq.com/s/zkXW6rXOBNQeZgPSMB_zyQ)

- 元数据：Lychee & Ethan，Miracle Farms，2026-05-12 00:02；状态：`readable`。
- 文章主张/机制/证据：vLLM 将 block 状态机内联进 scheduler，再通过 connectors 接 LMCache/Mooncake。文章转述 610 条 agent trace 的 1.7%→92.2% hit、3.8× throughput、46× P50 TTFT；并指出 decode 直接从 pool 拉取等能力在当时仍是计划。
- Serving/KV 判断：native block/connector 是首选 extension seam；文章中“计划”不能写成 shipped。
- 项目假设：做 **pinned-vLLM connector capability probe + attribution**，证明 requested/observed action、GPU/CPU/remote hit、async completion 与 fallback。Primary trace：[vLLM OffloadingConnector source](https://github.com/vllm-project/vllm/blob/main/vllm/distributed/kv_transfer/kv_connector/v1/offloading_connector.py)、文章列出的 Mooncake/LMCache PR。

### 45. [SGLang 如何管理 KV Cache：从 RadixAttention 到 HiCache 的底层技术主线](https://mp.weixin.qq.com/s/BakRqb-l2IhHeQFc5TCp1Q)

- 元数据：Lychee & Ethan，Miracle Farms，2026-05-11 07:38；状态：`readable`。
- 文章主张/机制/证据：SGLang 以 radix tree 组织 exact prefix reuse，再扩到 HiCache tier、HiSparse 和 ShadowRadix。文章汇总若干部署数据，如 Qwen3-Coder hit 40%→80%、TTFT -56%、吞吐 2×；不同来源/版本不可合并成通用结论。
- Serving/KV 判断：RadixAttention/HiCache 是强基线，重做树或稀疏 kernel 没有项目新意。
- 项目假设：做 **SGLang cache observability & tier-policy evaluator**，围绕 radix hit、eviction、tier promotion、router locality 与 negative regions，不修改 radix core。Primary trace：[SGLang paper](https://arxiv.org/abs/2312.07104)、[HiCache docs](https://docs.sglang.ai/advanced_features/hicache.html)、`radix_cache.py`/`hiradix_cache.py` source。

## 一手来源交叉核验：哪些能力真的存在

| 能力 | 一手来源状态（截至 2026-07-13） | 对项目主张的约束 |
|---|---|---|
| vLLM exact prefix caching | [APC docs](https://docs.vllm.ai/en/stable/design/prefix_caching/) 与 KV manager source：`shipped` | 不重做 exact prefix cache；APC 不等于 semantic reuse，也不等于 tool-wait lifecycle policy。 |
| vLLM native KV offload | [KV offloading guide](https://docs.vllm.ai/en/v0.25.0/features/kv_offloading_usage/) 与 [OffloadingConnector](https://github.com/vllm-project/vllm/blob/main/vllm/distributed/kv_transfer/kv_connector/v1/offloading_connector.py)：`shipped` | CPU/secondary tier 已存在；需要研究 completion、attribution、policy、failure，不是“能 offload”。 |
| vLLM context-aware retention | [RFC #37003](https://github.com/vllm-project/vllm/issues/37003) open；[PR #38514](https://github.com/vllm-project/vllm/pull/38514) closed without merge：`roadmap` | 不得把 priority/duration retention 写成 current stable API；实现前做 pinned-build probe。 |
| vLLM disaggregated prefill | [官方文档](https://docs.vllm.ai/en/latest/features/disagg_prefill/) 标 experimental | 可以做 testbed；官方明确它不保证提高 throughput，重点是 TTFT/ITL isolation。 |
| SGLang RadixAttention/HiCache | [SGLang paper](https://arxiv.org/abs/2312.07104)、[radix source](https://github.com/sgl-project/sglang/blob/main/python/sglang/srt/mem_cache/radix_cache.py)、HiCache source/docs：`shipped` | 是 tree/tier baseline；文章 speedup 只能归属原环境。 |
| LMCache/Mooncake 多级/远端数据面 | 官方 docs/repo：`shipped`；Mooncake FAST'25 含 experiment/simulation/production trace 多种证据 | backend 可复用；不得把论文/README 最高倍数当项目预期。 |
| cache-aware routing | SGLang/vLLM Router/AIBrix：`shipped`；Preble：论文 `experimentally validated`；llm-d precise index：事件驱动实现可用 | 新 router 必须对比 tuned baseline，证明 state accuracy/SLO/failure 价值。 |
| tool-wait lifecycle prior art | [InferCept](https://arxiv.org/abs/2402.01869)、[Continuum](https://arxiv.org/abs/2511.02230)、[Astraea](https://arxiv.org/abs/2512.14142)：论文 `experimentally validated`；公开代码完整度不同 | retain/offload/recompute、TTL/duration、pressure-aware selector 均非空白。 |
| approximate/non-prefix reuse | CacheBlend/Cache-Craft 是 repeated chunk + selective recompute；GPTCache/Krites 是 response cache | `semantic cache ≠ semantic KV reuse`；必须测质量/一致性，不能以最终 accuracy 单指标证明安全。 |

## 对抗式审查：这些“新方向”为什么可能失败

1. **状态事实表可能不值得维护。** 如果 request-history/consistent-hash 已能拿到几乎相同 TTFT，KVEvents index 的复杂性没有回报；项目必须报告 false-locality 与 reconciliation cost，而不是只展示架构。
2. **deadline scheduler 只在狭窄过渡带有效。** deadline 太松或太紧都无收益；若 workload 很少进入过渡带，应该终止该主线。
3. **多 tier 可能只是把瓶颈从 HBM 移到 NIC/PCIe/SSD。** hit rate 提升不等于 prefilling work 被真正避免，也不等于 JCT/Goodput 提升。
4. **agent hint 可能变成不可移植的私有协议。** 若 vLLM/SGLang/Dynamo 无法共享最小语义，协议项目会退化成单框架配置封装。
5. **simulator 很容易高保真地拟合错误世界。** 必须用 held-out hardware/workload 验证，并公开误差随 concurrency、disk tier、failure shift 的退化。
6. **正确性 verifier 可能只有测试价值，没有系统贡献。** 它需要抓到真实上游 bug、定义可复用 contract 或进入 CI，才足以成为强项目。

## 检索与阅读局限

- 45 篇原文均成功取得正文；文章大多来自同一公众号，观点与选题存在来源相关性，不能当作 45 个独立市场信号。
- 本台账追溯了关键论文、官方 docs、repo、issue/PR；没有逐一复现文章引用的所有性能实验。所有倍数只代表原作者声明的环境。
- PR、main branch 与 preview code 在 2026 年仍快速变化；落地前必须 pin commit，并重新确认 merged/closed/experimental 状态。
- 本报告刻意排除 kernel/算子主项目；这不意味着它们不重要，只是与目标岗位边界和可交付性不匹配。

## 完整性自检

- 用户输入链接数：45
- 独立文章条目：45（编号 01–45）
- `readable`：45
- `metadata_only` / `unread` / `failed`：0
- 每条均包含：元数据、文章主张/机制/证据、Serving/KV 判断与越界、可导出项目假设、一手来源入口。
