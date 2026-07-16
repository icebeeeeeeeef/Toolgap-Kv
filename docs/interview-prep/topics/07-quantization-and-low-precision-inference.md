# 07｜量化与低精度推理详细知识列表

> 优先级：P1；包含面试启动前必须完成的 P0 防守子集
>
> 当前状态：已敲定非 kernel 岗位范围，原理、源码阅读与实验均待完成
>
> 目标熟练度：原理 L3 / 源码 L2 / 手写 L0 / 实验 L2
>
> 依赖：[PyTorch 与张量编程](01-pytorch-tensor-programming.md)、[Transformer 推理原理与手撕](02-transformer-inference-and-handwriting.md)、[KV Cache 与内存系统](03-kv-cache-memory-system.md)、[性能分析与 GPU 最小认知](05-performance-analysis-and-gpu-literacy.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能从有限数值表示出发解释量化误差、粒度、校准和异常值处理，区分权重、激活与 KV Cache 量化，说明存储 dtype、计算 dtype、累加 dtype 和 kernel 支持如何共同影响显存、吞吐、延迟与质量；能够读懂固定版本 vLLM 的量化集成路径，并运行、修改和解释一份完整复现实验。

这是独立的 P1 工程实践节点，预计集中投入约 10-16 小时。节点不以算子开发为目标，手写维度为 L0；完成标准是形成原理、源码集成和实验判断能力，而不是重写生产量化实现。

## P0 防守要求

开始目标岗位面试前，应能脱稿回答以下问题：

1. 浮点张量为什么能够映射到有限整数范围，`scale`、`zero_point`、round、clip 和 dequantize 分别做什么；
2. symmetric 与 asymmetric quantization 的表示、误差和元数据差异；
3. per-tensor、per-channel 与 group-wise 量化的精度、scale 数量和执行代价；
4. PTQ 与 QAT、static 与 dynamic quantization 的目的和适用边界；
5. weight-only、weight-activation 与 KV Cache 量化分别减少什么资源；
6. W8A8、W4A16、FP8 等写法分别描述了哪些表示或计算路径；
7. calibration dataset、outlier 和敏感层为什么会影响量化质量；
8. 模型文件或显存变小为什么不保证端到端吞吐提高；
9. 缺少匹配硬件、shape 或 kernel 时可能发生什么 fallback，以及为什么可能比 BF16 更慢；
10. 量化结果为什么必须同时检查质量指标和 Serving 指标。

通过标准：完成一次 10 分钟连续追问，并能手算一个简单张量的 scale、量化值、反量化值和误差。不要求现场写代码。

## P1 详细知识列表

### 数值表示与误差

- 浮点与定点/整数表示的动态范围、精度和存储差异；
- 线性 uniform quantization 的 quantize/dequantize 语义；
- 舍入误差、截断、饱和和 clipping range；
- symmetric/asymmetric 与 signed/unsigned 表示；
- scale、zero point、group metadata 的存储成本；
- per-tensor、per-token、per-channel、group-wise 等粒度共享 scale 的含义；
- group size 变小时精度、元数据、访存和 kernel 效率可能发生的变化；
- 存储 dtype、输入 dtype、计算 dtype、累加 dtype 和输出 dtype 必须分别说明。

要求不是背诵量化名词，而是能从“有限编码范围如何近似原始分布”推导误差来源和设计取舍。

### 量化阶段与对象

- PTQ、QAT、static calibration 和 runtime dynamic quantization；
- weight-only quantization 主要减少权重容量和读取流量，但激活通常仍保持较高精度；
- weight-activation quantization 对激活分布、outlier 和校准提出额外要求；
- KV Cache 量化改变历史 K/V 的容量、读取/传输字节、scale 元数据和数值误差；
- KV Cache 量化与权重量化使用不同配置和数据路径，不能混为一种能力；
- FP8 与 INT8/INT4 在编码、动态范围、scale、硬件支持和 kernel 路径上的基本差异；
- mixed precision 和保留敏感层高精度的原因。

### 常见方法的定位

只要求能够说明各方法主要解决的问题、作用阶段和工程代价，不要求逐一推导论文或复现算法：

- GPTQ：面向权重的离线量化和误差补偿直觉；
- AWQ：利用激活统计保护重要权重的直觉；
- SmoothQuant：在权重与激活之间平滑/迁移 outlier 难度的直觉；
- 常见 weight-only、W8A8 和 FP8 路线如何映射到不同硬件与 Serving 条件。

面试回答必须先声明讨论的是权重、激活还是 KV Cache，以及量化发生在离线转换、加载阶段还是运行时。

### Serving 性能与质量边界

- 权重存储变小、HBM 读取量减少与真实 kernel 加速之间的区别；
- packed weights、fused dequantize/GEMM 和专用 kernel 为什么决定运行时收益；
- dequantize、scale 读取、layout 转换和 launch overhead 可能抵消收益；
- batch、矩阵 shape、GPU 架构和并行方式会改变量化 kernel 的适用区间；
- 更大的可用 KV 容量或 batch 可能带来间接吞吐收益，不能错误归因为单 kernel 加速；
- throughput、TTFT、ITL/TPOT、端到端延迟和显存必须联合报告；
- perplexity、标准任务或领域评测与“生成文本看起来正常”的证据强度不同；
- 长上下文、特定层和异常输入可能暴露平均质量指标遗漏的问题；
- fallback、部分层回退高精度和 unsupported configuration 必须被观测，而不是只看启动参数。

## 源码阅读与参考复现实验契约

### 触发与边界

量化在已收集问题中主要作为原理和工程 trade-off 出现；对当前非 kernel 岗位，它不是需要候选人拥有生产算子实现的核心控制流模块。因此不要求从空文件重写量化 Linear 或 kernel，但源码 L2 和实验 L2 仍要求把数值语义映射到真实引擎。

### 主实现锚点

- 主实现选择 vLLM，并在正式学习开始时记录固定 release/commit，不追随浮动 `main`；
- 选择一个与该版本、模型和实际硬件兼容的代表性量化方案完成主实验；
- 第二种算法、框架或第三方量化库只有在 JD 明确要求，或需要回答一个具体质量/性能 trade-off 时才加入；
- 与 ToolGap-KV 使用的引擎版本不一致时，分别保存学习锚点与项目锚点。

### 源码深度

需要能够沿以下路径定位真实对象和分支：

```text
model/config metadata
  -> quantization method 选择与兼容性检查
  -> quantized weight / scale / zero-point 加载
  -> layer quant method 绑定或替换
  -> hardware、dtype、shape 与 kernel capability 检查
  -> kernel dispatch / fallback
  -> model execution 与观测结果
```

完成源码阅读后必须回答：

- 模型声明的量化格式如何进入引擎配置；
- 权重、scale、zero point 或其他元数据如何加载和校验；
- Linear/Attention 等层如何选择量化执行方法；
- kernel dispatch 依赖哪些硬件、dtype、shape 或可选依赖；
- unsupported configuration 是显式失败、静默回退还是部分层回退；
- 权重量化配置与 KV Cache dtype 配置为什么进入不同路径；
- 哪些代码属于 vLLM glue，哪些属于第三方库或 CUDA kernel；
- 当前学习为什么停在 kernel 接口、输入输出和性能边界，而不进入 kernel 内循环。

### 完整参考实验

可以使用官方或可信实现，不要求独立重写量化算法，但必须完成：

1. 从环境、模型、量化配置到评测结果完整运行一次；
2. 逐段解释量化表示、scale/metadata、加载、dispatch、推理和评测发生在哪里；
3. 主动修改至少一个变量，例如 bit width、group size、量化粒度或执行配置；
4. 在运行前预测容量、误差或性能的变化，并用结果修正判断；
5. 保存 exact command、版本、模型 revision、硬件、原始结果和失败/回退信息。

只复制命令并得到输出不算完成；能够解释实现但没有实际运行，也不满足实验 L2。

### Baseline 与量化对照

使用相同 target model 或可证明等价的基线，比较 BF16/FP16 与一种量化权重方案：

- 固定框架 commit、模型 revision、硬件、并行配置、workload 和测量窗口；
- 记录磁盘模型大小、加载时间和 GPU 显存；
- 记录请求/token throughput、TTFT、ITL/TPOT 和端到端延迟；
- 至少使用一种 perplexity、标准任务或明确的领域质量指标；
- 记录实际 dispatch 的 quantization method/kernel 或 fallback；
- 至少保留一个“容量下降但性能没有提高”或发生回退的案例；
- 解释改变来自权重字节、可用 batch、kernel、额外 dequantize 还是其他因素。

KV Cache 量化实验是 ToolGap-KV 相关的 P1 加分项；只有固定引擎与硬件确实支持并能记录质量/格式边界时才执行，不阻塞本节点完成。

### 可选数值练习

可以写一个约 20 行的 `quantize -> dequantize -> error` notebook，对比不同粒度或 clipping range。它只用于固化公式，不是量化算子，不设限时要求，也不计入节点完成门槛。

## 明确不要求

- 手写 quantized Linear、整数 GEMM 或 fused dequantize/GEMM；
- INT4 bit packing、layout 编码或模型文件格式实现；
- 自定义 PyTorch/C++ operator；
- CUDA/Triton kernel、PTX/SASS 或 Tensor Core 指令；
- 独立复现 GPTQ、AWQ、SmoothQuant 或完整模型转换工具链；
- 建立 QAT 训练体系；
- 为所有硬件和量化方案建立 benchmark 矩阵；
- 把某个模型、GPU 或 workload 的质量/性能结果外推为通用结论。

## 与 ToolGap-KV 的边界

KV Cache 低精度表示可能改变 HBM 容量、D2H/H2D 传输字节、scale/格式元数据、restore 后的可消费性和长上下文输出质量，因此项目深挖需要能解释它与 retain/offload/recompute 的潜在交互。

但量化不是 CT1-CT3 主线。除非仓库出现真实接口、兼容性测试、质量评测和实验产物，否则：

- 不实现量化 kernel 或模型转换；
- 不把“支持 KV Cache 量化”描述为 `shipped`；
- 不把参考实验结果外推为 ToolGap-KV 已完成集成；
- 可以把 KV dtype 作为 `roadmap`、兼容性风险或实验控制变量。

## 面试连续追问

- scale 和 zero point 是什么？为什么 asymmetric quantization 需要 zero point？
- per-tensor、per-channel 和 group-wise 分别有什么 trade-off？
- group size 越小是否一定越好？
- PTQ、QAT、static 和 dynamic quantization 如何区分？
- W4A16 和 W8A8 分别意味着什么？真正计算时一定使用 INT4/INT8 吗？
- weight-only 量化减少了什么，为什么不一定减少激活或 KV Cache？
- 激活 outlier 为什么会破坏低比特量化？AWQ 与 SmoothQuant 的处理方向有什么不同？
- FP8 与 INT8 的主要表示和硬件差异是什么？
- 为什么模型显存下降一半，吞吐可能几乎不变甚至下降？
- 如何确认 vLLM 实际选择了量化 kernel，而不是 fallback？
- 为什么权重量化和 KV Cache 量化需要分别配置与验证？
- KV Cache 量化可能如何影响长上下文质量和 restore 格式兼容性？
- 你会用哪些指标判断量化方案可以上线？
- 不同模型、硬件和 workload 上的量化结论为什么不能直接迁移？

## 完成证据

- 一次通过的 P0 十分钟防守追问和一次简单数值手算；
- 一张固定版本 vLLM 量化集成与 dispatch 路径图；
- 一份完整参考实验解读，包含主动变量修改与预测复盘；
- 一份 BF16/FP16 与量化方案的固定环境对照；
- 至少一项质量指标和一组 Serving 指标；
- 一个容量下降但没有性能收益或发生 fallback 的案例；
- 一份生产依赖说明，明确哪些能力来自框架、第三方库和 kernel；
- 所有 ToolGap-KV 关联表述保持 `roadmap`、`shipped`、`experimentally validated`、`simulated` 的证据边界。
