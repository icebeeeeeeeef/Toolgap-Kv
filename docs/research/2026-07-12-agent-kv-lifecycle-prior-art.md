# Agent KV 生命周期 prior-art 与重复工作风险审查

> 日期：2026-07-12
> 证据状态：`roadmap`（本报告是文献与上游状态审查，不是本项目的 GPU 实验结果）
> 来源边界：论文原文、作者官方仓库/项目页、vLLM/NVIDIA 官方 issue、PR 与文档。未把博客转载、搜索摘要或第三方复现当作结论证据。

## 结论先行

ToolGap-KV **不能再把“agent 调用工具时在 retain / offload / recompute 三者间动态选择”当作机制创新**。这条主线至少已被 InferCept 的 Preserve/Swap/Discard + MinWaste、Continuum 的 tool-aware TTL、Astraea 的 I/O-wait 自适应 KV 管理，以及 ThunderAgent 的 caching/recompute time-decay 占据。PBKV、KVFlow 又覆盖了动态/静态 agent workflow 下的预测驱逐与预取。

但这不等于 Experiment 0001 应删除。它目前只问同一 pinned vLLM 构建能否**确定性触发并归因** GPU hit、CPU restore、full recompute；这是一项必要的集成校准，而不是论文贡献。重复风险出现在下一步：若项目只实现一个成本公式或 duration predictor，并报告它胜过 LRU，就会高度重复。

可辩护的改题应从“提出新策略”改为：

> **在当前 vLLM 原生 offload 与不稳定 retention contract 上，对 agent tool-gap 生命周期做可复现的机制校准、跨硬件 break-even map、强静态基线与失败域研究。**

换言之，剩余价值是 `modern vLLM artifact + deterministic attribution + hardware/workload boundary + negative results`，不是三动作本身，也不是“预测工具时长”本身。

## 1. 直接 prior art

| 工作 | 场景与机制（primary source） | 已占据的结论/机制 | 未直接覆盖的空间 |
|---|---|---|---|
| [InferCept, 2024](https://proceedings.mlr.press/v235/abhyankar24a.html) / [作者仓库](https://github.com/WukLab/InferCept) | 明确处理 augmented LLM 在外部工具/环境交互时的 interception；实现 Preserve、Swap、Discard，并用 MinWaste 选择。作者报告旧式 serving 把交互当作请求结束会重复计算，重复上下文计算占 forwarding time 的 37–40%。 | 三动作生命周期、基于等待时间和资源浪费的动作选择已经存在；不能再称“首次 retain/offload/recompute”。论文 technique breakdown 也比较了 Discard、Preserve、Swap 和 MinWaste。 | 仓库是旧 vLLM core fork，且 [复现环境 issue #2](https://github.com/WukLab/InferCept/issues/2) 未解决；没有证明其动作/观测接口能在 2026 vLLM 原生 offload 上等价复现。其结果也不是跨硬件的普适阈值。 |
| [Continuum, 2025](https://arxiv.org/html/2511.02230) / [Hugging Face Papers 入口](https://huggingface.co/papers/2511.02230) / [作者 preview code](https://github.com/Hanchenli/vllm-continuum) | 多轮 agent 显式交错 LLM generation 与 tool call；用工具时延经验 CDF 权衡 pin opportunity cost 与避免 prefill/reload/后续排队的收益，为 GPU KV 设置动态 TTL，并联合 program-level scheduling；论文在 SWE-Bench、BFCL、Llama-3.1 8B/70B 上评估。 | “tool duration predictor + dynamic TTL”不是新方向；retention 与 program continuity 已被直接研究。 | README 明确 preview code 不含论文 estimation；[issue #19](https://github.com/Hanchenli/vllm-continuum/issues/19) 指出公开代码用历史均值而非论文经验 CDF。完整 policy 的公开可复现性仍不足，但 tuned TTL 必须成为 ToolGap-KV 强基线。 |
| [Astraea, 2025](https://arxiv.org/html/2512.14142) | 面向 agent 全生命周期 JCT；I/O wait 低压力时 Preserve，高压力时在 Preserve/Discard/Swap 的 memory-waste 中取最小值，并结合 state-aware scheduling。其公式沿用 InferCept：`W_preserve=T_api*C_self*M`、`W_discard=T_recompute*C_batch*M`、`W_swap=2*T_swap*C_batch*M`。 | “I/O wait + memory pressure + dynamic KV action + JCT”已被直接占据；把简单 analytic selector 当贡献不安全。 | 论文没有单独给出 offload-vs-recompute break-even 曲线或 action distribution；ablation 也未干净隔离 cache manager 增益，且未找到官方代码仓库。current-vLLM contract、path attribution 与硬件可迁移阈值仍未被证明。 |
| [ThunderAgent, 2026](https://arxiv.org/abs/2602.13692) / [官方项目页](https://thunderagent.ai/) / [官方仓库](https://github.com/ThunderAgent-org/ThunderAgent) / [NVIDIA Dynamo 官方集成文档](https://docs.nvidia.com/dynamo/user-guides/agents/thunder-agent-program-scheduler) | program-aware agent scheduler；工具执行期间对 acting program 的 KV footprint 施加 exponential time decay，显式平衡 `Cost_caching` 与 `Cost_recompute`；Dynamo 暴露 `acting-decay-tau-seconds` 和 agent tracing。 | time-decay/TTL 类成本权衡、程序级 pause/restore、开源工程实现均已存在。 | 这是 router/program scheduling 取向；不自动回答单机 vLLM native CPU offload 的 D2H/H2D/recompute break-even 与 action attribution。 |
| [KVFlow, 2025](https://arxiv.org/abs/2507.07400) | 将静态 multi-agent execution schedule 抽象为 Agent Step Graph，用 steps-to-execution 指导 radix-tree KV 节点驱逐，并提前从 CPU 向 GPU prefetch。作者报告相对 SGLang hierarchical cache 的 workflow speedup。 | workflow-aware eviction、未来步骤距离、CPU prefetch 已存在；对静态图 workload，简单的 workflow knowledge 是必要强基线。 | 重点是跨 agent 共享 prefix 与静态 workflow，不是同一 session 在不可控 tool gap 中的三动作 break-even。SGLang radix-node 与 vLLM block 语义也不能默认等价。 |
| [PBKV, 2026](https://arxiv.org/html/2605.06472) / [Hugging Face Papers 入口](https://huggingface.co/papers/2605.06472) | 对动态 workflow 预测未来 agent invocation，估计 cache reuse potential，并保守地用于 eviction/prefetch。 | learned/prediction-based lifecycle 与 prediction-error robustness 已被占据；ToolGap-KV 不应以新 predictor 为主贡献。其关键负结果是：aggressive prefetch 在 prediction noise 达 20% 时已被 conservative policy 超过，30% 及以上甚至不如不预取；低并发、几乎不发生 eviction 时，各策略也几乎无差异。 | PBKV 基于 SGLang/HiCache，且未找到公开作者代码仓库；它不直接给出 current vLLM 单 session tool-wait 的传输/重算边界。 |
| [Sutradhara, 2026](https://arxiv.org/abs/2601.12967) | vLLM 上的 orchestrator-engine co-design；包括 tool-aware prompt splitting、streaming tool execution 与 orchestrator-aware cache hints。 | “把 agent/tool 元数据传给引擎改善 KV 命中”本身也不是空白。 | 核心贡献包含 orchestration overlap；没有替代同构三路径的低层机制校准。 |

## 2. 相邻但不能被误当成同一问题的工作

- [I/O-Aware Partial KV Recomputation](https://arxiv.org/abs/2411.17089) 证明 PCIe 可能成为 CPU offload 瓶颈，并把“传一部分 KV”和“从 activation 重算一部分 KV”并行化。这支持“offload 不总优于 recompute”，但场景是长上下文推理的数据搬运，不是 agent tool-wait 生命周期。
- [Understanding Bottlenecks for Efficiently Serving LLM Inference With KV Offloading](https://arxiv.org/abs/2601.19910) 给出 cached-to-prefill ratio 的临界分析，并报告其测试中传输可占绝大多数延迟。它说明硬件 interconnect/模型形态决定结果；不能把某张卡上的阈值外推为 agent workload 的普适结论。
- [MARCONI](https://arxiv.org/abs/2411.19379) 研究 cost-aware prefix-cache admission/eviction；支持“价值不应只由 recency 决定”，但不是 tool call pause/resume。
- [TokenDance](https://arxiv.org/abs/2604.03143) 处理 multi-agent synchronized round 的 collective KV sharing 与压缩，主要消除 sibling cache redundancy，不回答 retain/offload/recompute。

## 3. 已知的负结果与条件依赖

这里不存在一个可信的、跨硬件通用的“offload 一定优于 recompute”结论。primary sources 反而共同表明边界依赖条件：

1. **模型越大，保留收益未必越大。** InferCept 的 13B 单 GPU 结果解释：权重占据更多 HBM、正常 forward 占总延迟更多，留给 interception 优化的空间缩小。这是否定“上下文越贵，retain/offload 总越值”的简单推断。
2. **PCIe/CPU 路径可能主导。** I/O-aware recomputation 与 offloading bottleneck 工作都把传输带宽视为核心限制；因此 `T_restore(bytes) < T_prefill(tokens)` 必须实测，不能由 token 数推断。
3. **批量 onload 会造成 head-of-line blocking。** vLLM [Progressive KV Cache CPU Onloading RFC #33526](https://github.com/vllm-project/vllm/issues/33526) 指出当前整请求 onload 与共享 block 串行限制会让短请求等待长请求；issue 给出的复现实验中 block 传输时间远小于请求观测延迟，说明只量 memcpy 会漏掉调度阻塞。
4. **静态图知识与 duration prediction 都可能失准。** KVFlow 依赖 Agent Step Graph；PBKV 正是为动态调用序列补洞，并采用 conservative use of predictions。PBKV 的 aggressive-prefetch 负结果说明预测噪声达到 20–30% 就可能反转 policy ordering。任何动态策略必须同时报告 predictor error、fallback 与 tuned-static 差距。
5. **高压力下保留会伤害其他请求。** InferCept、Astraea、ThunderAgent 都把 memory pressure/caching cost 纳入决策；因此单 session 的 resume TTFT 提升不能推出系统 goodput/JCT 提升。

尚未找到 primary source 给出一个可直接复用到当前 vLLM、所有模型和 GPU/互连的 closed-form universal break-even。已知的是**成本项和方向**，不是通用常数。

## 4. vLLM 原生能力与 contract 风险（截至 2026-07-12）

### CPU offload：机制已进入主线，但不是完整 agent policy

- [vLLM KV cache offloading RFC #19854](https://github.com/vllm-project/vllm/issues/19854) 定义基于 KV connector 的原生 CPU offload 架构。
- [PR #37874](https://github.com/vllm-project/vllm/pull/37874) 合入 pluggable CPU offload `CachePolicy` 结构；后续 release 继续加入 per-request policy hook、selective offload 与 tiering（应在 pin commit 时再次核对 [官方 releases](https://github.com/vllm-project/vllm/releases)）。
- [Selective KV Cache offload RFC #39305](https://github.com/vllm-project/vllm/issues/39305) 与 [multi-tier RFC #38260](https://github.com/vllm-project/vllm/issues/38260) 表明数据面仍在快速演进。

结论：实现“CPU 存一份并恢复”不构成项目贡献。可研究的是 pinned build 上 store 完成语义、GPU copy invalidation、restore attribution、queue/transfer 分解，以及 policy hook 能否表达 agent lifecycle。

### retention：需求明确，稳定 contract 仍不足

- [Context-Aware Retention RFC #37003](https://github.com/vllm-project/vllm/issues/37003) 直接以 agent tool-call pause 后 LRU 驱逐为动机，提出 token-range priority/duration；这进一步证明 ToolGap-KV 的问题不是新发现。
- 对应 [PR #38514](https://github.com/vllm-project/vllm/pull/38514) 曾实现并带测试/benchmark，但已关闭未合入。因此不能把 duration/priority retention 当 current mainline 稳定 API。
- [Active Coordination and Two-Zone Scheduling RFC #37168](https://github.com/vllm-project/vllm/issues/37168) 是更直接的 long-running-agent 上游相邻设计，实施前必须纳入 hook-capability matrix。

结论：最小 retention compatibility layer 或可审计 upstream contract 仍可能有工程价值；但 RFC/PR 本身已经占据 API 设计方向，项目需要证明缺失 contract，而不是换名重做。

## 5. Experiment 0001 是否重复

### 判定

**作为研究结论：重复且过弱。作为集成 gate：不重复，且必须保留。**

InferCept/Astraea 已证明三种动作有系统意义；vLLM 也已有 CPU offload。仅展示三条路径能跑通，不能成为论文、简历主成果或“experimentally validated policy”。但在同一模型、prompt、HBM budget、server flags 下，证明 requested action 等于 observed action，并把 queue / D2H / H2D / prefill / TTFT 分开，仍是后续任何比较的可信性前提。现有论文结果不能替代目标 commit 的 contract 验证。

### 建议改为两层交付

**0001A — Mechanism conformance（保留现有目标）**

- 强制 `gpu_hit / cpu_restore / recompute`；
- 同时证明 GPU miss/CPU hit、GPU miss/CPU miss、异步 store/restore completion；
- 记录 exact commit、patch hash、block/token accounting、output hash；
- 结果只标记 `shipped` 或 target environment 下的机制 `experimentally validated`，不声称策略收益。

**0001B — Cost-surface calibration（新增，才决定项目 go/no-go）**

- 变量至少包含 context tokens、KV bytes、PCIe/C2C 类型、HBM pressure、并发数、tool-gap 分布；
- 输出 `T_prefill(tokens)`、`T_store(bytes)`、`T_restore(bytes)`、queue delay 与 resume TTFT，而不是只给端到端均值；
- 基线至少为 recompute、always-retain、always-offload、tuned static TTL、InferCept/MinWaste-inspired analytic policy；若进入 workflow 预测，再加 KVFlow/PBKV-inspired，并明确 fidelity level；
- 报告动态策略相对 **per-workload tuned TTL**、small-instance hindsight bound 的 regret，而非只相对 LRU；
- 专门保留负区域：短 context/慢 PCIe、低压力、极长或高方差 tool gap、高并发/HOL blocking、predictor error。

### 硬停止线

若 0001B 显示：

1. tuned TTL 在所有可达 workload 上都接近 hindsight；或
2. 一个动作在所有可达硬件/压力下占优；或
3. current vLLM 无法可靠观测/强制动作，且修复需要大面积 fork；

则应终止“新动态策略”主线。可以把交付收缩为 vLLM lifecycle conformance suite、break-even/失败域数据集，或一个有明确 missing contract 的 upstream contribution。

## 6. 可辩护的项目表述

不安全：

> 首个在工具等待期间动态选择 retain/offload/recompute 的 agent KV 系统。

仍可能安全，但必须由仓库 artifact 与 GPU 数据支撑：

> 在 pinned current-vLLM 上构建可归因的 agent KV lifecycle conformance harness，并测量 retain/CPU restore/recompute 在不同上下文、互连、内存压力、并发与 tool-gap 分布下的决策边界；以 tuned TTL 和已有策略为强基线，公开动态策略失效区域。

最有防御力的科学问题不是“动态策略是否能赢”，而是：

> **已有策略的结论能否跨 engine contract、cache granularity、offload implementation 与硬件互连迁移？哪些成本或调度项导致 paper ordering 在 current vLLM 上反转？**

这会把项目从重复造一个 selector，转为复现性、可迁移性和 failure-domain 研究。

## 7. 检索局限

- 本审查覆盖任务指定的 InferCept、Continuum、PBKV、Astraea、KVFlow、vLLM upstream，并补充 ThunderAgent、Sutradhara 和两项 offload/recompute 工作；不能声称穷尽 2026-07-12 当日所有预印本。
- Hugging Face Hub 的模型/Space 搜索不是这类系统结论的权威索引；关键证据最终都需要回到论文、作者仓库和 engine upstream。此次未发现 Hugging Face 自己发布一个可替代上述系统的官方 agent tool-gap 三动作结论。
- 所有论文 speedup/JCT 数字只代表其声明的环境，本文未在 ToolGap-KV 中复验；其状态不能升级为本项目的 `experimentally validated`。
