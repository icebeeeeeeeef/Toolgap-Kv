# 05｜性能分析与 GPU 最小认知详细知识列表

> 优先级：P0
>
> 当前状态：已有零散 benchmark 要求，尚未形成统一方法并完成验收
>
> 目标熟练度：原理 L2 / 源码 L0 / 手写 L0 / 实验 L2
>
> 依赖：[PyTorch 与张量编程](01-pytorch-tensor-programming.md)、[Transformer 推理原理与手撕](02-transformer-inference-and-handwriting.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能用最小但正确的 GPU 性能模型解释 LLM Serving：知道计算、HBM 容量/带宽、CPU-GPU 数据移动、异步执行和排队分别如何影响 Prefill、Decode、KV Cache 与 restore；能够设计可复现的 benchmark，并拒绝由错误计时、错误 workload 或单一平均值导出的结论。

这是一个紧凑的防守节点，预计集中投入约 6-10 小时。它不要求源码阅读或领域手写，也不单独建设新项目；验收直接复用其他主题的实验产物。

## 为什么保留、为什么不继续深入

完全不了解 GPU 会导致无法回答：为什么 Decode 常受带宽和容量约束、为什么 KV Cache 占用 HBM、为什么 CUDA 朴素计时错误、为什么 D2H/H2D 可能伤害 active decode，以及低精度为什么影响容量和吞吐。

但目标岗位不负责算子实现，因此学习目标停在“解释系统行为并正确测量”。能够指出问题更可能来自计算、访存、数据搬运、同步还是调度即可；不要求独立优化 kernel。

## P0 详细知识列表

### 计算与内存直觉

- CPU 与 GPU 在顺序控制、并行吞吐和任务粒度上的基本差异；
- kernel、thread block、warp、SM 之间的概念关系，只要求能画出层次；
- HBM 的容量与带宽是两个不同约束；
- register、shared memory、cache 只需知道比 HBM 更靠近计算，不背硬件参数；
- 计算量、内存访问量和 Arithmetic Intensity 的定性关系；
- compute-bound、memory-bound 与 latency/launch-bound 的基本判断；
- batch、sequence length 和并发变化可能改变瓶颈，不能给 Prefill/Decode 贴永恒标签。

### 映射到 LLM Serving

- Prefill 通常具有更高并行度和矩阵乘强度，为什么更容易利用算力；
- 单 token Decode 为什么反复读取权重和历史 KV，更容易受带宽、batch 和调度影响；
- KV Cache 消耗的是 HBM 容量，也会产生读取流量；
- PagedAttention 解决管理和寻址问题，不自动消除 HBM 带宽成本；
- Continuous Batching 如何改变有效 batch、设备利用率和尾延迟；
- offload/restore 引入 D2H/H2D、排队、同步与 active-request 干扰；
- 优化可能减少计算、减少访存、隐藏传输或改善调度，必须区分归因。

### CUDA 异步与数据移动常识

- CPU 发起 GPU 工作后通常不会等待其立刻完成；
- 为什么不做同步的 `time.time()` 可能只测到 launch；
- warmup、显式同步、重复和分位数的用途；
- stream/event 只要求理解顺序、并发与依赖，不要求手写复杂多流程序；
- CPU↔GPU 数据移动经过的基本路径；
- pageable 与 pinned host memory 的用途和代价，只需会解释实验现象；
- PCIe/NVLink 只要求理解它们约束设备间传输，具体带宽以现场环境测量为准。

### 精度与容量直觉

- FP32、FP16、BF16 的字节数、动态范围和精度基本差异；
- FP8、INT8、INT4 能减少权重/KV 容量和传输量，但会引入 scale、kernel 支持和质量边界；
- dtype 变小不保证端到端等比例加速；
- 量化算法、校准、量化 kernel 和质量评估留给独立量化主题。

### 可信实验方法

- 固定模型、版本/commit、硬件、driver/runtime、dtype 和启动参数；
- 保存 exact command、workload manifest 和原始结果；
- 分离 cold start、warmup 与 steady state；
- 同时报告请求/token 吞吐、TTFT、ITL/TPOT 和端到端延迟；
- 使用 p50/p95/p99，并记录样本量和重复次数；
- 对显存区分逻辑容量、allocated、reserved 和进程/设备可见值；
- 比较策略时保持 executor、workload、预算和测量窗口一致；
- 保留 losing workload、负面结果和无法归因的结果；
- simulator 结论标记为 `simulated`，真实路径证据才可标记为 `experimentally validated`。

## P1 补充

- 用 PyTorch Profiler 或 Nsight Systems 定位 CPU gap、kernel 时间和数据搬运；
- CUDA Graph 降低 launch/CPU overhead 的基本收益与静态约束；
- stream/event overlap 的小实验；
- pinned/pageable memory 与不同传输尺寸的带宽实验；
- Roofline 的定量计算；
- 多 GPU 拓扑、PCIe/NVLink、NUMA 对通信和 offload 的影响；
- GPU utilization、memory utilization 等监控指标的误读边界。

## P2/P3 延后

- CUDA C++ 或 Triton kernel 手写；
- PTX/SASS 和指令级分析；
- warp scheduler、occupancy calculator 与寄存器压力调优；
- shared-memory bank conflict 深入优化；
- Tensor Core MMA/WGMMA 指令和 layout 编程；
- 针对特定 GPU 微架构的算子极致调优。

## 验收任务

### A. 修正错误 CUDA 计时

1. 对同一 PyTorch CUDA 操作分别使用错误的朴素计时和正确的同步计时；
2. 加入 warmup、重复与 p50/p95；
3. 说明两组数字差异来自什么；
4. 无可用 GPU 时保留脚本和预期现象，但不能把它标记为 `experimentally validated`。

通过标准：能够现场指出缺少 warmup、同步、重复或 workload 描述的 benchmark 为什么不可信。

### B. Serving 瓶颈归因

从 Transformer、KV Cache 或调度主题选择一个已有实验，回答：

1. 改动主要改变计算、HBM 容量/流量、CPU-GPU 传输还是调度排队；
2. 哪些观测支持该归因；
3. 哪个替代解释尚未排除；
4. 至少给出一个预期不获益或变差的 workload。

通过标准：不使用“GPU 利用率提高所以整体更快”一类单指标结论。

### C. ToolGap-KV 实验清单审查

对一条 retain/offload/recompute 实验记录检查：

- pinned vLLM/model/environment；
- workload、并发、上下文和 tool-gap 分布；
- queue/store/restore/recompute/first-token 分解；
- active request 与 resumed request 的 p50/p95/p99；
- 输出正确性、清理和容量回到基线；
- `roadmap`、`simulated`、`experimentally validated` 状态正确。

通过标准：能够拒绝环境不固定、只报平均值、只报 winning case 或无法区分 requested/observed path 的结论。

## 面试连续追问

- 为什么 Prefill 常被称为 compute-bound，Decode 常被称为 memory-bound？哪些场景会例外？
- HBM 容量和 HBM 带宽分别限制什么？
- 为什么 PagedAttention 减少碎片不等于 Attention 不再受带宽约束？
- CUDA 异步执行为什么会让朴素计时过小？
- warmup 在排除什么？为什么还需要多次重复和分位数？
- FP16/BF16/FP8/INT8 变小后为什么不保证端到端等比例加速？
- D2H/H2D restore 为什么可能拖慢正在 Decode 的请求？
- GPU utilization 很低或很高分别能证明什么、不能证明什么？
- throughput 提升但 TTFT/p99 变差时，优化是否成功？
- simulator 与真实引擎结果偏差时，应该相信哪个，如何校准？

## 完成证据

- 一份错误/正确 CUDA 计时对照；
- 一份包含环境、命令、workload、重复和分位数的 benchmark 记录；
- 一次 Serving 瓶颈归因与替代解释；
- 一个 losing workload；
- 一次 ToolGap-KV 实验清单审查；
- 一次 15 分钟 GPU/测量防守追问；
- 所有性能表述保持仓库 claim state 边界。

## 当前官方参考

- [PyTorch CUDA semantics](https://docs.pytorch.org/docs/stable/notes/cuda.html)
- [PyTorch benchmark recipe](https://docs.pytorch.org/tutorials/recipes/recipes/benchmark.html)
- [PyTorch Profiler recipe](https://docs.pytorch.org/tutorials/recipes/recipes/profiler_recipe.html)
- [NVIDIA CUDA C++ Programming Guide](https://docs.nvidia.com/cuda/cuda-c-programming-guide/)
