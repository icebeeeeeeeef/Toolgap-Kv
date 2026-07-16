# 02｜Transformer 推理原理与手撕详细知识列表

> 优先级：P0
>
> 当前状态：原理具有旧笔记基础；张量级推导、源码、手写和实验待开始
>
> 目标熟练度：原理 L3 / 源码 L2 / 手写 L3 / 实验 L3
>
> 依赖：[PyTorch 与张量编程](01-pytorch-tensor-programming.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能从 token 输入开始，沿 decoder-only Transformer 的每个张量和模块讲到 logits、采样与下一个 token；能够独立实现 Attention、Decoder Block 和 KV Cache Decode，并将实现连接到 Prefill/Decode、显存、带宽、PagedAttention 与 vLLM runtime。

在 PyTorch 基础达标后，本主题预计需要约 25-35 小时专注练习。限时手写、输出一致性或连续追问未通过时，不视为完成。

## 当前基础与缺口

已有笔记证明以下主线曾经建立：

- Transformer 根据上下文预测下一个 token；
- Self-Attention 是内容相关的信息聚合；
- Causal Mask 约束自回归生成；
- Decode 反复使用历史 K/V，因此 KV Cache 用空间换计算；
- Block Manager、Block Table、PagedAttention 的基本职责边界。

当前缺口：

- Q/K/V、Attention Scores、Context 的张量形状；
- RoPE、Residual、Norm、MLP 的准确执行顺序；
- Prefill/Decode 的计算形态和资源画像；
- MHA/MQA/GQA 的实现与 KV 容量差异；
- 可运行实现、源码路径和可复现实验。

旧笔记只作为起点，不作为当前已经掌握的证据。

## P0 详细知识列表

### Decoder-only 主链路

- Tokenizer、token IDs、Embedding 与 hidden states；
- Pre-Norm Decoder Layer；
- Attention、Residual、RMSNorm、SwiGLU MLP；
- Final Norm、LM Head、logits；
- greedy、temperature、top-k 的最小采样链路；
- 自回归停止条件。

### Tokenization、采样与输出处理防守子集

> 子集目标：原理 L2 / 源码 L1 / 手写 L0 / 实验 L0
>
> 建议投入：2-4 小时。该子集不改变本主题整体的四维目标，也不增加独立手写或实验门槛。

需要能够从一次请求的输入边界讲到流式输出：

```text
text / messages
  -> chat template 与特殊 token
  -> tokenizer / input_ids
  -> model logits
  -> logits processor / penalty
  -> temperature 与 top-k / top-p
  -> token selection
  -> EOS / stop token / stop string / max tokens
  -> incremental detokenize
  -> streaming response
```

原理要求：

- Tokenizer、词表、合并规则、token ID、特殊 token 和 OOV/byte fallback 的基本职责；
- chat template 会决定实际 prompt token 序列，模型 revision、tokenizer、template 和特殊 token 不一致可能改变输出或破坏 cache 兼容性；
- greedy 直接选择最大 logit/probability token；temperature 通过缩放 logits 改变分布尖锐程度；
- top-k 保留固定数量候选，top-p 保留累计概率达到阈值的最小候选集合；
- 能解释 penalty/logits processor、temperature、候选截断、归一化和采样的概念顺序，并说明固定框架版本的真实顺序必须以源码为准；
- 区分 EOS、stop token、stop string、最大生成长度和外部 abort/cancellation；stop string 可能跨 token 边界，增量 detokenize 还要处理不完整字符与输出缓冲；
- streaming 是逐步公开已完成输出，不代表模型一次前向产生了完整答案；调度、采样、detokenize 和网络发送可以位于不同执行阶段。

源码只要求选择一个固定版本 vLLM，记录以下高层链路的入口、关键对象和职责，不要求精读采样 kernel：

```text
request / SamplingParams
  -> tokenizer 与 prompt preprocessing
  -> model logits
  -> logits processing / sampler
  -> request output state
  -> detokenize / streaming response
```

结构化或约束解码只作为 P2 防守知识：知道 grammar、正则或 JSON schema 可以编译为 FSM/等价状态，根据当前状态屏蔽非法候选 token；能够说明状态推进、合法 token mask 构造、CPU 开销、同步和 batch 异质性可能影响吞吐。不要求阅读或实现 grammar compiler、FSM engine 或完整 structured output runtime。

明确不要求：

- 从空文件手写 top-k/top-p sampler、logits processor 或输出状态机；
- 手写 CUDA/Triton Top-K、softmax 或采样 kernel；
- 独立完成采样质量、吞吐或 structured output 性能实验；
- 把按权重随机采样的 LeetCode 题当作 Serving sampler 的领域手撕验收。

通过标准：完成一次 5-10 分钟脱稿口述，能够解释采样参数如何改变候选分布，画出 tokenizer 到 streaming response 的完整链路，并指出固定版本 vLLM 的主要源码入口。无需提交独立实现或实验结果。

### Attention

- Q/K/V 投影的数学语义与张量形状；
- Scaled Dot-Product Attention；
- `1 / sqrt(D)` 缩放；
- Causal Mask 与 padding/length mask 的边界；
- 多头拆分、独立计算、拼接与输出投影；
- MHA、MQA、GQA 的 head 映射；
- RoPE 作用于 Q/K 的位置与 position offset；
- Attention 计算复杂度、激活和访存直觉。

### Decoder Layer 组件

- Residual 的信息与梯度路径；
- Pre-Norm 与 Post-Norm；
- LayerNorm 与 RMSNorm 的计算和取舍；
- FFN/MLP 的位置维度独立计算；
- SwiGLU 的 gate/up/down 投影；
- 多层堆叠时的 shape 与参数共享边界。

### Prefill、Decode 与 KV Cache

- Prefill 和 Decode 的输入形态；
- 每层 K/V 的产生、布局、追加与读取；
- 为什么缓存 K/V，不缓存历史 Q；
- 无缓存 Decode 的重复计算；
- MHA/MQA/GQA 对单层 K/V 形状的影响；
- 简化连续 tensor cache 的正确性；
- 为什么 Prefill 更容易计算密集、Decode 更容易受带宽和容量制约。

容量手算、block/page 管理、Prefix Cache、offload、驱逐和生命周期正确性统一归入 [KV Cache 与内存系统](03-kv-cache-memory-system.md)。

### 正确性与性能

- 手写实现与参考实现的数值对照；
- 带缓存与无缓存 logits/token 一致；
- position offset、mask、dtype 对一致性的影响；
- naive Attention 与融合 SDPA 的职责边界；
- warmup、同步、输入形状、重复和显存统计；
- 数学等价不代表浮点逐位一致。

## P1 补充

- Linear/MLP 的简化 backward；
- 一个 Transformer Layer 的 Column/Row Parallel 切分；
- AllReduce/ReduceScatter/AllGather 出现的位置；
- FP16/BF16/FP32 的数值与吞吐 trade-off；
- FlashAttention 的 IO-aware 原理与 online softmax；
- 阅读一个固定版本 Hugging Face Llama-family Decoder Layer；
- 阅读固定版本 vLLM model executor、Attention layer 与 KV Cache 接口。

### MLA Serving 防守子集

> 子集目标：原理 L2 / 源码 L1 / 手写 L0 / 实验 L0
>
> 建议投入：与 Topic 03 的 MLA 缓存子集共享 3-5 小时。该子集不改变本主题整体的四维目标。

需要能够从张量形状解释 MLA，而不是只背“压缩 KV Cache”：

- 对比 MHA/GQA 直接缓存 K/V 与 MLA 缓存低维 latent representation 的差异；
- 解释 query 与 KV 的低秩投影、up-projection，以及为什么部分 RoPE 维度需要与可吸收部分解耦；
- 从矩阵乘法结合律解释矩阵吸收：把可合并的投影权重预先组合，避免 Decode 时为历史 token 显式恢复完整 K/V；
- 区分 Prefill 与 Decode：Prefill 仍要处理整段 token 的并行计算，Decode 更受每步读取历史缓存的表示与带宽影响；
- 能说明缓存容量下降不自动等于端到端更快，实际收益还受到额外投影、kernel 支持、layout、batch 和硬件约束影响；
- 能比较普通 MHA/GQA 与 MLA 的 `cached state -> attention output` 数据路径，但不要求推导特定模型的全部超参数。

源码只要求固定一个模型 revision 或推理框架版本，定位以下主链路的入口和关键张量：

```text
hidden states
  -> query / latent KV projection
  -> decoupled RoPE path
  -> latent KV cache write/read
  -> absorbed Decode computation
  -> attention output projection
```

通过标准：能够完成一次 10-15 分钟脱稿讲解，画出 MHA/GQA 与 MLA 的缓存表示及 Decode 路径差异，并沿固定版本源码指出主要入口。不要求提交独立代码或实验结果。

明确不要求：

- 从空文件手写 MLA 或复现 DeepSeek 完整 Attention；
- 阅读、实现或调优 FlashMLA/CUDA/Triton kernel；
- 完成 MLA 性能 benchmark 或 DeepSeek 全架构源码巡游；
- 把 MLA 描述为 ToolGap-KV 已支持的模型能力。

## P2 延后

- 完整训练体系和优化器；
- Encoder-only 与 Encoder-Decoder 的实现细节；
- MoE、MLA 等模型变体的完整手写与 kernel 复现；
- 从零手写 FlashAttention/PagedAttention CUDA 或 Triton kernel；
- 编译器 lowering、kernel fusion 与调度器内部实现。

## 训练顺序与验收

### A. 张量契约

必须能够脱稿写出：

```text
x:       [B, S, H]
q:       [B, Nq, S, D]
k/v:     [B, Nkv, T, D]
scores:  [B, Nq, S, T]
context: [B, Nq, S, D]
output:  [B, S, H]
logits:  [B, S, V]
```

通过标准：能够分别代入 Prefill 与单 token Decode，并解释 `S`、`T`、`Nq`、`Nkv` 的变化。

### B. Attention 手撕

必须完成：

1. 单头 Scaled Dot-Product Attention；
2. 带 Causal Mask 的 MHA；
3. RoPE；
4. MQA 与 GQA；
5. 与 PyTorch SDPA 或固定参考实现做数值对照。

通过标准：30 分钟内从空文件完成 MHA forward；能解释缩放、mask、softmax 维度、拆头/合头、layout 和 GQA 映射。

### C. Decoder Block 与生成

必须完成：

1. RMSNorm；
2. SwiGLU MLP；
3. Pre-Norm Decoder Block；
4. Token Embedding、LM Head 和最小采样；
5. 无 KV Cache 的自回归生成。

通过标准：45 分钟内完成简化 Decoder Block；90 分钟内拼出可运行的小型 decoder-only 生成链路。

### D. KV Cache Decode

必须完成：

1. 将完整前向拆成 Prefill 与 Decode；
2. 为每层保存 K/V；
3. Decode 只投影新 token，并读取历史 K/V；
4. 实现 append 与预分配两种 cache；
5. 验证缓存前后 logits 与生成 token 一致；
6. 用公式和实际统计核对 KV Cache 容量。

通过标准：60 分钟内完成给定接口的简化 KV Cache Decode；能够追踪一个新 token 穿过所有层时 K/V 如何产生、存放和读取。

### E. 源码与实验

必须完成：

1. 对比 naive Attention 与 PyTorch SDPA；
2. 比较不同 `B/S/H/Nq/Nkv` 的时延和显存；
3. 阅读一个固定版本真实模型前向；
4. 阅读固定版本 vLLM Attention/KV 接口；
5. 记录数学实现、融合算子和 runtime 的职责边界；
6. 完成一次限时手撕和一次 20 分钟连续追问。

通过标准：所有源码结论记录版本和路径；所有性能结论记录环境、输入、命令、重复与已知限制。

## 必须通过的领域手撕

| 题目 | 时间限制 | 最低要求 |
|---|---:|---|
| RMSNorm | 10 分钟 | 最后一维、epsilon、dtype 正确 |
| Causal Scaled Dot-Product Attention | 15 分钟 | shape、缩放、mask、softmax 正确 |
| Multi-Head Attention | 30 分钟 | QKV、拆头、Attention、合头、输出投影 |
| RoPE | 20 分钟 | 正确旋转维度并处理 position offset |
| GQA | 30 分钟 | query heads 与 KV heads 映射正确 |
| SwiGLU MLP | 15 分钟 | gate/up/down 和激活正确 |
| Pre-Norm Decoder Block | 45 分钟 | norm、残差、Attention、MLP 顺序正确 |
| KV Cache Decode | 60 分钟 | Prefill/Decode、cache 更新、输出一致 |
| 简化 TP Transformer Layer | 60 分钟 | 切分方式和 collective 位置正确；P1 |

## 原理连续追问

### Attention 与形状

- 为什么 Attention 除以 `sqrt(D)`？不除会怎样？
- Causal Mask 在 Prefill 和单 token Decode 中分别是什么形态？
- 为什么 MHA 需要拆头和输出投影？
- MQA/GQA 如何减少 KV Cache？质量和并行性代价是什么？
- RoPE 为什么作用于 Q/K？position offset 为什么影响增量 Decode？
- MLA 缓存的状态与 MHA/GQA 有何不同？为什么低秩表示可以减少历史缓存读取？
- 什么是矩阵吸收？为什么解耦 RoPE 会影响哪些权重能够被吸收？

### Layer 与模型

- Pre-Norm 和 Post-Norm 的差异是什么？
- RMSNorm 舍弃了什么？为什么现代 LLM 常用它？
- MLP 为什么按 token 独立计算？SwiGLU 的三组投影是什么？
- Residual 解决了什么问题？它不解决什么问题？

### Serving 与性能

- Prefill 为什么更容易计算密集，Decode 为什么更容易受内存带宽限制？
- KV Cache 为什么只缓存 K/V？为什么不缓存 Q？
- naive Attention 与 SDPA/FlashAttention 的数学语义和执行实现如何区分？
- temperature、top-k、top-p 分别怎样改变候选分布，为什么 stop string 不能总被当作单个 token 处理？
- 一次生成如何从 SamplingParams、logits 和 token selection 走到增量 detokenize 与流式返回？
- 如果缓存输出不一致，应按什么顺序排查 mask、position、layout、dtype 和 cache 更新？
- MLA 为什么更直接优化 Decode 数据路径？哪些条件会让显存下降却没有得到端到端加速？

## 与 ToolGap-KV 的连接

- 本主题只负责 K/V 如何由模型产生、如何参与 Attention，以及简化连续 cache 的输出正确性；
- 容量、block、共享、回收、offload/recompute 和故障语义见 [KV Cache 与内存系统](03-kv-cache-memory-system.md)；
- 手写连续 tensor cache 不能被包装成已完成的 vLLM PagedAttention 或 ToolGap-KV 集成证据。

## 完成证据

- 独立 Transformer 实现及本地测试；
- 所有关键路径包含 shape assertions；
- 手写 Attention 与参考实现数值一致；
- KV Cache 前后输出等价；
- CPU 与可用 GPU benchmark；
- 一份固定版本模型和 vLLM 源码路径笔记；
- 一次限时手撕记录；
- 一次连续追问复盘，记录答错和修正；
- ToolGap-KV 相关表述没有越过仓库实际 claim state。

## 现有个人笔记

- [Transformer 主笔记](https://app.notion.com/p/3725d315c09080e695f3d7fa7000b792)
- [Transformer 推理与 KV Cache 阶段学习记录](https://app.notion.com/p/3415d315c09081228447d3c7b927ac16)
- [面向 LLM Serving 的 Transformer 最小必要基础](https://app.notion.com/p/33e5d315c09081cbb56ae208cc775668)
- [Transformer 推理两阶段](https://app.notion.com/p/33c5d315c0908143bfc3ef2cde8e5680)

## 当前官方参考

- [PyTorch MultiheadAttention](https://docs.pytorch.org/docs/stable/generated/torch.nn.MultiheadAttention.html)
- [PyTorch scaled dot-product attention](https://docs.pytorch.org/docs/stable/generated/torch.nn.functional.scaled_dot_product_attention.html)
- [PyTorch CUDA semantics](https://docs.pytorch.org/docs/stable/notes/cuda.html)
- [PyTorch benchmark recipe](https://docs.pytorch.org/tutorials/recipes/recipes/benchmark.html)
