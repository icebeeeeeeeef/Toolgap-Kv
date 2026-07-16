# 01｜PyTorch 与张量编程详细知识列表

> 优先级：P0
>
> 当前状态：从零开始
>
> 目标熟练度：原理 L2 / 源码 L1 / 手写 L3 / 实验 L2
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

这不是完整的 PyTorch 课程。完成后应能把 Transformer 数学表达稳定地翻译成 PyTorch，实现时能主动检查 shape、dtype、device、layout 和推理语义，并能写出可信的正确性测试与基础 benchmark。

若 Python 基础稳定，本主题预计需要约 12-18 小时专注练习。时间投入不等于完成；必须通过后文验收。

## P0 详细知识列表

### Tensor 心智模型

- tensor 的 `shape`、`ndim`、`dtype`、`device`；
- storage、stride、offset 与逻辑视图之间的关系；
- view 与 copy 的区别；
- 连续与非连续 tensor；
- CPU/GPU tensor 的设备一致性；
- FP32、FP16、BF16 的最小数值直觉。

### 形状与数据变换

- 索引、切片和维度选择；
- broadcasting 规则；
- `view`、`reshape`、`flatten`、`unsqueeze`、`squeeze`；
- `transpose`、`permute`、`contiguous`；
- `cat`、`stack`、`split`、`chunk`；
- `expand` 与 `repeat` 的语义和内存差异。

### Transformer 所需算子

- `matmul`、`bmm`、`einsum` 的批量矩阵乘语义；
- element-wise 运算和 reduction；
- `softmax` 的维度选择与数值稳定直觉；
- `triu`、布尔 mask、`masked_fill`；
- `argmax`、`topk` 与最小采样操作；
- 随机数种子和可复现性。

### 模型组件

- `nn.Module` 与 `forward`；
- `Parameter`、buffer、普通 tensor 的区别；
- `Linear`、`Embedding`、`LayerNorm/RMSNorm`；
- `ModuleList` 和模块注册；
- `state_dict` 的保存与加载；
- `train()`、`eval()`、`no_grad()`、`inference_mode()` 的职责边界。

### 推理与测量

- tensor 在 CPU 与 CUDA 之间移动；
- CUDA 操作的异步执行直觉；
- benchmark 的 warmup、同步、重复和统计；
- `torch.cuda.memory_allocated()` 与 `memory_reserved()` 的基本区别；
- shape assertion、`torch.testing.assert_close` 和异常输入测试。

## P1 补充

- Autograd 计算图、leaf tensor、`requires_grad` 和最小 backward；
- Linear/MLP 的手工梯度对照；
- autocast 与混合精度推理；
- caching allocator 的 block 缓存、split/coalesce、碎片与 `empty_cache()` 边界；
- `torch.utils.benchmark` 与 PyTorch Profiler；
- PyTorch SDPA 的参考接口、后端选择和 fallback 直觉。

## P2 延后

- `torch.compile`、Dynamo、AOTAutograd、Inductor、graph break；
- DDP、FSDP 与完整训练工程；
- Dataset/DataLoader 性能调优；
- 自定义 C++/CUDA operator 与 dispatcher；
- 完整 Autograd 内部实现。

## 训练顺序与验收

### A. Tensor 与形状语言

必须完成：

1. 在 `[B, S, H]` 和 `[B, N, S, D]` 之间拆头、换轴和合头；
2. 写出 `Q @ K.transpose(-2, -1)` 每一步的 shape；
3. 构造能广播到 Attention Scores 的 Causal Mask；
4. 用 `matmul`、`bmm`、`einsum` 表达等价的批量矩阵乘；
5. 制造非连续 tensor，观察 `view` 失败并解释 `reshape/contiguous` 的行为。

通过标准：给出任意 `B/S/H/N/D`，能先推导形状，再写代码；不能依赖反复运行报错来猜维度。

### B. Module 与推理组件

必须完成：

1. 手写并测试 `RMSNorm`；
2. 建立包含 `Embedding`、`Linear` 和 `ModuleList` 的最小模型；
3. 注册一个 buffer 并解释它为何不是 parameter；
4. 保存、加载 `state_dict` 并验证输出一致；
5. 在 CPU 和可用 GPU 上保持 parameter、input、cache 的 device/dtype 一致。

通过标准：能够从空文件组织一个可测试的 `nn.Module`，并解释 `eval()` 与禁用 Autograd 不是同一件事。

### C. 正确性与性能工具

必须完成：

1. 为 shape、dtype、device 和输出数值编写 assertions；
2. 使用 `torch.testing.assert_close` 对照两个实现；
3. 展示一次错误的 CUDA 朴素计时和修正后的计时；
4. 记录 warmup、同步、重复次数和输入形状；
5. 记录一次 allocated/reserved 的变化并给出谨慎解释。

通过标准：不会根据单次 `time.time()` 或单个显存数字下性能结论。

## 面试手写出口

PyTorch 本身不单独以“背 API”验收，而以能否支持下列实现验收：

- 10 分钟手写 RMSNorm；
- 15 分钟完成带 mask 的 Scaled Dot-Product Attention；
- 30 分钟完成 MHA；
- 45 分钟完成 Pre-Norm Decoder Block；
- 60 分钟完成简化 KV Cache Decode。

这些题目的模型语义和完整要求记录在 [Transformer 推理原理与手撕](02-transformer-inference-and-handwriting.md)。

## 原理追问

- tensor、storage、stride 和 view 分别是什么？
- `view` 与 `reshape` 什么时候会复制？
- 为什么 `transpose` 后经常需要 `contiguous`？它的代价是什么？
- broadcasting 会不会真实复制数据？
- `matmul` 与 `bmm` 的 batch 语义有何不同？
- parameter、buffer、普通属性如何影响设备迁移和 `state_dict`？
- `eval()`、`no_grad()`、`inference_mode()` 分别改变什么？
- CUDA 异步执行为什么会使朴素计时失真？
- allocated、reserved 和进程可见显存为什么可能不同？

## 完成证据

- 一组独立 PyTorch tensor/module 练习及本地测试；
- shape、dtype、device、view/copy 的错误案例记录；
- RMSNorm 实现与参考结果对照；
- CPU 和可用 GPU benchmark；
- 一次 15 分钟 tensor/Module 口头追问复盘；
- Transformer 领域手撕中没有因 PyTorch API 或 tensor shape 失败。

## 当前官方参考

- [PyTorch Learn the Basics](https://docs.pytorch.org/tutorials/beginner/basics/intro)
- [PyTorch Tensor tutorial](https://docs.pytorch.org/tutorials/beginner/basics/tensor_tutorial)
- [PyTorch MultiheadAttention](https://docs.pytorch.org/docs/stable/generated/torch.nn.MultiheadAttention.html)
- [PyTorch scaled dot-product attention](https://docs.pytorch.org/docs/stable/generated/torch.nn.functional.scaled_dot_product_attention.html)
- [PyTorch CUDA semantics](https://docs.pytorch.org/docs/stable/notes/cuda.html)
- [PyTorch benchmark recipe](https://docs.pytorch.org/tutorials/recipes/recipes/benchmark.html)
