# 面向 LLM Serving 的 PyTorch 最小上手路线

> 日期：2026-07-16
> 状态：学习路线研究，不代表 Topic 01 已完成
> 目标：用最少的 PyTorch 学习投入，获得实现和验证 Transformer 推理所需的张量编程能力
> 来源边界：PyTorch 官方文档与教程、当前仓库的 AI Infra 知识地图；不使用二手速成教程作为结论依据

## 结论

不建议顺序刷完整的 PyTorch 入门教程，也不建议只听讲解。

推荐采用：

> **Agent 引导的短讲解 + 用户从空文件实现 + `pytest` 自动反馈 + 官方文档查证 + Notion 记录错误与复习。**

原因不是“官方教程不好”，而是官方 `Learn the Basics` 面向完整机器学习工作流，依次覆盖
Tensors、Datasets/DataLoaders、Transforms、Build Model、Autograd、Optimization 和
Save/Load。当前目标不是训练 FashionMNIST，而是把 Transformer 推理表达为可靠的
PyTorch 代码，因此 Dataset、Transforms 和完整训练循环不是第一阶段依赖。

当前仓库已经把 Topic 01 的出口定义为：能够处理 shape、dtype、device、layout、模型
组件、推理模式、正确性测试和基础 benchmark，并最终支撑 Attention、Decoder Block 与
KV Cache Decode 手写。学习路线应直接围绕这个出口组织，而不是围绕 PyTorch API 目录组织。

## 当前环境事实

2026-07-16 在当前工作区只读检查得到：

```text
machine: arm64 macOS 15.7.4
default python3: 3.8.10
torch: not installed in default Python
uv: available at /Users/bytedance/.local/bin/uv
repository Python requirement: >=3.10
```

PyTorch 当前官方安装页要求 latest stable 使用 Python 3.10 或更高，并推荐 macOS 使用
Python 3.10-3.14。默认 Python 3.8 因此不能直接作为本路线环境。

建议后续单独执行环境初始化，不污染系统 Python：

```bash
uv venv --python 3.12 learning/.venv
source learning/.venv/bin/activate
uv pip install torch pytest
python -c 'import torch; print(torch.__version__); print(torch.backends.mps.is_available())'
```

版本和实际安装命令应在执行当天再次以 PyTorch 官方安装选择器为准。第一至第四阶段都可
以 CPU 完成；Apple MPS 只在设备迁移和测量阶段加入，不能代替后续 CUDA 环境中的真实性能
实验。

## 应该读什么，应该跳过什么

### 第一阶段必读

1. 官方 `Tensors` 入门：tensor 创建、属性、索引、拼接、设备和 NumPy bridge；
2. Tensor Views：共享底层数据、view/copy、连续性和隐式 copy 风险；
3. Broadcasting semantics：从尾维比较以及无数据复制的自动扩展语义；
4. `torch.matmul`：最后两维执行矩阵乘，前置 batch 维参与 broadcasting；
5. `nn.Module`：子模块注册、parameter/buffer、`to()`、`state_dict()` 和 `eval()`；
6. `inference_mode`：禁用 Autograd 相关开销，但不会自动调用 `model.eval()`；
7. `torch.testing.assert_close`：对数值、dtype、device 和 layout 建立可执行断言；
8. PyTorch Benchmark 与 CUDA semantics：warmup、同步、线程数和 caching allocator。

### 暂时跳过

- Dataset、DataLoader 和 transforms；
- 完整 Autograd、loss、optimizer 和训练循环；
- DDP/FSDP；
- `torch.compile`、Inductor 和 graph break；
- 自定义 C++/CUDA/Triton operator；
- 从零实现高性能 Attention kernel。

Autograd 只需在完成推理主线后补一个 30-45 分钟最小练习，理解 `requires_grad`、leaf
tensor 和 backward 即可；它不是当前上手阻塞点。

## 12-18 小时最小路线

时间是预算，不是完成证明。每一步都以可运行代码、测试和闭卷复述为出口。

### 第 0 步：环境和反馈闭环（30-60 分钟）

目标：建立独立 Python 环境，让一个测试能够稳定运行。

产物：

```text
learning/pytorch/
  pyproject.toml or requirements record
  exercises/
  tests/
```

退出条件：

- 固定 Python 与 torch 版本；
- CPU 上成功创建 tensor；
- `pytest` 能发现并运行一个测试；
- MPS 是否可用被记录，但不要求可用。

### 第 1 步：Tensor 是带存储语义的形状对象（2-3 小时）

只学：

- `shape`、`ndim`、`dtype`、`device`；
- storage、offset、stride；
- basic indexing、slice；
- view 与 copy；
- contiguous 与 non-contiguous。

核心练习：

```text
[B, S, H] -> [B, S, N, D] -> [B, N, S, D]
```

必须在运行前写出每一步 shape 和 stride 预期，主动制造一次 `transpose` 后 `view`
失败，并解释 `reshape()` 或 `contiguous()` 为什么能够继续。

退出条件：不给解释器试错机会，也能为任意 `B/S/H/N/D` 写出拆头与合头过程。

### 第 2 步：Broadcasting 与批量矩阵乘（2-3 小时）

只学：

- broadcasting 从尾维开始匹配；
- `matmul` 的 batch 维与 matrix 维；
- `bmm` 的严格三维 contract；
- `einsum` 只作为等价表达和验证工具；
- `expand` 与 `repeat` 的内存语义。

核心练习：

```text
q:      [B, N, S, D]
k:      [B, N, T, D]
scores: [B, N, S, T]
mask:   [1, 1, S, T]
```

分别用 `matmul`、`bmm` 和 `einsum` 计算等价 scores，并用
`torch.testing.assert_close` 对照。

退出条件：先推导 batch broadcasting 和矩阵乘维度，再写实现；不靠报错猜 shape。

### 第 3 步：从算子拼出 naive Attention（2-3 小时）

只学：

- scale；
- causal mask；
- `masked_fill`；
- `softmax(dim=-1)`；
- `scores @ value`；
- dtype 对容差和数值的影响。

核心练习：从空文件实现单头和多头 scaled dot-product attention，与官方
`torch.nn.functional.scaled_dot_product_attention` 做小规模输出对照。

需要特别记录：官方 SDPA 的 boolean mask 语义，以及 `dropout_p` 在 evaluation 时不会
因为 `model.eval()` 自动变成零。

退出条件：15 分钟完成 causal SDPA，30 分钟完成带拆头/合头的 MHA，并通过数值测试。

### 第 4 步：最小 `nn.Module` 与推理语义（2-3 小时）

只学：

- `nn.Module`、`forward` 和子模块注册；
- `Parameter`、persistent buffer 和普通属性；
- `Linear`、`Embedding`、`ModuleList`；
- `state_dict` 保存/加载；
- `eval()`、`no_grad()` 和 `inference_mode()` 的不同职责；
- model/input/cache 的 dtype 与 device 一致性。

核心练习：手写 `RMSNorm` 和一个包含 `Embedding + ModuleList + Linear` 的最小模块，
注册 position buffer，保存/加载后验证输出一致。

退出条件：能够解释为什么 `model.eval()` 不会关闭梯度，以及为什么
`inference_mode()` 不会自动改变 Dropout/BatchNorm 行为。

### 第 5 步：测试和可信测量（2-3 小时）

只学：

- shape/dtype/device assertions；
- `torch.testing.assert_close` 的 tolerance；
- seed 和可复现性边界；
- CPU benchmark；
- MPS/CUDA 的异步直觉、warmup 和同步；
- allocated 与 reserved 的区别。

PyTorch 官方 benchmark 教程给出的直接负例是：未同步的普通计时可能只量到 CUDA kernel
launch；首次 cuBLAS 调用还会受初始化影响。`torch.utils.benchmark` 会处理 warmup 和
同步等常见陷阱，但 workload、线程数、输入 shape 和环境仍必须记录。

退出条件：能够展示一个错误测量和修正后的测量，并且不从单次时间或单个显存数字得出
性能结论。

### 第 6 步：综合出口（2-3 小时）

完成一个 `attention_shape_playground`：

- 接收 `B/S/H/N/D`；
- 生成 Q/K/V；
- 拆头、计算 causal attention、合头；
- 每一步具有 shape/dtype/device assertions；
- naive 结果与官方 SDPA 对照；
- CPU 测试必过，可用时增加 MPS 运行；
- 保存一次错误案例和修正；
- 闭卷完成一次 15 分钟追问。

这个产物只证明 Topic 01 的张量工具能力，不证明已经实现 vLLM Attention、PagedAttention
或 ToolGap-KV runtime。

## 为什么推荐由 Agent 带着学

推荐“Agent 教学”，但教学不等于由 Agent 替用户写代码。

### Agent 负责

- 每次只解释一个最小因果链；
- 根据当前回答选择直觉、原理或工程层深度；
- 在用户运行代码前要求先写 shape 预测；
- 给练习接口、失败用例和测试标准；
- 审查代码中的隐式 copy、broadcast、dtype/device 和测量错误；
- 用连续追问检验是否能脱离代码复述；
- 把稳定结论、薄弱点和复习计划回写 Notion。

### 用户负责

- 从空文件实现核心练习；
- 先预测，再运行；
- 解释失败原因，而不只修到测试变绿；
- 保留一个错误案例；
- 在复习时闭卷重写关键路径。

### 官方文档负责

- 作为 API 和语义的一手事实源；
- 当 Agent 解释与实际版本不一致时，以 pinned 官方文档和运行结果为准；
- 提供进一步阅读，但不决定学习顺序。

这种分工比纯自学更适合当前目标：它压缩无关训练内容，同时保留独立实现和查证能力；也
比纯讲课更可靠，因为每个结论都必须通过代码和测试。

## 第一课建议

第一课不要直接讲 Attention。固定为：

> **Tensor 的 shape、storage、stride、view/copy 与拆头操作。**

建议流程：

1. 3 句话建立 tensor 心智模型；
2. 用户先预测五次 shape 变换；
3. 从空文件实现拆头和合头；
4. 制造 non-contiguous `view` 失败；
5. 写 4 个测试；
6. 用户用自己的话解释 `reshape` 与 `contiguous`；
7. 把错误类型、Git commit 和下一次复习日期写入 Notion。

第一课结束时仍不会完整 Attention 是正常的。它只关闭一个阻塞点：不再靠运行报错猜
Transformer tensor shape。

## Notion 最小记录字段

每次学习只回写这些内容，代码留在 `learning/`：

```text
主题
训练维度：原理 / 源码 / 手写 / 实验
本节目标
开始前理解
完成结果
错误表现与错误类型
正确模型
GitHub commit / 文件 / 测试命令
当前四维等级
下次复习时间与复习题
```

不要把整份代码复制进 Notion；链接到 exact commit，Notion 只保存个人理解、薄弱点和复习
状态。

## 一手资料

- [PyTorch Get Started](https://pytorch.org/get-started/locally/)
- [Learn the Basics](https://docs.pytorch.org/tutorials/beginner/basics/intro)
- [Tensors](https://docs.pytorch.org/tutorials/beginner/basics/tensor_tutorial.html)
- [Tensor Views](https://docs.pytorch.org/docs/stable/tensor_view.html)
- [Broadcasting semantics](https://docs.pytorch.org/docs/stable/notes/broadcasting.html)
- [`torch.matmul`](https://docs.pytorch.org/docs/stable/generated/torch.matmul.html)
- [`torch.nn.Module`](https://docs.pytorch.org/docs/stable/generated/torch.nn.Module.html)
- [`torch.inference_mode`](https://docs.pytorch.org/docs/stable/generated/torch.autograd.grad_mode.inference_mode.html)
- [`torch.testing.assert_close`](https://docs.pytorch.org/docs/stable/testing.html#torch.testing.assert_close)
- [Scaled dot-product attention](https://docs.pytorch.org/docs/stable/generated/torch.nn.functional.scaled_dot_product_attention.html)
- [PyTorch Benchmark](https://docs.pytorch.org/tutorials/recipes/recipes/benchmark.html)
- [CUDA semantics](https://docs.pytorch.org/docs/stable/notes/cuda.html)
- [MPS backend](https://docs.pytorch.org/docs/stable/notes/mps.html)

## 最终决策

采用 Agent 引导教学，从第一课开始，不先自行刷完整教程。官方文档作为每节课的一手参考，
代码和测试存入 `learning/`，学习状态和复习记录存入 Notion。

环境准备是当前唯一前置阻塞：创建 Python 3.10+ 的隔离环境并安装 `torch`、`pytest`。
完成环境验证后，直接进入 shape/storage/stride，不增加额外前置课程。
