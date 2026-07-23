# 从对象存储数据面迁移到 KV Serving：项目方向调研

> 日期：2026-07-19
> 状态：research input / roadmap，不代表已实现、已验证或已有性能结果。
> 目标：判断对象存储数据面实习经验如何转译为 LLM Serving / KV Cache 的可验证招聘证据。

## 结论

方向值得做，但需要 `reshape`。

不建议把后续项目定义为“实现 Mooncake、PD 分离、KV 分层、冷热迁移”。这是多个各自足以成为项目的系统问题，而且完整 Mooncake 的证据环境依赖多节点 GPU、高速网络和真实规模负载，超出当前单卡条件。

建议在 ToolGap-KV 的 CT1-CT3 完成之后，另起一个独立项目，主问题收敛为：

> 在长上下文/Agent 前缀复用场景中，后台 KV 写入对象层与前台 KV 恢复争用有限的 CPU、网络和 I/O 资源时，SLO-aware 的传输准入和优先级控制，能否比原生 store-all 级联策略获得更好的 Goodput@SLO，并保持明确的失效边界？

这个方向连接了三段证据：对象存储实习中的队列、背压、尾延迟和部分失败；ToolGap-KV 中的逻辑生命周期与异步完成 fencing；后续项目中的物理 KV 数据移动与 serving SLO。

## 为什么“只接对象存储”不够

vLLM 当前的 `OffloadingConnector` 已支持 CPU 主层和多个二级层；二级层包含文件系统、S3-compatible object store（NIXL OBJ）以及 P2P/RDMA。GPU 与二级层之间经 CPU 主层中转，并已有每请求 `max_offload_tokens` 等配置。因此，一个普通 object-store adapter 更像已有能力的重复实现，而不是独立的 serving 决策。

当前 tiering manager 的公开实现会将保存级联到所有二级层，并通过 CPU 主层完成 staged promotion。公开的 object-tier manager 代码暴露了异步传输和一个统一 `io_threads` 配置；从该公开代码尚未看到面向 active decode 的读写优先级或按收益进行的写入准入。这里是候选切口，但必须先做源码 Gate：确认接口、队列和缺失机制，不能仅凭文档推断实现空白。

## 一手系统给出的边界

### Mooncake

Mooncake 是 KVCache-centric 的 PD 分离 serving 系统：将 KV 放进 CPU DRAM、SSD 和 RDMA 连接的分布式池，并由调度器综合缓存复用、负载和 TTFT/TBT SLO。论文也展示了 cache skew、热点复制和迁移对传输拥塞的影响。

可迁移的是问题与抽象：复用价值、位置、传输成本、热点、SLO 和故障之间的联合决策。不可直接迁移的是其规模结论：论文的多节点集群与高速互连结果不能作为单卡/普通网络项目的性能主张。

Mooncake Store 的公开设计还提供了适合学习的数据面原语：不可变 KV、元数据与数据路径分离、lease、pin、近似 LRU、zombie cleanup、preferred placement、RAM/SSD 两层存储。这些是设计参考，不是需要全部复刻的功能清单。

### LMCache

LMCache 已经覆盖 GPU/CPU/本地/远端多层 KV、持久化与跨请求复用，并具有 controller、move、pin/unpin 等机制。后续项目若只是做通用多层缓存或远端传输，会很容易变成 LMCache 的缩小版；必须用明确的控制决策和反事实基线区分。

### vLLM PD 分离

vLLM 的 disaggregated prefilling 仍明确标为 experimental，并列出 NIXL、LMCache、Mooncake 等 connector。它适合用来研究独立调节 TTFT/ITL 和控制 decode 尾延迟，但真正证明 PD 调度与跨节点传输通常需要至少两个 GPU worker 和可解释的网络环境。当前阶段应把 PD 当成未来实验环境，而不是下一项目的必需前提。

## 对象存储经验中最值得主动争取的内容

### P0：直接迁移到 serving 数据面的能力

1. 传输队列、并发窗口、背压、带宽准入、前后台或读写优先级。
2. 异步迁移状态机：copy、提交/切换、epoch/fencing、重试、取消、超时、清理和迟到完成。
3. 尾延迟诊断：排队、序列化、网络、介质、回调各阶段的可观测性和归因。
4. 部分失败与降级：远端慢、超时、成功未知、重复请求、资源泄漏时如何安全回到 recompute。

### P1：有价值，但要与 serving 指标绑定

1. 热冷准入、提升/降级、TTL、逐出和 write amplification。
2. placement、热点复制、本地性、分片和负载均衡。
3. buffer pool、pinned memory、NUMA、zero-copy、批处理和 multi-NIC。
4. fault injection、限速、拥塞模拟以及 per-stage tracing。

### 低信号内容

1. 只实现 S3 CRUD、接口胶水或部署配置。
2. 与 KV 热路径没有因果关系的通用控制面封装。
3. 只讲纠删码、耐久性或容量，而没有 owning serving latency/cost decision。
4. 复刻整套 Mooncake/LMCache，或在缺少硬件时把多节点/RDMA 写成已验证能力。

## 迁移类比会在哪里失效

| 对象存储数据 | 推理 KV Cache |
|---|---|
| 通常是权威、耐久数据 | 派生且通常可重算 |
| 优先耐久性、容量、吞吐与成本 | 优先 TTFT、TPOT/ITL、Goodput 和 GPU hot path |
| 写入成功常有持久语义 | 远端写入可能随请求取消而失去价值 |
| 远端读取通常是功能要求 | 若 restore 比 recompute 更慢，应直接放弃复用 |
| 对象 key 足以定位数据 | KV identity 还受模型、tokenizer、模板、dtype、并行配置等约束 |
| 常见对象粒度较大 | KV block 粒度更细、元数据基数更高 |
| 故障目标偏修复和恢复 | 很多故障的正确策略是 discard + recompute |

因此，最重要的思维转换不是“把对象存储搬过来”，而是把 KV 当成**有重算成本、有限时效和 serving SLO 的派生对象**。

## 推荐项目：SLO-aware KV Transfer Admission

### 最小可信实现

只拥有一个 controller：

1. 对 CPU -> object 的后台写入做收益准入，而不是保存所有候选 KV。
2. 给 object -> CPU 的前台 promotion 更高优先级，并限制后台 inflight。
3. 在远端慢或队列饱和时停止写入/恢复，安全回退到 recompute。
4. 输出 DecisionTrace：为什么保存、跳过、提升、取消或回退。

第一版不做通用分布式元数据服务、不做自定义存储协议、不做完整 PD scheduler，也不把 eviction/GC、热点复制和动态 placement 全部塞进 MVP。

### Gate S：先证明扩展点成立

在正式实现前，用固定 vLLM commit 做 1-2 周源码 spike：

1. 定位 object tier 的保存、恢复、异步 job 和队列路径。
2. 确认是否能通过 custom spec/manager 实现准入和优先级；否则只接受一个窄小、可审计的 upstream patch。
3. 验证能观测 queue dwell、inflight、PUT/GET bytes、完成/失败和 fallback。
4. 若必须广泛 fork engine core，或无法把 controller 与存储后端解耦，则停止该方向，不为“做项目”硬造框架。

### 对照组

1. vLLM 原生多层 offload + object secondary tier（store-all cascade）。
2. CPU-only offload。
3. no offload / recompute。
4. 固定并发上限，用来证明收益不是单纯限流。

### 工作负载

1. 高复用：重复长前缀、多轮 Agent session、burst resume。
2. 低复用：唯一短 prompt，证明 controller 应关闭或跳过远端层。
3. 高取消：保存完成前请求结束，测无效写入和迟到完成。
4. 慢远端/拥塞：注入延迟、限速和失败，测 active decode 干扰与回退。

### 指标

- TTFT p50/p95/p99。
- TPOT 或 ITL p95/p99，尤其是有 active decode 时。
- Goodput@SLO，而不是只看平均吞吐。
- KV hit tokens、avoided prefill tokens 和 recompute cost。
- PUT/GET ops 与 bytes、queue dwell、inflight、write amplification。
- object bytes、取消后无效写、失败/超时/fallback 数量。

### 最关键的负结果

当复用概率低、KV 很快失效、远端 restore 慢于 recompute，或后台写入伤害 active decode 时，对象层应该被禁用。能精确画出这个 break-even boundary，比只报告一个最优 case 更有招聘价值。

## 项目评价

- **Verdict**：大方向 `reshape`；完成 ToolGap-KV CT1-CT3 且 Gate S 通过后，窄化项目 `select`。
- **目标岗位**：2027 校招 LLM Serving / inference platform / AI Infra，偏 KV、调度、数据面，不以 kernel/operator 为主线。
- **现有优势**：对象存储生产数据面的队列、背压、失败和尾延迟经验；ToolGap-KV 的逻辑生命周期/异步正确性。
- **当前状态**：roadmap，没有实现和测量，不能写性能 bullet。
- **最弱环节**：尚未证明 vLLM 扩展点、单卡环境下的真实争用，以及 controller 的独立所有权。
- **条件可行性**：单 GPU + CPU + 独立 S3-compatible endpoint 可以证明控制机制；本机 MinIO 只能算功能/受控实验，不能包装成远端生产性能。
- **延后项**：完整 PD、跨节点 RDMA、全局热点复制和 Mooncake-class conductor。

面试中的核心因果链应是：

> 可复用的长前缀 KV -> 原生 store-all 产生后台写入 -> 有限 CPU/网络/I/O 队列与前台恢复和 active decode 争用 -> controller 做收益准入、优先级和回退 -> 用 tail latency、Goodput 与负结果证明适用边界。

## 招聘叙事与占位简历条目

三段经历应互相递进，而不是堆关键词：

1. 火山引擎对象存储数据面：真实生产系统的传输、背压、尾延迟和部分失败。
2. ToolGap-KV：候选人拥有的 KV 逻辑生命周期、正确性、恢复和 DecisionTrace。
3. Transfer Admission 项目：KV 物理数据移动如何受 serving SLO 约束。

在没有数据前只能写占位版本：

> 针对长上下文/Agent 复用场景下后台 KV 写入与前台恢复竞争，在固定 vLLM 版本中实现 SLO-aware KV transfer admission controller；相较原生 store-all 多级 offload、CPU-only 与 recompute，在 `[环境]` 下实现 TTFT p99 `[x]`、active TPOT p99 `[y]`、Goodput@SLO `[z]`，并给出低复用、高取消和慢远端下的关闭边界。

`[x/y/z]` 在实验完成前不得替换成推测数字。

## 推荐阅读顺序

1. vLLM KV Offloading Usage：先知道现有能力，避免重复造 adapter。
2. vLLM Tiering Manager 与 OBJ Manager 源码：寻找真实扩展 seam 和队列语义。
3. Mooncake paper 的架构、cache-centric scheduler、缓存画像和评测部分。
4. Mooncake Store design 的 lease、eviction、zombie cleanup、placement 与 tiering。
5. LMCache architecture：明确已经存在的通用多层缓存能力。
6. 最后才考虑 vLLM disaggregated prefilling，把 PD 当实验放大器而不是项目定义。

## 一手来源

- [vLLM KV Offloading Usage Guide](https://docs.vllm.ai/en/latest/features/kv_offloading_usage/)
- [vLLM TieringOffloadingManager API/source](https://docs.vllm.ai/en/latest/api/vllm/v1/kv_offload/tiering/manager/)
- [vLLM ObjectStoreSecondaryTierManager API/source](https://docs.vllm.ai/en/latest/api/vllm/v1/kv_offload/tiering/obj/manager/)
- [vLLM Disaggregated Prefilling](https://docs.vllm.ai/en/stable/features/disagg_prefill/)
- [Mooncake paper: A KVCache-centric Disaggregated Architecture for LLM Serving](https://arxiv.org/abs/2407.00079)
- [Mooncake Store design](https://github.com/kvcache-ai/Mooncake/blob/main/docs/source/design/mooncake-store.md)
- [LMCache architecture](https://docs.lmcache.ai/developer_guide/architecture.html)
