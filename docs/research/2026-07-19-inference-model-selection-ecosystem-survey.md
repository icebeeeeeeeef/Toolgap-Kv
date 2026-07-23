# 推理/KV 优化场景的模型选择生态调查

> 研究日期：2026-07-19
> 仓库证据状态：`roadmap`。本文是上游一手资料调查；不包含本仓库的集成、GPU 实验或性能结论。
> 问题：为 ToolGap-KV 的 A0.1 token round-trip 选择一个模型，使实验既能覆盖真实工具调用，又不把“单模型可行”误写成“普适性能”。

## 结论

**A0.1 应冻结 `Qwen/Qwen2.5-7B-Instruct`；`meta-llama/Llama-3.1-8B-Instruct` 应作为后续、独立的跨模型复现锚点，而不是 A0.1 的第二个变量。**

这不是因为 Qwen2.5-7B 是“最通用的 KV benchmark 模型”，而是因为 A0.1 的待证命题是严格的真实工具调用往返：原生模型输出经 vLLM parser 成为 assistant tool-call message，加入 tool result 后按 canonical history 重渲染，R0 是否仍是 R1 的 token 前缀。固定 vLLM 的官方文档明确：Qwen2.5 的 `tokenizer_config.json` 已含 Hermes 风格 tool use，vLLM 可直接使用 `hermes` parser；因此它以较少额外模板变量覆盖了 A0.1 的关键风险。([vLLM Tool Calling](https://docs.vllm.ai/en/v0.25.1/features/tool_calling/))

Llama-3.1-8B 是更强的**生态代表性锚点**：SGLang 的 serving、shared-prefix、trace/Mooncake 与 PD 例子均以它示范，LMCache 的 Llama recipe 也以它示范。([SGLang serving benchmark guide](https://github.com/sgl-project/sglang/blob/main/docs/developer_guide/bench_serving.md), [LMCache Llama recipe](https://docs.lmcache.ai/recipes/llama.html)) 但 vLLM 对 Llama 3.1 tool calling 推荐 `llama3_json` 加一个为 vLLM 调整过的 template；把它放进 A0.1 会同时检验本项目的 token contract 和第三方 template 适配，降低失败归因性。([vLLM Tool Calling](https://docs.vllm.ai/en/v0.25.1/features/tool_calling/))

## 一手证据汇总

| 模型 | 在 serving/KV 优化官方材料中的使用证据 | 原生工具调用路径 | 单卡 Gate A 可行性 | 对 ToolGap-KV 的角色 |
| --- | --- | --- | --- | --- |
| `Qwen/Qwen2.5-7B-Instruct` | Qwen 官方 quickstart 给出 vLLM 部署命令；SGLang 官方 tool-parser 文档给出该模型的 `qwen25` 启动示例。([Qwen quickstart](https://qwen.readthedocs.io/en/v2.5/getting_started/quickstart.html), [SGLang Tool Parser](https://sgl-project.github.io/advanced_features/tool_parser.html)) | vLLM 官方明确 Qwen2.5 的 Hub `tokenizer_config.json` 已包含 Hermes-style tool use，指定 `--tool-call-parser hermes`。([vLLM Tool Calling](https://docs.vllm.ai/en/v0.25.1/features/tool_calling/)) | 7B dense instruct；适合作为单 GPU、单工具、非流式 token-contract 探针。实际显存余量仍须由冻结的 dtype、`max_model_len`、GPU 型号测得，本文不预断。 | **A0.1 唯一主模型**：最少额外模板适配，直接测 parser + canonical history。 |
| `meta-llama/Llama-3.1-8B-Instruct` | SGLang 的在线 serving、generated shared-prefix、Mooncake trace、PD fake-prefill 示例均使用该模型；LMCache 的 vLLM recipe 亦使用它。([SGLang guide](https://github.com/sgl-project/sglang/blob/main/docs/developer_guide/bench_serving.md), [LMCache recipe](https://docs.lmcache.ai/recipes/llama.html)) | vLLM 支持 Llama 3.1 JSON tool calling，但推荐 `--tool-call-parser llama3_json --chat-template` 指向其为 vLLM 调整的模板。([vLLM Tool Calling](https://docs.vllm.ai/en/v0.25.1/features/tool_calling/)) | 官方模型卡为 8B、128K context、GQA；Hub 访问受许可门槛约束。([model card](https://huggingface.co/meta-llama/Llama-3.1-8B-Instruct)) | **后续 cross-model conformance 锚点**：证明 Qwen 专属 serializer/template 假设没有偷偷进入 runtime；不进入 A0.1。 |
| `mistralai/Mistral-7B-Instruct-v0.3` | vLLM 官方列为已确认的 Mistral tool model。([vLLM Tool Calling](https://docs.vllm.ai/en/v0.25.1/features/tool_calling/)) | 官方文档同时记录并行 tool-call 质量问题，以及 HF tokenizer template 的 9 位 tool-call ID 限制，需要额外 template/模式选择。([vLLM Tool Calling](https://docs.vllm.ai/en/v0.25.1/features/tool_calling/)) | 7B 量级，但 template/ID 兼容性本身是额外变量。 | **不选作 A0.1**：不是不支持，而是会污染“token round-trip 是否由 ToolGap-KV 造成”的归因。 |
| DeepSeek-V3、Qwen3-Coder、Kimi-K2 等大模型/MoE | vLLM 支持多个相应 parser；其官方文档为它们列出专用 parser/template。([vLLM Tool Calling](https://docs.vllm.ai/en/v0.25.1/features/tool_calling/)) | 有各自格式与 parser。 | 不应把多 GPU、MoE、reasoning 或专用 template 变量引入 A0.1。 | **排除**：适合未来 scalability/compatibility 研究，不是最小可归因 vertical slice。 |

## 为什么“广泛采用”不足以推出 A0.1 选 Llama

两类证据回答的是不同问题：

1. SGLang/LMCache 对 Llama-3.1-8B 的反复示例，说明它是可比较的 serving/KV benchmark 锚点；并不说明它的工具调用序列化最适合拿来隔离 A0.1 的 token prefix 命题。
2. Qwen2.5-7B 的 vLLM 原生 template + Hermes parser 路径，说明它适合减少 A0.1 的接缝变量；并不证明任何 offload/recompute 策略可跨模型、跨 tokenizer、跨架构泛化。
3. 任何单模型、单 GPU、串行工具 gap 只能给出 **该模型 + 该 revision + 该 tokenizer/template/parser + 该 vLLM commit** 的 conformance 结论。它不能给出全局吞吐、HBM 竞争、CPU offload break-even 或“通用 agent runtime”结论。

因此“代表性”的最小可维护定义应是：**A0.1 先用一个低接缝、真实工具调用的 7B dense 模型证伪 token contract；只有该 contract 成立，才将同一 fixture 迁移至一个不同家族的 8B ecosystem anchor 做独立复现。** 这比同时跑两个模型更有信息量：前者先将失败定位到 protocol/template，后者才检验实现是否偷依赖 Qwen 专属格式。

## A0.1 冻结建议

建议在实验规格中写成以下不可省略的 pin（本文不执行下载或解析）：

```text
model_id: Qwen/Qwen2.5-7B-Instruct
weights_revision: <首跑前解析并冻结为 Hugging Face commit SHA>
tokenizer_revision: <同一 SHA>
chat_template: tokenizer_config.json 中该 SHA 的内置 template 原文 + SHA-256
tool_parser: hermes
tool_mode: 单工具、非流式、temperature=0
```

R0/R1 的输入必须来自同一官方/Hub template 的真实渲染：R0 包含系统消息、工具 schema、用户消息和模型实际产生的 assistant tool call；R1 在同一历史后追加带匹配 `tool_call_id` 的 `role: tool` result。不得以手写 JSON prompt 或自行拼接 assistant/tool 文本替代。

## 后续验证边界

- 若 A0.1 通过，才创建一个**新规格票**讨论 Llama-3.1-8B cross-model conformance；它不是当前 gate 的 pass 条件。
- 若 A0.1 失败，先保存 rendered prompt、token IDs、template hash、parser 输出和最早偏离 token；不得先换模型“刷过”。
- 本文没有比较模型质量、选择最佳 agent 模型，亦没有报告任何性能数字。它只为最小实验的变量控制提供依据。

## 来源与方法

仅使用模型/引擎所有者的文档、源码仓库或 Hugging Face 原始模型卡：vLLM 官方工具调用文档与 v0.25.1 支持矩阵、SGLang 官方 benchmark/tool-parser 文档、LMCache 官方 recipe、Qwen 官方文档与模型卡、Meta 原始 Hugging Face 模型卡。搜索命中但不属于这些一手来源的论文、博客和 issue 未用于上述结论。
