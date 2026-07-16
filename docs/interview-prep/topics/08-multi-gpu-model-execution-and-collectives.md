# 08｜多 GPU 模型执行与集合通信详细知识列表

> 优先级：P1；包含面试启动前必须完成的 P0 防守子集
>
> 当前状态：已敲定 TP 主线和非通信内核边界，原理、源码、手写与实验均待完成
>
> 目标熟练度：原理 L3 / 源码 L2 / 手写 L2 / 实验 L2
>
> 依赖：[PyTorch 与张量编程](01-pytorch-tensor-programming.md)、[Transformer 推理原理与手撕](02-transformer-inference-and-handwriting.md)、[KV Cache 与内存系统](03-kv-cache-memory-system.md)、[性能分析与 GPU 最小认知](05-performance-analysis-and-gpu-literacy.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能从模型容量、单 token 计算量、设备带宽和互连成本出发解释为什么需要多 GPU 模型执行；能够把 Tensor Parallel 映射到 Transformer 的 Linear、Attention、MLP、Embedding/LM Head 和 KV Cache，推导每个 rank 的张量形状与 collective 位置，并解释 TP degree 增加后为什么不一定加速。

这是一个 TP 深入、其他并行方式建立比较能力的 P1 节点，预计集中投入约 12-20 小时。它不是通信库、分布式训练或集群控制面课程。

## P0 防守要求

开始目标岗位面试前，应能脱稿回答以下问题：

1. 单 GPU 的模型容量、KV 容量或计算能力不足时，分别有哪些扩展方向；
2. Tensor Parallel、Pipeline Parallel、Data Parallel 和 Expert Parallel 分别切分什么；
3. `rank`、`local_rank`、`world_size` 和 process group 分别表示什么；
4. broadcast、all-reduce、all-gather、reduce-scatter 与 all-to-all 的输入输出语义；
5. Column Parallel Linear 和 Row Parallel Linear 分别切 `W` 的哪个维度；
6. 为什么列并行输出可以暂时保持分片，而行并行输出需要对局部和做归并；
7. Transformer MLP 如何组合列并行和行并行以减少中间 collective；
8. Attention head 如何在 TP ranks 之间切分，GQA/MQA 会增加哪些整除和布局约束；
9. TP degree 增大为什么可能因为小矩阵、同步和通信开销而变慢；
10. PCIe、NVLink、跨 NUMA 或跨节点链路为什么会改变相同 TP 配置的表现。

通过标准：完成一次 10-15 分钟连续追问，现场推导一次两路 Column/Row Parallel Linear 的 shape 和输出等价关系。P0 防守不要求写代码、运行多 GPU 或阅读 NCCL 源码。

## P1 详细知识列表

### 多 GPU 执行的第一性原理

- 模型权重、激活、临时 workspace 和 KV Cache 分别消耗什么容量；
- 容量扩展、单请求延迟、总吞吐和并发容量是不同目标；
- 模型并行通过切分单个模型解决容量或单请求计算问题；
- 数据并行通过复制模型扩展独立请求吞吐，不减少单副本权重；
- 并行收益取决于可并行计算是否覆盖通信、同步和调度开销；
- Prefill 的大矩阵与 Decode 的小 batch GEMM 对 TP 通信摊销能力不同；
- 增加设备数会同时改变局部矩阵 shape、kernel 效率和通信比例；
- 多 GPU 可以扩大可用模型或并发容量，但不等价于延迟线性下降。

回答扩展问题时，先明确目标是“模型能否放下”“单请求是否更快”还是“集群吞吐是否更高”，避免把所有扩展方式混成同一种加速。

### 分布式运行时与集合通信语义

- rank、local rank、world size、node rank 和 device mapping；
- 默认 process group 与 TP/PP/DP/EP 子 group 的区别；
- point-to-point send/recv 与 collective 的使用边界；
- broadcast：一个 rank 的输入传播到 group 内所有 rank；
- all-reduce：对各 rank 同形张量做规约，并把结果返回所有 rank；
- all-gather：收集各 rank 分片，并让所有 rank 获得完整拼接结果；
- reduce-scatter：先规约再把结果分片到各 rank，可减少中间完整张量；
- all-to-all：每个 rank 向每个其他 rank 发送不同分片，常见于 Expert Parallel token dispatch；
- collective 要求的 shape、dtype、参与者顺序和 group 一致性；
- 阻塞完成、异步 enqueue、stream 顺序和显式等待之间的区别；
- 某个 rank 未进入 collective、调用顺序不一致或提前失败可能造成 hang，而不只是普通异常。

只要求理解 ring/tree 的基本通信直觉和延迟-带宽权衡，不要求推导 NCCL 协议、channel、chunk 或底层 kernel。

### Tensor Parallel：核心主线

以下公式采用 `Linear(X) = XW + b`，其中 `X` 为 `[..., I]`，`W` 为 `[I, O]`。

#### Column Parallel Linear

- 按输出维切分 `W = [W_0, ..., W_{p-1}]`，每个 `W_i` 为 `[I, O/p]`；
- 每个 rank 计算 `Y_i = XW_i`，局部输出为 `[..., O/p]`；
- 若下一层能够直接消费分片输出，可以延迟 all-gather；
- 若所有 rank 都需要完整 `Y`，沿输出维 all-gather 得到 `concat(Y_i)`；
- bias 同样按输出维切分，每个 rank 只加自己的 bias shard。

#### Row Parallel Linear

- 按输入维切分 `W`，每个 `W_i` 为 `[I/p, O]`；
- 输入也必须按最后一维切分为 `X_i`，每个 rank 计算局部部分和 `Z_i = X_iW_i`；
- 完整输出满足 `Y = sum_i(Z_i) + b`，因此需要 all-reduce 或等价 reduce-scatter 路径；
- 未切分 bias 只能在规约后加一次，不能让每个 rank 在规约前重复加入完整 bias。

#### Transformer 中的组合

- MLP 的 gate/up projection 通常适合列并行，down projection 适合行并行；
- 列并行中间激活直接进入行并行 down projection，可以避免中间 all-gather；
- Q/K/V projection 可按 head 或投影维切分，输出 projection 再规约；
- TP degree 必须与 attention heads、KV heads 或实现的复制策略兼容；
- MQA/GQA 下 query heads 与 KV heads 数量不同，KV head 可能被分片、复制或按 group 映射；
- Embedding/LM Head 可以使用 vocabulary parallel，局部 logits 需要按采样方式 gather 或做分布式规约；
- TP 下每个 rank 只持有与本地 KV heads 对应的 KV Cache，恢复、迁移或复用必须保留 layout 和 rank 身份；
- sequence length、hidden size、head count、KV head count 和 vocabulary size 的整除条件需要显式验证。

### 其他并行方式：比较能力

#### Data Parallel

- 每个副本通常持有完整模型并处理不同请求；
- 推理时不存在训练梯度 all-reduce，但路由、负载均衡和副本间 cache locality 会影响收益；
- 数据并行扩大集群吞吐和并发容量，不解决单副本模型放不下的问题；
- replica routing、弹性和多租户治理归入后续控制面节点。

#### Pipeline Parallel

- 按层把模型切成多个 stage，激活通过 point-to-point 通信跨 stage；
- microbatch 可以填充流水线并提高吞吐，但会引入 bubble、排队和端到端延迟；
- 自回归 Decode 的逐步依赖与小 batch 会限制流水线利用率；
- 只要求比较适用条件，不要求手写流水线调度器或阅读生产 PP 源码。

#### Expert Parallel

- MoE 把 experts 分布到不同 ranks，router 为 token 选择目标 expert；
- token dispatch/combine 常依赖 all-to-all；
- expert 热点、capacity、padding/dropping 和跨节点流量会影响负载与质量；
- 只要求形成 all-to-all 与负载不均的工程直觉，不要求手写 MoE、router 或 fused expert kernel。

#### Sequence/Context Parallel

- 知道它们通过切分序列维或上下文相关状态缓解长序列的容量与计算压力；
- 能说明它们与按 hidden/head 切分的 TP 不是同一维度；
- 作为 P2 内容，不进入本节点的源码、手写和实验验收。

### 通信成本与拓扑边界

- 用 `T ≈ α × 通信轮次 + β × 传输字节` 建立 latency 与 bandwidth 成本直觉；
- 关注 payload 大小、collective 次数、并行度和是否位于每个 decode step；
- 计算与通信能否重叠取决于数据依赖、stream、buffer 生命周期和实现支持；
- 小消息更容易被固定延迟和同步开销主导，大消息更容易受链路带宽限制；
- PCIe、NVLink、NVSwitch、NUMA 和跨节点网络只要求理解相对层级与拓扑影响；
- benchmark 必须记录设备型号、互连、拓扑、并行配置和运行时版本；
- GPU utilization 高不直接证明通信高效，TP 吞吐变差也不能仅凭直觉归因于 NCCL。

## 源码与复现契约

### 触发依据

Tensor Parallel 是主流 LLM Serving 引擎的模型执行核心机制，且真实岗位会追问框架如何初始化并行组、分片模型和插入 collective。因此核心模块门槛触发，需要 toy 机制复现和真实框架映射。

### 主实现锚点

- 主实现选择 vLLM，并在开始学习时记录固定 release/commit；
- 优先选择单机双 GPU、模型和 TP degree 均可稳定运行的版本与配置；
- 第二实现只在 JD 明确要求或需要回答一个具体设计差异时加入；
- 不为了框架覆盖同时精读 Megatron-LM、DeepSpeed、TensorRT-LLM 和 SGLang。

### 源码深度

需要能够沿固定版本定位以下路径：

```text
CLI / engine parallel configuration
  -> distributed environment initialization
  -> TP/PP group and rank state
  -> worker / model executor construction
  -> model loading and parameter sharding
  -> parallel Linear / Attention layer
  -> collective invocation
  -> local KV Cache layout and model output
```

完成源码阅读后必须回答：

- TP size 如何从用户配置进入执行器和模型加载；
- rank、device 和 process group 在哪里建立并传递；
- 权重是加载后切分、加载时分片，还是由 loader 映射到本地 shard；
- Column/Row Parallel Linear 的输入输出 contract 和 collective 在哪里发生；
- Attention heads 与 KV heads 如何映射到本地 rank；
- vocabulary parallel 或采样前 logits 如何处理；
- worker 失败或 collective 参与者不一致时，错误如何表现和传播；
- 哪些能力来自 vLLM glue，哪些来自 PyTorch distributed/NCCL；
- 为什么本节点停在 collective 接口与调用语义，而不进入 NCCL 内部实现。

源码记录必须保存项目、release/commit、入口、关键对象、控制流图和已知版本差异，不能只记录类名列表。

## 手写 L2 契约

### 必须完成的简化实现

从空文件实现一个单进程多 shard 的 TP Linear/MLP 练习：

1. Column Parallel Linear：切分权重和 bias，分别计算 local output，再按输出维拼接；
2. Row Parallel Linear：切分输入和权重，分别计算 partial sum，再求和并正确添加 bias；
3. TP MLP：用列并行 up/gate 与行并行 down 组合，避免中间恢复完整张量；
4. 与未分片 `nn.Linear`/MLP 使用相同权重，验证输出数值一致；
5. 显式断言 hidden/intermediate size、world size 和 shard shape；
6. 至少覆盖一个非法整除、错误切分维或 bias 重复累加的失败测试。

时间限制：45-60 分钟完成 Linear 核心；TP MLP 可以在后续 30 分钟内补齐。已有 [Transformer 节点](02-transformer-inference-and-handwriting.md) 的“简化 TP Transformer Layer”可以复用同一份实现和测试，不重复计算完成度。

通过标准不是能够调用 `torch.chunk`，而是能够先写出每个 shard 的数学关系和 shape，再实现并通过等价性测试。

### 不要求手写

- `torch.distributed` rendezvous、launcher 或 ProcessGroup；
- all-reduce/all-gather 的网络实现；
- NCCL communicator、ring/tree 或通信 kernel；
- 完整多进程容错和生产模型加载器；
- 完整分布式 Transformer。

## 实验 L2 契约

### 语义实验

- 用单进程 shard 模拟验证 Column/Row Parallel Linear 数值等价；
- 使用 CPU/Gloo 或真实 GPU/NCCL 运行最小 all-reduce、all-gather、reduce-scatter 示例；
- 主动改变 tensor shape、world size 或 collective 类型中的至少一个变量；
- 记录每个 rank 的输入、输出、shape、dtype 和 group；
- 制造一次 collective 顺序或 shape contract 错误，记录失败或 hang 风险及安全终止方法。

CPU/Gloo 结果只能证明 collective 语义和多进程控制流，标记为 `simulated` 或学习实验；不能外推 GPU/NCCL 的带宽、延迟或扩展效率。

### 真实 TP 实验

有单机双 GPU 条件时，在固定 vLLM 版本上完成 TP=1 与 TP=2 对照：

- 固定模型 revision、dtype、workload、请求并发、输入/输出长度和测量窗口；
- 记录 GPU 型号、显存、PCIe/NVLink 拓扑、驱动、CUDA、PyTorch、NCCL 和 vLLM 版本；
- 记录每 rank 权重/KV/总显存以及模型是否能够在 TP=1 放下；
- 记录 request/token throughput、TTFT、ITL/TPOT、端到端延迟和 p50/p95；
- 计算 speedup 与 scaling efficiency，区分容量收益和速度收益；
- 至少保留一个 TP=2 没有加速或发生退化的小模型、小 batch、短输出案例；
- 用 profiler、runtime log 或源码路径说明可能的计算/通信边界，不做无证据的单因子归因。

如果模型无法在 TP=1 放下，应把实验表述为容量扩展验证，不能伪造 TP=1 性能基线。没有双 GPU 时保留命令、脚本和待验证假设，节点的实验维度继续标记为待完成。

## 明确不要求

- 实现或修改 NCCL、Gloo、ProcessGroup、RDMA/NIXL；
- CUDA/Triton 通信或融合 kernel；
- NCCL channel、protocol、chunk、LL/LL128 等内部细节；
- 完整 DDP、FSDP、ZeRO、optimizer state 或分布式训练容错；
- 从零实现 PP scheduler、MoE router、expert kernel 或完整分布式模型执行器；
- 多机多卡拓扑调优、通信计算重叠改造和大规模 benchmark；
- 把 CPU/Gloo、单进程 shard 或纸面推导包装成 GPU 性能证据。

## 与后续控制面节点的边界

以下内容独立进入“分布式 Serving 与平台控制面”，不在本节点继续展开：

- Prefill/Decode disaggregation 与跨实例 KV transfer；
- replica routing、cache affinity、load balancing 和 admission；
- 多节点部署、服务发现、健康检查、重试和容错；
- 弹性伸缩、资源编排、多租户、配额和 SLO；
- Ray、Kubernetes 或其他平台控制面的具体实现。

本节点回答“一个模型如何跨 GPU 执行”；后续节点回答“多个执行实例和资源如何组成在线 Serving 系统”。

## 与 ToolGap-KV 的边界

TP 会改变 KV Cache 的本地 head layout、rank 身份、容量统计、格式兼容和跨 rank 完成条件，因此是解释未来多 GPU 生命周期问题的必要背景。

但 ToolGap-KV CT1-CT3 当前仍限定为单引擎、TP=1。除非仓库存在真实多 GPU 接口、rank-aware lifecycle、兼容性测试和实验产物，否则：

- 多 GPU、heterogeneous TP 和跨 rank completion 只能标记为 `roadmap`；
- 单进程 shard 练习最多是学习验证，不是 ToolGap-KV `shipped` 能力；
- CPU/Gloo 结果不能标记为 GPU `experimentally validated`；
- 不因学习 vLLM TP 源码而声称项目已经集成对应路径；
- TP layout 可以作为 manifest/compatibility 的未来字段，但不扩大 CT1-CT3 主线。

## 面试连续追问

- 为什么模型并行和数据并行解决的问题不同？
- TP 为什么能降低单卡权重占用？是否也按相同比例降低 KV Cache？
- Column Parallel 和 Row Parallel 分别如何切分 `W`？
- 为什么 MLP 可以把列并行和行并行相邻组合？节省了哪次通信？
- Row Parallel 的 bias 为什么不能在 all-reduce 前由所有 ranks 重复加入？
- all-reduce 能否等价改写成 reduce-scatter 加 all-gather？为什么可能这样做？
- TP 下 Attention heads 和 KV heads 如何切？GQA 的 KV heads 小于 TP degree 怎么办？
- TP degree 从 2 增加到 8，单卡计算减少，为什么端到端延迟可能上升？
- Prefill 与 Decode 哪一个更容易摊销 collective？为什么？
- PP 为什么会有 bubble？自回归 Decode 为什么让它更棘手？
- EP 为什么常用 all-to-all？expert imbalance 会导致什么？
- 为什么 CPU/Gloo benchmark 不能证明 NCCL 性能？
- 你如何判断 TP=2 的收益来自模型终于能放下，还是实际执行变快？
- collective hang 常见的 contract 违反有哪些？如何安全定位？
- vLLM 在哪里创建并行组、切分权重并调用 collective？
- ToolGap-KV 为什么当前不能声称支持 heterogeneous TP？

## 完成证据

- 一次通过的 P0 连续追问和一份 TP shape/通信手推记录；
- 一张固定版本 vLLM 多 GPU 模型执行路径图；
- 一份限时 TP Linear/MLP 实现及数值等价、shape 和失败测试；
- 一次 collective 语义实验，记录每个 rank 的输入输出；
- 有双 GPU 时完成 TP=1/TP=2 对照，并保留一个不加速案例；
- 没有双 GPU 时明确保留实验缺口，不把 CPU/Gloo 结果外推为 GPU 结论；
- 一份并行策略选择说明，区分容量、延迟、吞吐和通信目标；
- 所有 ToolGap-KV 关联表述保持 `roadmap`、`shipped`、`experimentally validated`、`simulated` 的证据边界。
