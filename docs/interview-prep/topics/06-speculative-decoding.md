# 06｜投机解码详细知识列表

> 优先级：P1；包含面试启动前必须完成的 P0 防守子集
>
> 当前状态：已敲定非 kernel 岗位的减负范围，原理、源码、手写与实验均待完成
>
> 目标熟练度：原理 L3 / 源码 L2 / 手写 L2 / 实验 L2
>
> 依赖：[PyTorch 与张量编程](01-pytorch-tensor-programming.md)、[Transformer 推理原理与手撕](02-transformer-inference-and-handwriting.md)、[KV Cache 与内存系统](03-kv-cache-memory-system.md)、[LLM 推理引擎与调度](04-llm-engine-scheduling.md)、[性能分析与 GPU 最小认知](05-performance-analysis-and-gpu-literacy.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能解释经典 speculative sampling 为什么在减少 target model 串行调用次数的同时保持目标分布不变，能够分析 draft 成本、接受长度、验证成本、并发、KV 占用和调度开销之间的收益边界；能够手写并测试简化 draft-verify 和 cache cursor 控制流，并把它映射到固定版本 vLLM 的真实请求链路和有界对照实验。

这是独立的 P1 深挖节点，预计在完成其前置主题后集中投入约 10-16 小时。为了避免 P1 未完成时形成明显面试漏洞，其中一小部分被定义为 P0 防守要求，但不会因此把整个节点升级为面试启动阻塞项。

## P0 防守要求

开始目标岗位面试前，应能在白板上脱稿回答以下问题，不要求此时已经完成生产源码阅读和本地复现：

1. 解释 draft proposal、target parallel verification、accept/reject、修正采样和继续生成的完整链路；
2. 解释为什么一次 target forward 可以验证多个候选位置，以及减少的是哪一种串行瓶颈；
3. 区分 greedy decoding 和随机采样的正确性要求，知道“预测相同就接受”不足以保证随机采样分布正确；
4. 用直觉解释接受概率和拒绝后的 residual distribution 为什么能够恢复 target 分布；
5. 说明接受率/接受长度、draft 开销、target 验证开销和系统 overhead 如何共同决定是否加速；
6. 给出低接受率、draft 过重、输出过短、小 batch 或资源竞争导致不加速甚至退化的场景；
7. 解释全部接受、部分接受和首 token 拒绝时，target/draft KV Cache 应如何提交、截断或丢弃未接受状态；
8. 解释 lookahead/speculative tokens 为什么需要占用 scheduler 的 token budget 和 KV block 预算。

通过标准：完成一次 10 分钟连续追问，能够画出请求、proposal、verification、sampler、KV 状态和 scheduler progress 的关系；不能只背“用小模型猜、大模型验证”。

## P1 详细知识列表

### 算法与概率正确性

- 普通自回归生成为什么受 target model 逐 token 串行调用限制；
- draft model/方法生成一段候选 token，target model 对相应位置做批量验证的张量关系；
- target 分布 `p`、draft 分布 `q` 和逐 token 条件概率；
- 经典 speculative sampling 的接受概率 `min(1, p(x) / q(x))`；
- 拒绝后从归一化的 `max(0, p - q)` residual distribution 采样的原因；
- 全部候选被接受后，为什么还可以从 target 分布生成一个额外 token；
- 接受一段前缀并在首次拒绝处停止的控制流；
- greedy verification 与 stochastic verification 的算法差异；
- 正确性结论依赖的前提，包括一致的 tokenizer/词表、条件上下文和数值实现语义；
- 近似变体与精确分布保持算法必须分开表述。

要求不是背公式，而是能从“最终输出必须仍服从 target model 分布”这一不变量重新推导接受和修正逻辑。

### 成本模型与收益边界

- proposal length、acceptance rate、accepted length 和 acceptance histogram 的区别；
- draft 每轮成本、target verification 成本、sampler/scheduler overhead 和额外内存成本；
- 每次 target 调用推进的有效 token 数为什么比单独看接受率更接近收益；
- draft 越强通常接受更多，但 draft 自身成本也可能更高；
- prompt length、output length、batch/concurrency 和采样参数如何改变收益；
- target/draft 是否共享层、设备和并行策略如何改变资源占用；
- throughput 提升不代表 TTFT、ITL/TPOT 或 p99 同时改善；
- benchmark 必须包含 losing workload，不能只展示高接受率样本。

### KV Cache 与调度交互

- target cache 与 draft cache 分别代表什么进度，不能把 proposal 直接当作 target 已提交状态；
- 全接受、部分接受和拒绝时，逻辑 token cursor 与物理 KV block 的提交/截断关系；
- 生产系统可以通过元数据移动或 block 复用处理回滚，不等于必须搬动整段 KV 张量；
- speculative/lookahead tokens 如何影响 token budget、KV block reservation 和 admission；
- Continuous Batching 下不同请求接受长度不同，scheduler 如何更新各自进度；
- 显存压力、抢占、prefix cache、chunked prefill 与投机预算之间的潜在竞争；
- 额外 draft 权重和 KV 占用可能减少可服务并发；
- 指标应区分 proposed、accepted、rejected、verified 和最终 committed tokens。

### 变体认知

以下变体只要求说明 proposal 从哪里来、需要什么额外状态、主要收益和限制，不要求逐一源码复现：

- 独立 draft model 的经典 speculative decoding；
- n-gram/prompt lookup speculation；
- multi-token prediction；
- Medusa/EAGLE 类多候选或特征级预测；
- self-speculative/layer skipping 等复用 target 部分能力的方法。

面试时应先说清当前讨论的是哪一种模式，不能把内部 MTP、外部 draft model 和 n-gram proposal 混成同一条实现链路。

## 源码与复现契约

触发依据：已收集问题会追问投机解码原理、实现和系统适配；同时它会跨越 sampling、scheduler、KV budget 和 model execution，是推理引擎的重要相邻机制。两个门槛均触发。

### 主实现锚点

- 主实现选择 vLLM，并在正式学习开始时记录固定 release/commit，不追随浮动 `main`；
- 与 ToolGap-KV 使用的引擎版本存在明显差异时，分别记录“学习锚点”和“项目锚点”，不混用源码结论；
- SGLang 只在目标 JD 明确要求，或需要回答一个具体 proposal/scheduler trade-off 时作为对比实现。

### 源码深度

需要能够从一次请求追踪：

```text
request/config
  -> scheduler 预留 speculative token 与 KV budget
  -> proposer 生成候选
  -> target model 批量验证
  -> rejection sampler / greedy verifier
  -> accepted token 与 KV 状态提交
  -> request progress 和下一轮调度
```

完成源码阅读后必须记录真实路径和对象，说明：

- 特性如何配置并进入请求/引擎；
- proposal 长度和预算由谁决定；
- proposer 与 target runner 之间传递什么张量和元数据；
- acceptance/rejection 由谁计算；
- scheduler 如何接收 accepted token 数并更新进度；
- KV slot/block 如何为 speculative tokens 预留和回收；
- metrics 如何暴露接受效果和性能；
- 哪些分支属于兼容性、并行、CUDA Graph 或模型特例，为什么不纳入本次手写。

### 有界控制流复现

投机解码的控制流、KV 状态和 scheduler 进度与目标 Serving 岗位直接相关，因此不把手写整体降为 L0；但完整随机采样系统从零恢复的边际收益不足，手写范围限定为：

- 从空文件实现简化 draft-verify 循环，能定位首个拒绝位置并只提交合法前缀；
- 记录 proposed、accepted、rejected 和 committed token；
- 用逻辑 cache cursor 实现全接受、部分接受和首 token 拒绝后的 commit/truncate；
- 独立写出单个 token 的 acceptance probability 和 residual distribution 核心函数，说明归一化与数值边界；
- 能读懂、运行并主动修改一份完整 stochastic speculative sampling 参考实现，但不要求脱稿从零恢复全部细节；
- 不依赖现成 speculative decoding 库完成简化控制流与 cache cursor。

限时标准：在完成学习后，能在 30-45 分钟内写出并调通简化控制流和 cache cursor；概率函数可作为独立小题，不与生产引擎骨架捆绑。

### 本地测试

- greedy 模式与 target-only autoregressive decoding 的 token 序列完全一致；
- `q == p` 时高接受路径正确；
- draft 很差时首 token 拒绝路径正确；
- 部分接受后只提交合法 token，逻辑 cache cursor 不越过 committed progress；
- 零 proposal length、EOS 和最大长度边界行为明确。

完整参考实现应有固定 seed 的可重复测试；经验分布一致性测试属于推荐深挖证据，不再阻塞本节点完成。

### 真实框架映射

在固定环境中使用一组兼容的 target/draft 组合，对比相同 target model 的普通生成和投机生成：

- 固定框架 commit、模型 revision、硬件、dtype、并行配置和启动参数；
- 固定 prompt 集、输入/输出长度、并发和采样参数；
- 报告 proposed/accepted token、平均接受长度或等价接受指标；
- 报告请求/token throughput、TTFT、ITL/TPOT、端到端延迟和显存；
- 主动改动一个 proposal length、draft 方法或并发变量，说明它对接受与系统成本的影响；
- 至少保留一个获益 workload 和一个不开启投机更优的 workload；
- 结合 source trace 解释一次典型请求的 accepted progress、调度预算与 KV 变化。

不要求完成短/长输出、低/高并发和多种 proposal 质量的全因子矩阵；如后续将投机解码变成项目主线，再把该矩阵升级为必做。toy 实现证明控制流理解，不证明生产集成或性能；只运行官方示例也不证明理解内部状态。真实固定环境对照完成后，性能结论才能标记为 `experimentally validated`。

## 明确不要求

- 训练或微调 draft model、MTP head、Medusa 或 EAGLE；
- 从零实现 CUDA/Triton speculative decoding kernel；
- 深挖 CUDA Graph 捕获和重放内部实现；
- 维护完整生产级 scheduler fork；
- 多机投机解码、跨节点 draft/target 通信优化；
- 为所有变体建立源码路径图和本地复现；
- 把某个固定 acceptance rate 或 speedup 当作跨模型、硬件和 workload 的通用结论。

## 与 ToolGap-KV 的边界

投机解码可能增加临时 token、KV block reservation、回滚和显存压力，并影响 retain/offload/recompute 的可用预算，因此需要在项目深挖中能够回答两者如何相互作用。

但它不是 CT1-CT3 主线的一部分。除非仓库出现真实接口、测试和实验产物，否则：

- 不实现 speculative scheduler 或 kernel；
- 不把“兼容投机解码”描述为 `shipped`；
- 不把 toy 实现结果外推为 ToolGap-KV 已完成集成；
- 可以把潜在冲突记录为 `roadmap` 或实验控制变量。

## 面试连续追问

- 为什么投机解码能够加速自回归生成？它没有减少哪些计算或成本？
- 一次 target forward 为什么能够验证多枚 draft token？
- greedy verification 和随机 speculative sampling 有什么本质差异？
- 为什么接受概率不是简单判断 `argmax` 是否相同？
- token 被拒绝后为什么不能直接从原始 target 分布继续采样？
- residual distribution 如何保证最终输出仍服从 target model？
- draft model 越强是否一定越快？
- acceptance rate 很高但端到端变慢，可能是什么原因？
- 全接受、部分接受和首 token 拒绝时，两套 KV Cache 分别如何变化？
- speculative tokens 如何影响 scheduler token budget、KV block 预算和并发？
- 投机解码如何与 Continuous Batching、Chunked Prefill、Prefix Cache 或抢占交互？
- 你会如何给 vLLM 增加一种新的 proposer，并验证没有破坏正确性？
- 线上应该监控哪些指标，如何判断是 proposal 质量还是系统开销导致退化？
- 为什么某个模型和硬件上的 speedup 不能直接外推到另一组 workload？

## 完成证据

- 一次通过的 P0 十分钟防守追问记录；
- 一张固定版本 vLLM 请求级源码路径图；
- 一份独立写成的 PyTorch draft-verify 与 cache cursor 简化实现；
- 一份已读懂、运行并主动修改的 stochastic speculative sampling 参考实现；
- 覆盖全接受、首 token 拒绝、部分接受和 cache cursor 不变量的本地测试；
- 一份固定环境 target-only 与 speculative 对照实验；
- 一个明确的 winning workload 和一个 losing workload；
- 一次 acceptance、调度预算、KV 状态与性能结果的联合归因；
- 所有 ToolGap-KV 关联表述保持 `roadmap`、`shipped`、`experimentally validated`、`simulated` 的证据边界。
