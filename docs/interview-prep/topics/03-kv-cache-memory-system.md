# 03｜KV Cache 与内存系统详细知识列表

> 优先级：P0
>
> 当前状态：已建立动机和 block 化直觉；容量、源码、系统手撕与实验未完成
>
> 目标熟练度：原理 L3 / 源码 L3 / 手写 L3 / 实验 L3
>
> 依赖：[Transformer 推理原理与手撕](02-transformer-inference-and-handwriting.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能把 KV Cache 从“Attention 的缓存数组”提升为完整的 Serving 内存系统：能够手算容量、解释 block/page 布局、追踪请求生命周期、处理前缀共享和引用、设计驱逐与 offload/recompute 边界、分析异步失败，并沿固定版本 vLLM 源码说明哪些状态由谁拥有。

本主题与 ToolGap-KV 直接相关，因此四个维度都要求 L3。文档理解不能替代真实源码、手写、测试和实验。

## 当前基础与缺口

已有个人笔记证明以下直觉曾经建立：

- Decode 会重复使用历史 K/V，缓存以显存换计算；
- 上下文、输出长度、并发和模型规模会扩大 KV 压力；
- fixed-size block 缓解连续扩容、外部碎片和动态请求管理问题；
- Block Table 维护逻辑到物理映射，PagedAttention 消费非连续物理 block。

但当前不能视为已经掌握：

- 旧知识表中的 block 化条目曾标记 L2，但没有近期闭卷复述或实现证据；
- 容量模型仍停留在旧的 L1 学习记录，面试题标准答案为空；
- 分配、共享、回收、驱逐和 Prefix Cache 场景题尚未作答；
- Block Manager 手撕题尚未实现；
- 没有固定版本 vLLM 源码路径和真实 GPU 实验。

## 职责边界

| 层次 | 本知识地图中的职责 |
|---|---|
| Transformer | K/V 如何从 hidden states 产生，以及如何参与 Attention |
| KV Cache 与内存系统 | 容量、布局、分配、共享、回收、驱逐、迁移和正确性 |
| vLLM 物理数据面 | block residency/refcount、PagedAttention、模型执行和原生数据搬运 |
| ToolGap-KV | 候选人拥有的逻辑生命周期、epoch、动作编排、fallback、取消、清理和 DecisionTrace |

手写 toy Block Manager 是学习证据，不等于已经修改 vLLM；ToolGap-KV 文档是 `roadmap`，不等于生命周期 runtime 已经 `shipped`。

## 源码与复现契约

### 触发依据

- **真题证据门槛已触发**：现有题库多次出现 PagedAttention 原理与 vLLM PagedAttention，并出现 Block Manager 核心逻辑手写；这证明不能只背“分页减少碎片”的概念答案。但当前证据不等于每一道 PagedAttention 题都会追问生产源码。
- **核心模块门槛已触发**：block table、物理块分配、共享引用和 Attention 读取路径共同构成 LLM Serving 的核心内存数据面，也是 ToolGap-KV 必须正确复用和划分所有权的依赖。

### 主实现与条件式对比

- **主实现：vLLM**。开始训练时固定一个 release/commit，以该版本的 scheduler、KV cache manager、block pool、attention metadata/kernel interface 和 connector 为真实锚点；不背诵跨版本类名。
- **对比实现：SGLang RadixAttention，按需加入**。只比较前缀如何组织、匹配、共享和驱逐，以及这些选择与 vLLM Prefix Cache 的 trade-off；不要求把 SGLang 全部 KV 路径再精读一遍，也不把 RadixAttention 与 PagedAttention 当成互相替代的同一层机制。
- 只有目标 JD 明确要求 SGLang、真题直接拷问其源码，或对比能够回答具体设计问题时，SGLang 才升级为必修完成项。

### 双层本地复现

1. **机制复现**：实现 toy block pool、free queue、block table、引用计数、Copy-on-Write、OOM rollback 和取消清理；再写 block table 驱动的逻辑 K/V gather 或 Attention 伪实现。
2. **真实映射**：在固定版本 vLLM 上运行/trace 一次请求从调度、block 分配、Attention 消费到完成释放的路径，并验证 Prefix Cache hit/miss、输出等价和容量清理。

完成标准：能够从入口沿真实对象解释所有权、控制流、数据流、不变量和 trade-off；留下固定 commit、源码路径图、toy 代码及测试、真实命令、原始结果和至少一个失败/负面案例。

明确不要求：从零手写 PagedAttention CUDA/Triton kernel。非算子岗位需要讲清 kernel 接口、block table/metadata 如何到达 kernel、逻辑到物理寻址代价和主要性能瓶颈。

## P0 详细知识列表

### 容量与形状模型

- 单层 K/V 的逻辑形状；
- 层数、总缓存 token 数、KV head 数、head dimension 和 dtype bytes；
- 基础容量公式：`2 × layers × cached_tokens × kv_heads × head_dim × dtype_bytes`；
- batch 上界公式与实际变长请求总 token 公式的区别；
- MHA/MQA/GQA 对 KV 容量的影响；
- MLA 的 latent cache 与普通 K/V cache 在每 token 表示、RoPE 状态和容量公式上的差异；
- Tensor Parallel 后每 rank 的 KV 分片边界；
- block/page 分配、尾部内部碎片和元数据开销；
- 模型权重、激活、CUDA graph 与 KV 预算之间的显存竞争；
- 混合 Attention/滑动窗口模型使简单公式失真的原因。

通过标准：能在 10-15 分钟内完成给定配置的每 token、每请求、每 block、每卡容量手算，并明确公式假设。

### 连续布局、block 与 PagedAttention

- 请求长度不可预知时连续预分配、按需扩容和重新复制的代价；
- 内部碎片与外部碎片；
- logical block、physical block、block ID、block table；
- free block pool/queue 与按需分配；
- block size 对尾部浪费、元数据、哈希粒度和访存的 trade-off；
- PagedAttention 如何根据 block table 读取逻辑连续、物理离散的 K/V；
- KV block 与 CUDA thread block 不是同一概念；
- PagedAttention 内存管理思想与具体 GPU kernel 的职责边界。

### 请求生命周期与所有权

- allocate、append/grow、touch、free、evict 的基本路径；
- request、sequence、prefix、logical lifecycle 与 physical block 的身份差异；
- block table 的增长和请求结束清理；
- 引用计数保护仍在使用或共享的 block；
- 共享前缀分叉后的 Copy-on-Write 边界；
- 取消、超时、异常和进程退出时的资源清理；
- duplicate free、double resume、late completion 的幂等性；
- capacity 是否回到基线的泄漏检查。

### Prefix Cache 与复用

- 普通 decode KV Cache 与跨请求 Prefix Cache 的区别；
- 前缀命中的 key 必须包含 token 内容和兼容的模型/runtime 身份；
- block hash/match unit、父前缀与链式身份；
- 区分前缀匹配粒度与物理 KV block 大小，并以固定版本实现为准；
- hash 碰撞、跨进程可复现性和多租户安全边界；
- 命中 block 的引用、共享、触碰和驱逐保护；
- Prefix Cache 主要减少重复 Prefill，不直接减少新 token Decode；
- 命中率、复用 token 数、TTFT、吞吐和容量占用的联合评估；
- 路由到有缓存 worker 与路由到低负载 worker 的冲突。

### Retain、Offload、Restore 与 Recompute

- GPU retain、CPU offload/restore、recompute 的动作语义；
- KV bytes、有效传输带宽、排队、同步和分块开销；
- recompute 的 token 数、Prefill 吞吐和调度等待；
- Restore 与 Recompute 的 break-even 模型；
- 异步 DMA、compute/transfer overlap 和真实尾延迟；
- HBM/CPU tier 容量水位、驱逐和回退；
- selective offload：共享长前缀与请求私有 decode token 的价值不同；
- 未命中、部分数据、传输失败时回到权威 token 历史重新计算。

### 正确性与异步失败

- KV 是由 token history 和兼容 runtime 配置派生的可重算状态；
- model、adapter、tokenizer、RoPE/position、dtype/layout 等兼容性边界；
- partial store/load 不得成为可复用完成态；
- lifecycle identity 与 monotonic epoch；
- 取消期间完成、旧 epoch 完成和重复完成的 fencing；
- requested action、observed action、fallback reason 分离；
- failed materialization 不可见，安全终态是显式失败或 recompute；
- 输出等价、引用归零和容量回收共同构成正确性证据。

### 调度与可观测性

- KV capacity 与 scheduler admission/preemption 的关系；
- waiting/running/resumed 请求对 block 的不同需求；
- cache hit、matched tokens、recomputed tokens；
- store/restore queue depth、bytes、bandwidth 和等待时间；
- Prefill、restore、queue、first token 时间拆分；
- active request 与 resumed request 的 p50/p95/p99；
- requested/observed/fallback 的 DecisionTrace；
- 只测平均 TTFT 无法证明系统设计正确。

## P1 补充

- cache-aware + load-aware 多 worker 路由；
- 分布式 KV 的分片、所有权、路由、一致性和回源；
- Prefill/Decode disaggregation 与 KV transfer connector；
- GPU、CPU、SSD、远端内存的多级缓存；
- KV Cache FP8/INT8 量化、scale 和质量校验；
- 多进程 hash 一致性与跨实例 Prefix Cache；
- sliding-window、cross-attention、hybrid model 的多种 KV cache spec；
- 公平的 TTL/LRU/ARC 或 action-only baseline。

### MLA 缓存表示防守子集

> 子集目标：原理 L2 / 源码 L1 / 手写 L0 / 实验 L0
>
> 建议投入：与 Topic 02 的 MLA 模型语义共享 3-5 小时，不增加 Topic 03 的领域手撕或实验验收项。

需要从 KV 内存系统视角补全以下边界：

- 普通 MHA/GQA 缓存完整或按 KV heads 缩减的 K/V，MLA 缓存低维 latent state 与单独保留的 RoPE 相关状态；
- 容量比较必须写明模型配置、latent dimension、RoPE dimension、dtype、层数和 token 数，不能直接套用普通 `2 × kv_heads × head_dim` 公式；
- 矩阵吸收改变 Decode 对缓存状态的读取与计算路径，但不改变 cache 仍需具备 position、model revision、dtype/layout 等兼容身份；
- block allocator 可以复用相同的生命周期原则，但每层 cache spec、block bytes、layout 和 Attention backend contract 可能不同；
- Prefix Cache、offload、restore 或跨实例传输必须保持 MLA cache representation 与目标执行路径兼容，不能只验证 token IDs 相同；
- 混合层模型可能同时拥有 full attention、sliding-window 和 MLA 等不同 cache spec，容量与 block 规划必须按实际层类型累计。

源码只要求沿一个固定版本定位模型配置到 cache spec、分配尺寸、Attention metadata 和 Decode cache read 的主要连接点。通过标准是能够画出普通 K/V 与 MLA latent cache 的物理表示差异，并解释一次兼容性拒绝场景。

明确不要求修改 Block Manager、手写 MLA cache manager、运行 MLA benchmark 或精读 FlashMLA kernel。没有模型兼容性实现、真实运行和验证产物时，ToolGap-KV 的 MLA 支持只能是 `roadmap`，不能标记为 `shipped` 或 `experimentally validated`。

## P2 延后

- 手写 PagedAttention CUDA/Triton kernel；
- RDMA/NIXL 协议和 NIC/GPU direct path 的底层实现；
- 生产级分布式 KV Store；
- 多节点故障域和跨地域一致性；
- 未通过 ToolGap-KV Gate B 就提前实现动态策略 CT4。

## 训练顺序与验收

### A. 容量模型

必须完成：

1. 写出 KV Cache 容量公式和全部变量；
2. 分别计算 MHA、GQA、MQA；
3. 从 batch 上界改写为变长请求总 token；
4. 计算一个 block 和尾部碎片；
5. 写一个容量计算器，并用手算样例测试。

通过标准：公式、代码和实际 tensor `numel × element_size` 三者一致；能说明 block 元数据和 allocator 开销为什么不在基础公式内。

### B. Toy Block Manager

必须实现：

1. 固定 block pool 与 free queue；
2. request 到 physical block IDs 的 block table；
3. allocate/append/free；
4. 引用计数与共享前缀；
5. 分叉写入时的 Copy-on-Write；
6. OOM、取消和异常清理；
7. 不变量检查：无重复分配、无负 refcount、终态容量回到基线。

通过标准：60 分钟完成给定接口的核心逻辑，随后用测试覆盖共享、扩容、释放、OOM rollback、duplicate free 和 cancellation。

### C. Prefix Cache 索引

必须完成：

1. 按 fixed-size token blocks 计算链式 key；
2. 查找最长完整 block 前缀；
3. 命中后增加引用并构造 block table；
4. LRU 或明确的 free queue 驱逐顺序；
5. 模型/adapter/位置配置不兼容时拒绝复用；
6. 命中率、复用 token 和 eviction 指标。

通过标准：能够解释为什么 Prefix Cache 不是字符串缓存，以及为什么 token 相同但 runtime identity 不兼容时仍不能复用。

### D. 生命周期与失败状态机

必须完成：

1. requested、in-flight、observed、fallback、terminal 状态；
2. lifecycle claim 与 epoch；
3. late/duplicate completion fencing；
4. restore failure 到 recompute；
5. cancellation 与 cleanup；
6. DecisionTrace。

通过标准：状态转移测试和 deterministic fault test 通过；删除/绕过候选人 controller 后，相应行为必须消失，而不是只少了日志。

### E. 真实源码与实验

必须完成：

1. 固定 vLLM release/commit；
2. 沿 scheduler、KV cache manager、block pool、attention 和 connector 画所有权图；
3. trace 一次请求从调度、block 分配、attention metadata/kernel interface 到完成释放的路径；
4. 记录当前版本的真实类、方法和数据流，不依赖旧博客命名；
5. 比较 Prefix Cache hit/miss 的复用 token、TTFT 和输出；
6. 比较不同 block size 的容量浪费与运行指标；
7. 在真实路径测 retain/offload/recompute 的一条 break-even 或 dominance 边界；
8. 注入一次 restore/cancellation 失败并证明输出或显式终态、清理和容量正确。

通过标准：每个结论都有固定版本、命令、原始结果和适用边界；没有 GPU 证据时保持 `roadmap` 或 `simulated`。

## 必须通过的领域手撕

| 题目 | 时间限制 | 最低要求 |
|---|---:|---|
| KV Cache 容量计算器 | 15 分钟 | 公式、GQA、dtype 和假设正确 |
| 连续 KV Cache append/预分配 | 30 分钟 | 更新、位置、容量和输出正确 |
| Block Table 与 block allocator | 45 分钟 | 分配、增长、回收和 OOM rollback |
| 引用计数与 Copy-on-Write | 45 分钟 | 共享、分叉写、释放不变量正确 |
| 简化 Block Manager | 60 分钟 | pool、table、refcount、清理和测试完整 |
| Prefix Cache 索引 | 60 分钟 | 链式 key、最长命中、引用和驱逐正确 |
| KV 生命周期状态机 | 60 分钟 | epoch、幂等、失败、取消和 cleanup 正确 |

不要求手写 PagedAttention GPU kernel。面试中若要求“大概原理代码”，可以手写 block table 驱动的逻辑 gather/attention 伪实现，并明确它不是高性能 kernel。

## 原理连续追问

### 容量与布局

- 给定模型配置，KV Cache 每 token 和总容量如何计算？
- 为什么 `batch × max_seq_len` 常常高估或误导实际变长服务？
- block size 变大会改善什么、恶化什么？
- 内部碎片和外部碎片在 KV 管理中分别是什么？
- 为什么逻辑连续可以建立在物理不连续 block 上？
- 为什么 MLA 不能直接套用普通 MHA/GQA 的 KV 容量公式？latent cache 还必须保留哪些位置相关状态？

### Prefix Cache 与生命周期

- 普通 KV Cache 与 Prefix Cache 有何区别？
- block hash 应包含哪些身份？为什么只有 token IDs 不够？
- 命中 block 为什么仍可能在 free/eviction queue 中？
- 引用计数与 Copy-on-Write 分别保护什么？
- 请求取消或失败时如何证明没有 block 泄漏？
- stale completion 为什么可能释放或复活错误的 block？

### Offload 与系统设计

- 什么条件下 restore 比 recompute 更差？
- 异步传输为什么仍可能恶化 active decode 的 p99？
- Prefix Cache 为什么主要优化 Prefill，不直接优化 Decode？
- cache-aware routing 为什么不能只追求命中率？
- CPU/SSD/remote tier 的容量提升分别引入哪些延迟与故障模式？
- 如何区分 requested action、observed path 和 fallback？

### 源码与项目

- 当前固定版本 vLLM 中，scheduler、KV manager、block pool、attention 和 connector 分别拥有哪部分状态？
- 为什么 ToolGap-KV 复用 vLLM physical data plane，而不是重写 Block Manager？
- 什么证据才能证明候选人真的拥有 lifecycle semantics，而不只是加了日志？
- 哪个缺失 contract 才足以证明需要 core patch？

## 与 ToolGap-KV 的连接

### CT1：集成边界

- 固定当前 vLLM 版本并审计最小扩展点；
- 候选人 runtime 必须拥有真实 lifecycle transition 或 fallback；
- ordinary requests 保持默认路径；
- controller removal/bypass test 证明拥有行为，而不是只拥有 trace。

### CT2：正确性与恢复

- cache identity、epoch、shared block 与 logical claim 分离；
- partial restore、late completion、duplicate resume、cancellation；
- failed materialization 不可见；
- recompute 或显式 failure；
- 输出、引用和容量清理共同验收。

### CT3：定量边界

- retain/offload/recompute 比较；
- context/KV size × transfer/recompute ratio × 一个压力条件；
- queue/store/restore/prefill/first-token 分解；
- 一条 winning boundary 和一条 losing workload；
- raw runs、环境、重复和 exact command。

CT4 动态策略只有 Gate B 通过后才能进入知识实践主线。

## 完成证据

- KV 容量计算器和测试；
- toy Block Manager、Prefix Cache 与生命周期状态机；
- 引用、COW、OOM、取消和 stale completion 的测试；
- 固定版本 vLLM 所有权与源码路径图；
- Prefix Cache hit/miss 实验；
- retain/offload/recompute 边界实验；
- 一次故障注入和容量回收证明；
- 一次 60 分钟系统手撕；
- 一次 30 分钟源码/系统连续追问；
- ToolGap-KV 的 claim state 与仓库证据一致。

## 现有个人笔记与真题

- [KV Cache 主笔记](https://app.notion.com/p/3735d315c09080c7bf8dee117009caa9)
- [Transformer 推理与 KV Cache 阶段学习记录](https://app.notion.com/p/3415d315c09081228447d3c7b927ac16)
- [block 化管理 KV Cache](https://app.notion.com/p/3415d315c0908128a097d30049319454)
- [KV Cache 显存占用模型](https://app.notion.com/p/33c5d315c0908181a97cdb6ec403825b)
- [KV Cache 的形状与显存占用如何计算](https://app.notion.com/p/39d5d315c090818d8076d6ff70e90b61)
- [推理服务中的 KV Cache 如何分配、复用、回收与驱逐](https://app.notion.com/p/39e5d315c090810aa65ee02d11b11aec)
- [PagedAttention 的核心原理是什么，解决了什么内存问题](https://app.notion.com/p/39d5d315c09081f29cbde3673af2af6b)
- [vLLM PagedAttention 面试记录](https://app.notion.com/p/39d5d315c090819fa254c19c27d9af6c)
- [手写 KV Cache / PagedAttention Block Manager 的核心逻辑](https://app.notion.com/p/39d5d315c09081d399bdfb48542ed90d)
- [如何提高 KV Cache 命中率，并用树结构、Routing 与 Replay 管理复用](https://app.notion.com/p/39d5d315c090813ea1a2ec8028423ecc)

## 当前 vLLM 官方参考

以下 latest/stable 页面只用于定位当前概念。开始源码学习和项目实现前必须固定具体 release/commit。

- [vLLM BlockPool API](https://docs.vllm.ai/en/stable/api/vllm/v1/core/block_pool/)
- [vLLM KV cache interface](https://docs.vllm.ai/en/latest/api/vllm/v1/kv_cache_interface/)
- [vLLM Automatic Prefix Caching](https://docs.vllm.ai/en/v0.22.1/features/automatic_prefix_caching/)
- [vLLM KV Offloading Usage Guide](https://docs.vllm.ai/en/v0.25.0/features/kv_offloading_usage/)
- [vLLM OffloadingManager API](https://docs.vllm.ai/en/latest/api/vllm/v1/kv_offload/base/)
- [SGLang repository（RadixAttention 条件式对比入口）](https://github.com/sgl-project/sglang)
