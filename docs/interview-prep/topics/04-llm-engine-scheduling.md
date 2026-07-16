# 04｜LLM 推理引擎与调度详细知识列表

> 优先级：P0
>
> 当前状态：已建立 Continuous Batching 和混合调度直觉；主循环、源码、手写与实验未完成
>
> 目标熟练度：原理 L3 / 源码 L3 / 手写 L3 / 实验 L3
>
> 依赖：[Transformer 推理原理与手撕](02-transformer-inference-and-handwriting.md)、[KV Cache 与内存系统](03-kv-cache-memory-system.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能把 LLM 推理引擎解释成一个持续运行的在线系统：请求不断到达、进入队列、获得 token 和 KV budget、执行 Prefill/Decode、被抢占或恢复、产生输出并清理资源。能够从空文件手写简化调度主循环，并通过 workload 实验解释吞吐、TTFT、ITL/TPOT、尾延迟和公平性的 trade-off。

## 当前基础与需要修正的表达

已有笔记证明以下直觉曾经建立：

- batching 通过合并请求提高 GPU 利用率；
- static batching 的固定 cohort 会在请求长度异质时发生 batch 退化；
- Continuous Batching 允许请求在迭代边界动态进入和退出；
- Prefill 与 Decode 的资源画像不同，混合调度是多目标 trade-off；
- 调度与 KV Cache 分配、扩容、回收存在直接耦合。

但需要修正和深化：

- “短请求结束后仍一直占用显存”不是所有 static batching 实现的必然语义；核心问题是固定 cohort 无法及时补位，已完成 lane 不再产生有效工作或 batch 逐渐缩小；
- Chunked Prefill 不只是“长请求一次放不进 GPU”的兜底，还用于 token budget、抢占粒度、TTFT/ITL 权衡和 Prefill/Decode 混批；
- 概念上区分 Prefill/Decode 有帮助，但当前 vLLM V1 源码可能用统一 token progress 表达调度，而不是维护两个完全独立的阶段调度器；
- 旧笔记处于 L1-L2，Continuous Batching 主循环伪代码仍标记未开始。

## 源码与复现契约

### 触发依据

- **真题证据门槛已触发**：题库不仅询问 Continuous Batching 原理和调度决策，也存在 Continuous Batching 源码与 KV Cache 命中的直接追问。
- **核心模块门槛已触发**：迭代级调度决定请求何时获得 token/KV budget、何时抢占和恢复，直接影响吞吐、TTFT、ITL 与正确清理，是推理引擎主循环而非外围知识。

### 主实现与条件式对比

- **主实现：vLLM V1**。固定 release/commit，沿 request queues、scheduler output、token progress、KV allocation、model execution 和 completion update 完成 source trace。
- **对比实现：SGLang，按需加入**。只有目标 JD/真题明确要求，或需要比较 scheduling policy、chunked prefill、prefix reuse 与执行组织的具体差异时才读对应路径；不要求并行精读两个完整 scheduler。
- ToolGap-KV 只学习并复用 vLLM 的真实调度/KV contract，不因此宣称拥有或重写整个 scheduler。

### 双层本地复现

1. **机制复现**：从空文件实现 deterministic Continuous Batching、token/KV budget、Chunked Prefill、preemption/resume 和清理，以本地 workload/test 验证不变量和 trade-off。
2. **真实映射**：在固定版本 vLLM 上 trace 一轮 `schedule -> execute -> update`，并用真实引擎验证至少一个 simulator 结论和一个 losing workload。

完成标准：留下固定 commit、源码路径图、简化 scheduler 代码与测试、真实运行命令、原始指标、模拟与真实系统偏差，以及至少一个失败或反例。

明确不要求：默写完整 vLLM/SGLang scheduler，或实现 speculative decode、multimodal、LoRA、DP 等与核心 contract 无关的生产分支。

## P0 详细知识列表

### 引擎请求生命周期

- request 到达、校验、排队、运行、抢占、恢复、完成、取消和失败；
- waiting、running、preempted/resumed、finished 的状态与合法转移；
- prompt tokens、computed tokens、output/speculative tokens 的进度；
- 每轮 scheduler output、model execution、sampling 与状态更新；
- streaming output、stop condition 与最终资源清理；
- 请求身份与一次 engine request/lifecycle 的边界。

### Static、Dynamic 与 Continuous Batching

- request-level、batch-level、iteration/token-level 调度粒度；
- static batching 的实现简单性、padding/cohort 固定与 batch 退化；
- dynamic batching 的等待窗口和组批条件；
- Continuous Batching 的迭代边界、动态补位和完成请求移除；
- 请求长度、到达时间、prompt/output 比例对 batch 组成的影响；
- batch size 不是唯一约束，token 数、KV block 和模型限制共同决定可运行集合；
- 提高设备利用率不保证每个请求的延迟都改善。

### 每轮调度约束

- token/compute budget；
- max running sequences；
- KV block/capacity admission；
- model max length；
- 当前 running 请求与 waiting 请求的选择顺序；
- 新请求、恢复请求和已有 running 请求；
- lookahead/speculative tokens 对预算的影响边界；
- 无法分配 KV 时的 skip、wait、preempt 或 reject；
- 调度输出必须与本轮实际执行和内存分配一致。

### Prefill、Decode 与 Chunked Prefill

- Prefill 对 TTFT 的影响；
- Decode 对 ITL/TPOT 和流式平滑度的影响；
- 只优先 Prefill 与只优先 Decode 的失败模式；
- 将长 Prefill 切成 token chunks；
- chunk 边界、已有 computed tokens 和 KV 状态；
- 用剩余 token budget 调度 Prefill chunk；
- Decode 优先与剩余预算填入 Prefill 的一种策略；
- token budget 大小对 TTFT、ITL、吞吐和显存压力的影响；
- 长请求独占、短请求插队与 starvation 风险。

### 抢占、恢复与过载

- KV 不足时为什么需要抢占；
- recompute、swap/offload 等恢复策略的适用边界；
- 抢占后释放哪些资源、保留哪些逻辑状态；
- 恢复请求如何重新进入 waiting/running；
- repeated preemption、thrashing 和 watermark/headroom；
- admission control、queue limit、timeout、load shedding；
- 过载下保护 active decode 与接纳新请求之间的权衡；
- 取消和失败不能留下 scheduler/KV 状态泄漏。

### 调度策略与公平性

- FCFS、priority、shortest-job-like 启发式的目标与风险；
- 已知输入长度与未知输出长度；
- arrival time、priority、remaining tokens、age；
- starvation、priority inversion 和 aging；
- 多租户 quota/SLO 的基本设计；
- 平均延迟、尾延迟和吞吐不能同时无条件最优；
- 策略公平比较需要相同 executor、workload 和预算。

### 引擎指标与归因

- TTFT、ITL、TPOT、end-to-end latency；
- request throughput 与 token throughput；
- queue time、Prefill time、Decode time、restore time；
- running/waiting 数量、batch tokens、KV usage；
- preemption、recompute、cache hit/miss；
- p50/p95/p99 与 workload arrival/length distribution；
- goodput/SLO attainment；
- throughput 上升但 TTFT 或 ITL 恶化的负面结果。

### vLLM V1 源码阅读

- 固定 release/commit 后再记录具体路径；
- scheduler 输入、request queues 和 schedule output；
- token progress 如何统一表达 chunked prefill、decode、prefix hit 和 speculative tokens；
- running 优先、waiting admission、token budget 和 KV slot allocation；
- preemption、free、requeue 和 resume；
- scheduler 与 KV cache manager、model runner、output processor 的边界；
- V0/V1 或版本差异只按固定源码作答，不背旧文章类名。

## P1 补充

- asynchronous scheduling 与 CPU/GPU pipeline gap；
- Prefix Cache hit 对 computed tokens 和 admission 的影响；
- speculative decoding 对 lookahead/token budget 的影响；
- LoRA adapter batch 限制；
- multimodal encoder input/cache budget；
- data-parallel prefill balancing；
- Prefill/Decode disaggregation；
- SLO-aware、deadline-aware 或 cost-aware policy；
- scheduler trace/replay 与离线 policy 对比。

## P2 延后

- 集群级副本路由、弹性伸缩和全局 placement；
- 生产级多租户配额控制面；
- 未经实验支持的复杂强化学习调度；
- 为关键词覆盖同时实现多个独立策略；
- 与目标岗位无关的 GPU kernel scheduler 细节。

## 训练顺序与验收

### A. 最小请求状态机

必须完成：

1. request 数据结构和合法状态；
2. waiting/running/finished 队列或集合；
3. add、schedule、step、finish、cancel；
4. 非法重复完成、取消和状态迁移测试；
5. 资源清理 hook。

通过标准：所有状态转移可枚举，finished/cancelled 请求不会再次被调度。

### B. Continuous Batching 主循环

必须完成：

1. 每轮接收新请求；
2. 先推进已有 running；
3. 移除完成请求；
4. 在预算允许时从 waiting 补位；
5. 生成本轮 batch 并更新 token progress；
6. 可重复输入下输出确定。

通过标准：45 分钟内手写最小版本；用不同到达时间和输出长度证明 dynamic refill 生效。

### C. Token/KV Budget 与抢占

必须完成：

1. `max_num_scheduled_tokens`；
2. `max_num_running_reqs`；
3. KV block admission 接口；
4. 无法分配时的 wait/preempt；
5. preempt 后 free、reset/recompute 和 requeue；
6. repeated preemption 与容量回收测试。

通过标准：60 分钟完成给定接口；总 scheduled tokens、running 数和 KV blocks 永远不越界。

### D. Chunked Prefill

必须完成：

1. 统一 `num_computed_tokens` 与 `num_target_tokens`；
2. running Decode 先消耗预算；
3. 剩余预算分配给 Prefill；
4. 长 Prefill 截断为 chunk；
5. 下轮从已计算位置继续；
6. 记录每请求 TTFT/ITL。

通过标准：给定 workload 能展示 token budget 改变带来的 TTFT/ITL trade-off，而不是只展示吞吐。

### E. 仿真、真实源码与实验

必须完成：

1. 用离散事件或 deterministic step simulator 比较 static/continuous batching；
2. workload 包含到达时间、prompt 长度和输出长度分布；
3. 对比不同 token budget、max sequences 和 policy；
4. 记录吞吐、TTFT、ITL、queue 和 preemption；
5. 固定 vLLM release/commit，沿真实 scheduler 完成一轮 source trace；
6. 在真实引擎上验证至少一个 simulator 结论，并记录校准偏差。

通过标准：明确区分 simulator 的 `simulated` 结论与真实 vLLM 的 `experimentally validated` 结论。

## 必须通过的领域手撕

| 题目 | 时间限制 | 最低要求 |
|---|---:|---|
| 请求生命周期状态机 | 30 分钟 | 合法转移、取消、终态幂等 |
| Continuous Batching 主循环 | 45 分钟 | 动态进入退出、补位和完成 |
| Token Budget Scheduler | 45 分钟 | token/sequence 预算不越界 |
| KV-aware Admission | 45 分钟 | allocate、wait/preempt、rollback |
| Chunked Prefill Scheduler | 60 分钟 | computed progress、chunk、混批和指标 |
| Preemption/Resume | 60 分钟 | free、requeue、recompute 与清理正确 |

不要求默写整个 vLLM scheduler。面试手撕应实现清楚的核心 contract，并主动说明删除了 speculative decode、multimodal、LoRA、DP 等生产分支。

## 原理连续追问

### Batching 与预算

- Static、Dynamic、Continuous Batching 的调度粒度分别是什么？
- Continuous Batching 为什么提高利用率，却可能恶化某些请求延迟？
- batch size、batch tokens 和 KV capacity 为什么不是同一个限制？
- 为什么当前 vLLM scheduler 可以不显式维护“Prefill 阶段队列”和“Decode 阶段队列”？
- `num_computed_tokens` 一类进度变量如何统一多个特性？

### Chunked Prefill 与混合调度

- Chunked Prefill 除了防止 OOM，还解决什么问题？
- token budget 变大为什么可能改善 TTFT、恶化 ITL？
- 为什么 Decode 优先不等于 Decode 永远独占？
- 长 Prefill 如何避免饿死？短请求插队是否公平？
- Prefill/Decode 混批一定更快吗？负面 workload 是什么？

### 抢占与过载

- KV 不足时应该 wait、reject、preempt、offload 还是 recompute？
- 抢占为什么可能导致 thrashing？如何观测？
- watermark/headroom 解决什么问题，代价是什么？
- 为什么平均吞吐不能代表用户体验？
- 系统过载时首先保护 TTFT、ITL、goodput 还是公平性？依据是什么？

### 源码与项目

- 固定版本 vLLM 一轮 `schedule -> execute -> update` 的数据流是什么？
- scheduler 和 KV cache manager 分别拥有哪类状态？
- ToolGap-KV 的 restore completion 如何安全地影响请求可调度性？
- 为什么外部 proxy 无法独自保证 engine 内部 lifecycle/KV 正确性？
- 哪项调度行为来自 vLLM，哪项是候选人 controller 拥有的？

## 与 ToolGap-KV 的连接

- CT1 需要找到 lifecycle event 与 scheduler/KV connector 的最小真实接缝；
- CT2 的 restore failure、cancellation 和 late completion 最终必须落到合法请求状态和清理；
- CT3 的 offload/restore 会与 active Decode 争用资源，必须测 active-request p95/p99；
- scheduler trace 必须区分 queue、store、restore、Prefill 和 first token；
- ToolGap-KV 不拥有 vLLM 整体调度器，除非 Gate A 证明存在一个窄缺失 contract；
- Dynamic policy 仍属于 CT4，不能因为学会调度就提前扩张项目范围。

## 完成证据

- 可测试请求状态机；
- Continuous Batching、token budget、Chunked Prefill 和 preemption 手写实现；
- static/continuous simulator 与 workload manifest；
- 指标包含 TTFT、ITL、吞吐、queue 和 preemption；
- 固定版本 vLLM scheduler source trace；
- 至少一个真实引擎实验和一个 losing workload；
- 一次 60 分钟调度手撕；
- 一次 30 分钟源码/系统连续追问；
- simulated 与 experimentally validated 结论清楚分离。

## 现有个人笔记与真题

- [Continuous Batching 主笔记](https://app.notion.com/p/3885d315c09080b79697e2afdb37775d)
- [Batching 与混合调度阶段学习记录](https://app.notion.com/p/3415d315c0908130803af01da4d6cd62)
- [Continuous Batching 的原理是什么，调度器如何决定批次](https://app.notion.com/p/39d5d315c09081cab048f6af56fa7359)
- [Continuous Batching 主循环伪代码](https://app.notion.com/p/33c5d315c090815694f5e795a737aca5)
- [continuous batching 的调度与内存复杂度](https://app.notion.com/p/3415d315c09081458e69e4a36c8d642e)
- [Continuous Batching 源码与 KV Cache 命中真题记录](https://app.notion.com/p/39d5d315c09081a287d3ec2a8e5085e3)

## 当前 vLLM 官方参考

以下 latest/stable 页面只用于定位当前概念。源码学习必须固定具体 release/commit。

- [vLLM V1 Scheduler API](https://docs.vllm.ai/en/stable/api/vllm/v1/core/sched/scheduler/)
- [vLLM SchedulerConfig](https://docs.vllm.ai/en/stable/api/vllm/config/scheduler/)
- [vLLM Optimization and Tuning](https://docs.vllm.ai/en/stable/configuration/optimization/)
- [vLLM Engine Arguments](https://docs.vllm.ai/en/stable/configuration/engine_args/)
- [SGLang repository（条件式调度对比入口）](https://github.com/sgl-project/sglang)
