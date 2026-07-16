# AI Infra 面试就绪知识地图索引

> 状态：持续维护
>
> 目标岗位：2027 校招 LLM Serving / 大模型推理平台 / AI Infra 平台研发 / 推理调度 / 模型服务后端
>
> 组织方法见 [知识地图设计](../superpowers/specs/2026-07-15-ai-infra-interview-readiness-map-design.md)。

## 交互式导图

- **浏览器直接打开：** [AI Infra 面试就绪知识图谱](AI_INFRA_INTERVIEW_READINESS.html)
- **内容源：** 本索引和 `topics/` 下的 13 个专题详情页；不要直接编辑生成后的 HTML。
- **修改 Markdown 后重新生成：** `python3 scripts/build_interview_readiness_html.py`

导图为离线单文件，不依赖 CDN 或在线服务，支持节点展开/收起、搜索、筛选、平移、缩放和详情面板。ToolGap-KV 项目答辩树继续在 `docs/agent-kv/INTERVIEW_MAP.md` 独立维护，不合并进本图。

## 索引约定

本文件只保存最终思维导图需要的主题节点。一个内容只有在具有独立优先级、目标熟练度、完成状态或复习决策时，才成为节点。

API、公式、练习、原理追问、源码锚点和参考资料保存在主题详情页中，不继续展开成导图节点。最终 HTML 点击节点后，通过详情面板展示这些内容。

熟练度维度：

- **原理**：从第一性原理解释机制、复杂度和资源约束；
- **源码**：定位真实实现并解释数据流、控制流和 trade-off；
- **手写**：在限定时间内完成简化实现并通过本地测试；
- **实验**：通过可复现实验验证正确性、性能和边界。

源码与复现采用双门槛：真题明确拷问源码/实现，或该特性属于目标岗位核心模块，满足任意一项就必须建立详情页契约。契约默认只选一个固定版本的主实现，并同时完成 toy 机制复现与真实框架运行/trace；第二个框架只用于回答明确的设计差异或 JD 要求，不做无目的源码巡游。

## 当前基线

- Transformer：能够口述总体结构、Attention 直觉、自回归生成、KV Cache 与 PagedAttention 的基本因果链；张量形状、源码、手写和实验尚未建立。
- PyTorch：从零开始。
- ToolGap-KV：项目材料目前仍以 `roadmap` 为主，不把设计文档视为已经获得的实现能力。

## 知识主题

### 01｜PyTorch 与张量编程

- **优先级：** P0
- **状态：** 已敲定，待训练与验收
- **目标熟练度：** 原理 L2 / 源码 L1 / 手写 L3 / 实验 L2
- **能力结果：** 掌握表达 Transformer 推理所需的 PyTorch 基础，能够正确处理张量形状、内存布局、模型组件、推理模式和 GPU 测量，并为 Attention、Decoder Block 与 KV Cache 手写提供工具能力。
- **边界：** 不系统学习数据集、训练循环、DDP/FSDP、`torch.compile` 或自定义 CUDA operator。
- **前置：** Python 基础。
- **支持主题：** Transformer 推理原理与手撕、量化、模型并行、性能分析。
- **详情：** [PyTorch 与张量编程详细知识列表](topics/01-pytorch-tensor-programming.md)

### 02｜Transformer 推理原理与手撕

- **优先级：** P0
- **状态：** 已敲定；原理具有旧笔记基础，手写与实验待开始
- **目标熟练度：** 原理 L3 / 源码 L2 / 手写 L3 / 实验 L3
- **能力结果：** 能从张量、模型、内存和 Serving 四层讲清 decoder-only Transformer，口述 tokenizer、采样、停止条件、detokenize 与 streaming 的完整链路，并独立手写 Attention、RoPE、GQA、SwiGLU、Decoder Block 与 KV Cache Decode；对 MLA 建立低秩缓存、解耦 RoPE、矩阵吸收及 Prefill/Decode 差异的防守能力。
- **边界：** 不要求从零手写高性能 FlashAttention、PagedAttention CUDA/Triton kernel，也不把完整训练体系纳入主线；输出处理子集和 MLA 子集只要求有界的原理/源码能力，不增加 sampler、grammar engine、MLA 或 kernel 手写及独立实验。
- **依赖主题：** PyTorch 与张量编程。
- **关联项目：** 为 ToolGap-KV 提供 K/V 产生、Prefill/Decode 和输出等价 oracle；系统生命周期与物理内存管理归入下一主题。
- **详情：** [Transformer 推理原理与手撕详细知识列表](topics/02-transformer-inference-and-handwriting.md)

### 03｜KV Cache 与内存系统

- **优先级：** P0
- **状态：** 已建立动机和 block 化直觉；容量手算、源码、系统手撕与实验待完成
- **目标熟练度：** 原理 L3 / 源码 L3 / 手写 L3 / 实验 L3
- **能力结果：** 能从容量、布局、block 分配、前缀共享、引用与回收、驱逐、offload/recompute、异步失败和观测指标完整解释 KV Cache 系统，并手写简化 Block Manager 与生命周期控制逻辑；能够比较普通 K/V 与 MLA latent cache 的容量、layout 和兼容性边界。
- **边界：** 不要求手写 PagedAttention CUDA/Triton kernel；MLA 缓存只做原理 L2 / 源码 L1 防守，不增加 cache manager 手写或 benchmark；分布式远端 KV、RDMA 和多级存储放在 P1，不扩大 ToolGap-KV 的 CT1-CT3 主线。
- **依赖主题：** Transformer 推理原理与手撕、操作系统内存管理、并发与异步状态机。
- **关联项目：** ToolGap-KV 核心主题；必须区分候选人拥有的逻辑生命周期与 vLLM 拥有的物理 KV 数据面。
- **源码与复现：** 双门槛均触发；主实现为固定版本 vLLM，完成 toy Block Manager/PagedAttention 逻辑与真实引擎 trace。SGLang RadixAttention 只作为 Prefix Cache 组织方式的条件式对比。
- **详情：** [KV Cache 与内存系统详细知识列表](topics/03-kv-cache-memory-system.md)

### 04｜LLM 推理引擎与调度

- **优先级：** P0
- **状态：** 已建立 Continuous Batching 和 Prefill/Decode 混合调度直觉；调度主循环、源码、手写与实验待完成
- **目标熟练度：** 原理 L3 / 源码 L3 / 手写 L3 / 实验 L3
- **能力结果：** 能沿请求生命周期解释 Continuous Batching、token/KV budget、Chunked Prefill、抢占、准入、调度策略和指标权衡，并手写可测试的迭代级调度器。
- **边界：** 聚焦单引擎 runtime；集群级路由、弹性伸缩和多租户控制面另设平台主题，不在此节点无限扩张。
- **依赖主题：** Transformer 推理两阶段、KV Cache 与内存系统、并发与异步状态机。
- **关联项目：** ToolGap-KV 的生命周期事件、KV 动作准入、恢复请求重入调度和 active-request 尾延迟边界。
- **源码与复现：** 双门槛均触发；主实现为固定版本 vLLM，完成简化 Continuous Batching scheduler 与真实 scheduler source trace/实验。仅在 JD 或具体 trade-off 需要时对比 SGLang。
- **详情：** [LLM 推理引擎与调度详细知识列表](topics/04-llm-engine-scheduling.md)

### 05｜性能分析与实验方法

- **优先级：** P0
- **状态：** PyTorch/Transformer 主题已有零散测量要求；尚未形成统一实验方法并完成验收
- **目标熟练度：** 原理 L2 / 源码 L0 / 手写 L0 / 实验 L2
- **能力结果：** 具备用于 LLM Serving 的最小 GPU 与性能认知，能正确测量和解释 Prefill、Decode、KV Cache 与数据搬运，不因异步执行、workload 或统计错误得出伪结论。
- **边界：** 这是性能实验防守节点，不是 CUDA/算子学习路线；不要求 kernel 源码、CUDA/Triton 手写、PTX/SASS、occupancy 调优或 Tensor Core 指令。
- **复用方式：** 不新增一套独立项目；直接复用 PyTorch、Transformer、KV Cache、调度和 ToolGap-KV 的实验作为验收载体。
- **详情：** [性能分析与 GPU 最小认知详细知识列表](topics/05-performance-analysis-and-gpu-literacy.md)

### 06｜投机解码

- **优先级：** P1；其中基础链路、正确性直觉、收益条件和系统交互属于面试启动前的 P0 防守要求
- **状态：** 已敲定非 kernel 岗位的减负范围，原理、源码、手写与实验均待完成
- **目标熟练度：** 原理 L3 / 源码 L2 / 手写 L2 / 实验 L2
- **能力结果：** 能从概率正确性、成本模型、KV 状态和调度预算解释投机解码，手写简化 draft-verify 与 cache commit/truncate 控制流，并通过固定版本 vLLM 对照实验解释一个获益和一个退化边界。
- **边界：** 不训练 draft/MTP/EAGLE 模型，不手写 CUDA/Triton kernel，不维护生产级 scheduler fork；其他投机解码变体只做有问题导向的设计比较。
- **依赖主题：** Transformer 推理原理与手撕、KV Cache 与内存系统、LLM 推理引擎与调度、PyTorch 与张量编程、性能分析与实验方法。
- **关联项目：** 只分析 speculative tokens 对 KV 容量、回滚、抢占和 offload 的相互影响；没有真实实现与证据前，不把它描述为 ToolGap-KV 的项目能力。
- **源码与复现：** 双门槛均触发；主实现为固定版本 vLLM，完成有界的 PyTorch 控制流练习与真实引擎基线/投机对照实验，不要求从零恢复完整随机投机采样系统。SGLang 仅在 JD 或明确 trade-off 需要时对比。
- **详情：** [投机解码详细知识列表](topics/06-speculative-decoding.md)

### 07｜量化与低精度推理

- **优先级：** P1；其中数值映射、常见方案、质量边界和性能条件属于面试启动前的 P0 防守要求
- **状态：** 已敲定非 kernel 岗位范围，原理、源码阅读与实验均待完成
- **目标熟练度：** 原理 L3 / 源码 L2 / 手写 L0 / 实验 L2
- **能力结果：** 能解释权重、激活和 KV Cache 量化的数值语义与 Serving trade-off，读懂固定版本 vLLM 的集成与 dispatch 路径，并通过完整复现实验判断容量、性能和质量边界。
- **边界：** 不要求量化 Linear、INT4 packing、自定义 operator、CUDA/Triton kernel 或完整复现 GPTQ/AWQ/SmoothQuant；可选数值 notebook 不作为限时手撕门槛。
- **依赖主题：** PyTorch 与张量编程、Transformer 推理原理与手撕、KV Cache 与内存系统、性能分析与实验方法。
- **关联项目：** 只分析 KV 低精度表示对容量、传输、格式兼容和正确性的影响；没有真实接口和质量实验前，不把 KV 量化描述为 ToolGap-KV 已实现能力。
- **源码与复现：** 采用固定版本 vLLM 集成路径阅读与完整参考实验复现，不要求独立重写生产算子；第二种量化框架或算法仅在 JD 或明确比较问题需要时加入。
- **详情：** [量化与低精度推理详细知识列表](topics/07-quantization-and-low-precision-inference.md)

### 08｜多 GPU 模型执行与集合通信

- **优先级：** P1；其中并行方式边界、TP 切分与 collective 语义属于面试启动前的 P0 防守要求
- **状态：** 已敲定 TP 主线和非通信内核边界，原理、源码、手写与实验均待完成
- **目标熟练度：** 原理 L3 / 源码 L2 / 手写 L2 / 实验 L2
- **能力结果：** 能从容量、计算和通信约束解释 TP/DP/PP/EP，推导 Transformer TP 的张量切分与 collective 位置，手写简化 TP Linear/MLP，并沿固定版本 vLLM 追踪多 GPU 模型执行路径。
- **边界：** TP 深入，DP/PP/EP 建立比较能力；不实现 NCCL/RDMA/ProcessGroup 或通信 kernel，不学习完整分布式训练，也不把 PD 分离、跨节点 KV、路由和弹性塞入本节点。
- **依赖主题：** PyTorch 与张量编程、Transformer 推理原理与手撕、KV Cache 与内存系统、性能分析与实验方法。
- **关联项目：** 只支撑 TP 下 KV layout、分片身份和格式兼容性分析；ToolGap-KV CT1-CT3 仍以单引擎、TP=1 为主线，没有真实产物前不得声称多 GPU 支持。
- **源码与复现：** 核心模块门槛触发；主实现为固定版本 vLLM，完成 toy TP Linear/MLP 等价性测试和真实执行路径 trace。GPU/NCCL 性能实验依赖实际双卡环境；CPU/Gloo 或单进程分片只能验证语义，不能形成 GPU 性能结论。
- **详情：** [多 GPU 模型执行与集合通信详细知识列表](topics/08-multi-gpu-model-execution-and-collectives.md)

### 09｜分布式 Serving 数据路径与 PD 分离

- **优先级：** P1；其中 Prefill/Decode 差异、KV 可信交接、失败回退和收益边界属于面试启动前的 P0 防守要求
- **状态：** 已敲定数据路径主线和非传输内核边界，原理、源码、手写与实验均待完成
- **目标熟练度：** 原理 L3 / 源码 L2 / 手写 L2 / 实验 L2
- **能力结果：** 能沿请求、KV Cache、状态、所有权和指标五条线解释一次 Prefill/Decode 分离服务，设计可信 KV handoff 与 Decode admission，手写逻辑交接状态机，并用等资源实验判断 PD 分离的获益与退化条件。
- **边界：** 聚焦 Prefill/Decode 数据路径、KV readiness、串联队列和失败回退；不实现 RDMA/NIXL/传输 kernel，也不把全局路由、cache-aware balancing、Kubernetes/Ray、弹性、多租户和 SLO 控制面塞入本节点。
- **依赖主题：** KV Cache 与内存系统、LLM 推理引擎与调度、性能分析与实验方法、多 GPU 模型执行与集合通信。
- **关联项目：** 可复用 lifecycle epoch、异步 completion fencing、兼容性、取消、fallback、cleanup 和 DecisionTrace 思想；ToolGap-KV CT1-CT3 仍是单引擎 retain/offload/recompute 主线，没有跨实例协议与实验证据前不得声称 PD 支持。
- **源码与复现：** 核心 Serving 模块门槛触发；主实现为固定版本 vLLM，完成 PD 角色到 KV connector、ready admission、失败与 cleanup 的完整 trace，以及 toy handoff 状态机。真实性能结论要求等资源 co-located/PD 对照；fake transfer 只能标记为 `simulated`。
- **详情：** [分布式 Serving 数据路径与 PD 分离详细知识列表](topics/09-disaggregated-serving-data-path-and-pd.md)

### 10｜Serving 路由与平台控制面

- **优先级：** P1；其中路由策略边界、locality-load 权衡、健康与 freshness、集群准入、背压、retry 和 SLO 属于面试启动前的 P0 防守要求
- **状态：** 已敲定源码主线和减负范围，原理、源码与手写待完成；实验维度不独立要求
- **目标熟练度：** 原理 L3 / 源码 L2 / 手写 L2 / 实验 L0
- **能力结果：** 能根据请求、Endpoint、KV locality 和 SLO 解释集群路由决策，区分硬过滤与软评分，沿固定版本 vLLM Router 讲清完整链路，并限时手写可解释的 `choose_endpoint` 核心代码。
- **边界：** 聚焦 endpoint eligibility、cache-aware + load-aware selection、admission/backpressure、health/freshness、retry 和 DecisionTrace；不要求独立模拟器、多实例 vLLM 实验、性能 benchmark、Kubernetes/Ray controller、autoscaler 或生产控制面实现。
- **依赖主题：** KV Cache 与内存系统、LLM 推理引擎与调度、性能分析与实验方法、分布式 Serving 数据路径与 PD 分离。
- **关联项目：** 可复用 lifecycle epoch、freshness、compatibility、DecisionTrace 和 fail-closed 思想；ToolGap-KV CT1-CT3 仍是单引擎生命周期系统，router/control plane 在没有真实多实例产物前只能是 `roadmap`。
- **源码与复现：** 主实现为固定版本 vLLM Router，完整追踪请求解析、Endpoint 状态、过滤、评分、转发、retry/circuit breaker 和指标；llm-d KV Cache Indexer 只用于比较 KVEvents 精确 locality。example/mock 最多是 `simulated`，不形成实验完成门槛或性能结论。
- **详情：** [Serving 路由与平台控制面详细知识列表](topics/10-serving-routing-and-control-plane.md)

### 11｜并发、异步与状态机

- **优先级：** P0
- **状态：** 已敲定范围与手写契约，原理复习、源码 trace 与闭卷手写待完成
- **目标熟练度：** 原理 L3 / 源码 L1 / 手写 L3 / 实验 L0
- **能力结果：** 能从执行单元、调度等待、同步容量、生命周期和正确性五层解释 Serving 异步控制流，讲清 Python `async/await`、timeout/cancellation、背压与 fencing，并限时手写带六个确定性测试的有界异步执行器。
- **边界：** 以跨语言并发语义和 Python `asyncio` 为主；不展开 Go 并发、CPython/event-loop 深层实现、无锁结构、网络服务器/RPC 框架或独立性能实验。
- **支持主题：** KV Cache 与内存系统、LLM 推理引擎与调度、分布式 Serving 数据路径与 PD 分离、Serving 路由与平台控制面。
- **源码与手写：** 固定一个 Python 版本追踪 `asyncio.run -> Task/Future -> 恢复/取消/清理`，固定一个 vLLM 版本追踪异步请求取消链；从空文件实现约 80-120 行 `BoundedAsyncExecutor`，队列满立即抛出 `ExecutorOverloaded`，timeout 后晚到结果不得改写终态。
- **关联项目：** 为 ToolGap-KV 的 lifecycle epoch、异步 completion fencing、取消、fallback 和 cleanup 提供通用基础；源码阅读、mock 和代码练习不能标记为项目 `shipped`，受控交错最多是 `simulated`。
- **详情：** [并发、异步与状态机详细知识列表](topics/11-concurrency-async-state-machines.md)

### 12｜模型加载、权重管理与推理引擎启动链路

- **优先级：** P1；其中启动阶段、内存构成、KV 容量关系和失败定位属于面试启动前的 P0 防守要求
- **状态：** 已敲定源码主线与最小复现，原理、源码 trace 和正常/失败/修正运行待完成
- **目标熟练度：** 原理 L2 / 源码 L2 / 手写 L0 / 实验 L1
- **能力结果：** 能沿固定版本 vLLM 解释配置校验、worker/model runner、loader、rank-local 权重映射、显存 profiling、KV Cache 初始化、warmup 和 ready/failure，并根据日志与显存变化定位启动失败。
- **边界：** 聚焦单引擎从进程启动到 ready；不手写 model loader/checkpoint parser，不做冷启动 benchmark、多节点加载、CUDA allocator 深挖或 Kubernetes/Ray rollout。
- **依赖主题：** KV Cache 与内存系统、性能分析与实验方法、量化与低精度推理、多 GPU 模型执行与集合通信、Serving 路由与平台控制面。
- **源码与复现：** 固定一个 vLLM release/commit 和模型 revision，完成一次小模型正常启动、一次主动制造的 `max_model_len`/KV 预算类失败及一次修正后的 ready 复测；真实证据只支持固定环境的启动行为，不形成通用性能结论。
- **关联项目：** 可复用模型兼容性、KV 容量和 engine-ready 前置条件；模型加载与启动优化不属于 ToolGap-KV CT1-CT3，源码阅读和 Topic 12 复现不能标记为项目 `shipped`。
- **详情：** [模型加载、权重管理与推理引擎启动链路详细知识列表](topics/12-model-loading-weight-management-and-engine-startup.md)

### 13｜C++ 系统编程防守

- **优先级：** P1；其中资源所有权、对象生命周期和基础同步属于面试启动前的 P0 防守要求
- **状态：** 已敲定恢复范围；原理复习、连续追问和两项闭卷手写待完成
- **目标熟练度：** 原理 L2 / 源码 L0 / 手写 L2 / 实验 L0
- **能力结果：** 恢复 C++ 系统编程的面试表达与小型实现能力，能讲清 RAII、智能指针、拷贝/移动、虚函数、STL 失效、mutex/condition variable/atomic 和构建链路，并限时手写 move-only RAII wrapper 与可关闭的 `BlockingQueue<T>`。
- **边界：** 不重写 WebServer、线程池或内存池，不手写 allocator/STL/`shared_ptr`，不深入模板元编程、复杂 ABI、lock-free 或 CUDA/C++ kernel；算法题继续使用 C++，但与本节点的系统手写分别验收。
- **支持主题：** 并发、异步与状态机；为 Serving 中的 buffer 所有权、异步完成、数据竞争和关闭清理提供语言层防守。
- **项目边界：** ToolGap-KV 答辩树独立维护，不并入通用知识地图；C++ 练习不构成项目 `shipped` 或 `experimentally validated` 证据。
- **详情：** [C++ 系统编程防守详细知识列表](topics/13-cpp-systems-programming-defense.md)

## 面试就绪门槛

只有同时满足以下条件，才能把对应 P0 主题标记为完成：

- 达到节点声明的四维目标等级；
- 限时手撕通过本地测试，而不是只看过参考实现；
- 原理追问能够脱稿回答，并记录答错后的修正；
- 源码与实验结论能够指向真实路径、命令和产物；
- 项目相关表述保持 `roadmap`、`shipped`、`experimentally validated`、`simulated` 的证据边界。
