# 12｜模型加载、权重管理与推理引擎启动链路详细知识列表

> 优先级：P1；包含面试启动前必须完成的 P0 防守子集
>
> 当前状态：已敲定源码主线与最小复现，原理、源码 trace 和正常/失败/修正运行待完成
>
> 目标熟练度：原理 L2 / 源码 L2 / 手写 L0 / 实验 L1
>
> 预计投入：集中学习约 6-10 小时，实际完成以验收证据为准
>
> 依赖：[KV Cache 与内存系统](03-kv-cache-memory-system.md)、[性能分析与 GPU 最小认知](05-performance-analysis-and-gpu-literacy.md)、[量化与低精度推理](07-quantization-and-low-precision-inference.md)、[多 GPU 模型执行与集合通信](08-multi-gpu-model-execution-and-collectives.md)、[Serving 路由与平台控制面](10-serving-routing-and-control-plane.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能沿固定版本 vLLM 的真实链路解释初始化的数据流、控制流、内存变化与失败边界：

```text
CLI / EngineArgs
  -> 模型、dtype、量化和并行配置校验
  -> device / distributed environment 初始化
  -> worker / model runner 创建
  -> model loader 选择
  -> 模型结构创建与权重加载
  -> rank-local weight shard 映射
  -> memory profiling
  -> KV Cache 容量计算与初始化
  -> warmup / CUDA Graph 准备
  -> engine ready
```

回答必须区分：

- 进程已经启动；
- 模型配置已经解析；
- 模型对象已经创建；
- 权重已经加载；
- KV Cache 已经初始化；
- warmup/可选 graph capture 已经完成；
- 服务真正 ready 并能完成请求。

本节点采用“启动全链路源码 + 单次故障复现”。不只整理配置参数，也不建设加载性能工程项目。

## 与已有节点的责任边界

1. Topic 07 负责量化数值语义、兼容性和 kernel dispatch；本节点只解释量化配置与权重怎样进入 loader；
2. Topic 08 负责 TP 数学、rank/group 和 collective；本节点只解释 rank 怎样获得自己的 weight shard；
3. Topic 05 负责 benchmark 可信度；本节点不比较冷启动性能；
4. Topic 03 负责运行时 KV block 生命周期；本节点只负责启动时 KV 容量的计算与分配；
5. Topic 10 负责副本扩容、placement 和 readiness 消费；本节点只负责单个 engine 何时能够声明 ready。

知道 rank 怎样调用 loader 不等于掌握 TP 数学；知道量化 loader 成功也不等于证明目标 quantized kernel 已经执行。各节点必须分别完成自己的证据门槛。

## P0 防守要求

开始目标岗位面试前，应能脱稿回答：

1. 为什么模型权重文件大小、CPU 内存峰值、GPU 显存峰值和 steady-state 显存不同；
2. 模型权重理论上能够放入 GPU，为什么启动时仍可能 OOM；
3. Safetensors 与 PyTorch checkpoint 在安全性、元数据和加载方式上的基本差异；
4. FP32、BF16、FP16 和量化权重怎样影响文件大小、加载路径和运行 dtype；
5. 为什么使用 meta device、empty initialization 或 shard-aware loading；
6. TP 模型完整加载后切分与每个 rank 只加载自己的 shard 有什么内存和 I/O trade-off；
7. model config、revision、tokenizer、权重 shape 或量化配置不兼容时可能在哪里失败；
8. `gpu_memory_utilization`、`max_model_len`、KV Cache block 数和并发容量之间有什么因果关系；
9. 为什么权重加载完成后还要进行 memory profiling、KV Cache 初始化和 warmup；
10. CUDA Graph 为什么可能降低运行开销，却增加启动时间、显存占用和 shape 约束；
11. 为什么“进程启动”“模型加载完成”和“服务 ready”不是同一个状态；
12. 怎样根据日志与显存变化判断失败发生在权重加载、KV Cache 分配还是 warmup 阶段。

P0 防守不要求背全部参数或精确类名。通过标准是能够画出启动链、解释主要资源项，并完成后文的连续故障场景题。

## 原理 L2 详细知识列表

### 模型身份与配置

- model ID、本地路径、revision、config revision 和 tokenizer revision 的关系；
- architecture、hidden size、layer/head 数、context length 和 vocabulary 怎样约束权重 shape；
- dtype 自动选择、显式覆盖和硬件兼容性；
- quantization、load format、trust-remote-code 和模型实现选择在配置阶段的作用；
- TP/PP degree、rank/world size 与模型结构整除条件；
- 配置校验应尽早拒绝不兼容组合，避免加载大量权重后才失败；
- 固定模型 revision、引擎 commit 和启动参数是可复现 trace 的前提。

### 权重格式与加载路径

- checkpoint index、单文件和多 shard 文件的组织直觉；
- Safetensors 与 pickle-based checkpoint 的基本安全和加载差异；
- loader 怎样根据 load format、模型类型、量化方法或可选依赖选择路径；
- 模型参数名、checkpoint key 和运行时 module 之间需要映射；
- tied weights、stacked parameters、QKV 或 gate/up 等布局可能需要特殊映射；
- missing、unexpected 或 shape-mismatched weights 应显式失败或遵循可解释规则；
- lazy、streaming 或 shard-aware load 的目标是降低峰值复制和无关 I/O，不保证启动时间一定更短。

只理解格式和 loader 契约，不实现 Safetensors parser、checkpoint index 或 converter。

### 加载期间的内存生命周期

- 磁盘文件大小不等于 CPU RSS、GPU allocated、GPU reserved 或启动峰值；
- checkpoint buffer、反序列化对象、模型参数、临时转换张量和 allocator cache 可能同时存在；
- meta/empty initialization 用无存储参数结构避免先随机初始化完整模型；
- dtype cast、layout conversion、parameter packing 或设备搬运可能产生临时峰值；
- 权重、KV Cache、workspace、CUDA Graph pool 和运行时保留显存共同竞争 HBM；
- allocated、reserved、device free memory 与框架可安全使用预算不是同一指标；
- worker 或部分 rank 初始化失败时，需要考虑进程组和显存资源清理。

只要求根据日志和阶段内存快照归因，不学习 CUDA allocator 源码、mmap 或 page-cache 实现。

### TP 与量化权重映射

- 每个 rank 建立相同逻辑模型，但可能只物化本地参数 shard；
- load-then-slice、每 rank 重复读取和 shard-aware load 具有不同峰值内存与 I/O；
- Column/Row/QKV/Embedding 的切分数学归入 Topic 08，本节点只追踪 loader 怎样获得 rank-local tensor；
- checkpoint 原始 shard 边界不一定等于 TP rank 边界，可能需要重新切片或映射；
- quantized weight、scale、zero point 或 packing metadata 必须与运行时 module 和 kernel contract 匹配；
- 量化 loader 成功不证明目标 kernel 被使用，dispatch/fallback 归入 Topic 07；
- 多 rank 中任一加载失败都可能阻止 engine ready，需要保存 rank-specific 日志。

### KV Cache 初始化、warmup 与 readiness

- 权重加载后通过 profiling 或预算计算估计可供 KV Cache 使用的显存；
- `gpu_memory_utilization` 是预算策略的一部分，不等于实际业务显存占用比例；
- bytes per token、layer 数、KV heads、head size、dtype 和 block size 共同决定 KV 容量；
- `max_model_len`、最大并发、block 数和调度容量必须在同一预算下成立；
- KV block pool 创建后仍可能需要 workspace、warmup 和可选 CUDA Graph 资源；
- warmup 用代表性 shape 初始化执行路径、触发必要的 lazy work 或验证模型运行；
- CUDA Graph 只要求理解捕获前置条件、额外内存和静态 shape/地址约束；
- ready 必须晚于必要 worker、模型、KV Cache 和执行路径全部准备完成；
- 失败时要明确 fail fast、降级 eager、缩小容量还是停止服务，不能错误暴露 readiness。

## 源码 L2 契约

### 固定主实现

学习开始时固定一个 vLLM release/commit、一个 model revision 和一套真实启动参数。具体类名和函数名以该版本为准，不追逐浮动 `main`。

沿以下链路完成一次 source trace：

```text
CLI / EngineArgs
  -> engine/model/cache/parallel configuration
  -> device and distributed initialization
  -> worker / executor / model runner construction
  -> model loader selection
  -> model construction and load_weights
  -> rank-local parameter mapping
  -> memory profiling / available-memory decision
  -> cache configuration and allocation
  -> warmup / optional graph capture
  -> ready or initialization failure
```

源码笔记必须保存项目、release/commit、model revision、入口、关键对象、控制流、内存所有者、失败传播和阶段图，并回答：

- 用户参数怎样进入最终 engine、model、parallel 和 cache 配置；
- 哪个对象创建模型，哪个对象选择 loader，哪个对象执行权重映射；
- load format 和量化配置怎样选择真实路径；
- 加载期间哪些对象可能同时持有 CPU/GPU 权重或临时张量；
- rank identity 怎样影响参数 shard；
- 引擎怎样得到可用显存并换算为 KV block 数；
- `max_model_len` 与 cache capacity 在哪里校验；
- warmup/CUDA Graph 在 ready 前完成什么；
- 初始化异常怎样跨 worker/executor 传播并触发清理；
- 哪些步骤属于 vLLM，哪些属于 Transformers、PyTorch、量化库或 CUDA runtime。

不精读 Transformers 全部加载实现、PyTorch serialization、CUDA allocator、NCCL 初始化或 CUDA Graph 内部捕获逻辑。

## 手写 L0 契约

不要求从空文件实现：

- model loader、checkpoint parser 或 tensor-name mapper；
- meta-device 模型构造框架；
- TP/PP checkpoint resharding；
- 显存 allocator、KV Cache allocator 或 CUDA Graph manager；
- checkpoint converter、下载器或分布式加载服务。

面试要求伪代码时，只需画阶段状态机、资源项和失败分支。源码 trace 与故障复现已经能够验证本节点需要的工程判断，独立手写上述组件的性价比过低。

## 实验 L1 契约

### 固定环境清单

使用现有本地或云端环境能够稳定运行的小模型，不强制目标大模型、多 GPU、量化模型或生产部署。记录：

- vLLM release/commit 与安装方式；
- model ID 和 revision；
- GPU/CPU、显存/内存、driver/runtime 和 dtype；
- 完整启动命令与环境变量；
- 是否启用 TP、量化、eager/CUDA Graph；
- 原始日志和观察时间点。

### 正常启动 trace

完成一次从命令启动到 ready 的真实运行，保存：

- 各阶段关键日志和时间顺序；
- config、worker/model runner、loader、memory profiling、KV Cache 与 warmup 的源码锚点；
- 进程 CPU 内存与 GPU 显存的阶段性变化；
- 最终 ready 证据和一个最小请求成功证据；
- 一张阶段表：

| 阶段 | 关键对象 | 内存变化 | 成功证据 | 可能失败 |
|---|---|---:|---|---|
| 配置校验 | Engine/model config | 小 | 配置构造完成 | revision/dtype/并行配置不兼容 |
| 权重加载 | Loader/model runner | 大 | 参数加载完成 | OOM、missing/shape mismatch |
| KV 初始化 | Cache config/allocator | 大 | block 数确定并分配 | context 或容量不足 |
| Warmup | Model runner | 额外开销 | engine ready | graph、shape 或显存失败 |

不要求高精度测量加载时间，也不比较多个 loader 或配置的性能。

### 主动失败与修正复测

优先通过过大的 `max_model_len` 或不合理的 KV 显存预算，使固定环境在 KV capacity 校验附近产生可解释失败。如果固定版本更早在配置阶段拒绝该组合，同样属于有效证据；必须以真实日志为准，不能为符合预想强行解释。

完成以下闭环：

1. 运行前预测失败阶段和原因；
2. 保存命令、原始日志、显存状态和异常；
3. 根据源码确认属于配置、权重、KV capacity 还是 warmup；
4. 只修改一个直接相关变量，并说明牺牲的 context、并发、精度、graph 能力或硬件成本；
5. 重新运行到 ready，并完成一个最小请求；
6. 记录预测与实际不一致之处。

真实运行只能标记为该固定环境启动行为的 `experimentally validated`；mock、他人日志或只读源码最多是 `simulated`。单次启动不能外推为冷启动性能、所有模型兼容性或生产可靠性结论。

## 场景题验收

至少完成一道 15 分钟连续场景题：

> 一个 BF16 模型的权重能够成功加载到 24 GB GPU，但随后引擎在 KV Cache 初始化或 warmup 阶段失败。日志显示剩余可用显存不足，同时配置了较大的 `max_model_len` 和较高并发目标。请定位失败阶段，解释显存组成，给出调整顺序，并说明每种调整牺牲了什么。

回答必须建立资源式：

```text
权重显存
+ KV Cache
+ 临时 workspace
+ CUDA Graph / warmup 额外占用
+ allocator reserved / fragmentation
= 实际启动显存需求
```

并覆盖：

1. 从日志确认失败阶段，而不是把所有失败归因于权重；
2. 验证 model revision、dtype、量化和 TP 配置；
3. 区分 `max_model_len`、KV block 数、最大并发和实际 workload；
4. 根据目标调整 context、并发、dtype/量化、TP 或 graph 配置；
5. 重新运行并验证服务真正进入 ready；
6. 不把“成功启动”描述成性能更优。

## 与 ToolGap-KV 的边界

本节点可以为 ToolGap-KV 提供模型配置兼容性、KV 容量和 engine-ready 前置条件的理解，也能帮助解释为什么生命周期 runtime 只能在物理 KV 数据面可用后开始工作。

当前能力状态保持：

- 模型加载、checkpoint 格式和 CUDA Graph 不属于 ToolGap-KV CT1-CT3；
- 阅读 vLLM loader 或完成 Topic 12 实验不能标记为 ToolGap-KV `shipped`；
- 不为 ToolGap-KV 新增自定义 model loader、checkpoint converter 或启动优化功能；
- 固定环境的真实运行只验证该环境中的启动行为；
- 只有仓库出现候选人拥有的接口、测试和证据后，才能提升对应项目声明。

## 明确不要求

- 手写 Safetensors、pickle/checkpoint parser 或 checkpoint index；
- 实现 Hugging Face 模型转换、下载和缓存工具链；
- 深入 mmap、page cache、direct I/O 或文件系统实现；
- 深入 PyTorch serialization、CUDA allocator 或 CUDA Graph 源码；
- 完整恢复 vLLM 支持的全部 loader、model architecture 或量化格式；
- 多节点并行加载、distributed checkpoint、对象存储和远端 streaming load；
- model loader、KV allocator 或 graph manager 手写；
- 多模型、多 GPU、多 loader 的冷启动 benchmark；
- Kubernetes/Ray autoscaling、镜像分发或生产 rollout；
- 把单次启动结果包装成通用性能、兼容性或生产可靠性结论。

## 完成证据

只有以下材料齐全，节点才能标记为完成：

- 一张固定版本 vLLM 启动链路图；
- 一份关键源码路径、对象所有权、失败传播和清理笔记；
- 一次正常启动的完整命令、原始日志和阶段显存表；
- 一次主动制造的启动失败及根因分析；
- 一次修正配置后的成功复测和最小请求；
- 一轮十二道 P0 口述题、连续场景题和错误修正记录。

建议顺序是：先建立内存构成和阶段模型，再运行正常启动建立日志锚点，然后读通对应源码，最后制造失败并复测。这样源码阅读有真实现象作为索引，不会退化为无边界浏览 vLLM 仓库。
