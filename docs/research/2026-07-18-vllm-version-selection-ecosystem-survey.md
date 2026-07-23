# vLLM 二次开发的版本选择：生态实践调查

> 研究日期：2026-07-18
>
> 用途：辅助讨论 ToolGap-KV 的 vLLM 基线版本；不构成 Runtime 集成、
> 兼容性或性能的 `shipped` / `experimentally validated` 结论。

## 要回答的问题

当社区项目对 vLLM 做硬件适配、KV cache 扩展、connector 或其他二次开发时，
它们通常基于“稳定版”还是 `main`？是否存在一个应当一律采用的 vLLM 长期稳定版？

## 结论先行

没有证据表明 vLLM 生态存在一个所有二次开发共用的“长期稳定版”。更准确的
共同实践是：

1. **发布给用户的适配/插件**：选择一个明确的 vLLM release line，精确配对
   依赖版本，并用兼容矩阵和 CI 证明该配对；
2. **跟进上游的开发分支**：可以跟 `main`，但这是持续 CI 的开发承诺，不是
   可复现实验或用户部署的稳定基线；
3. **研究性改造或局部 patch**：必须同时锁定 upstream tag/commit、patch hash
   和环境。换版本就意味着重新做与改动有关的审计和测试。

因此，ToolGap-KV 不应寻找抽象的“社区公认 LTS”，而应选定一个 release tag 作为
**唯一的 Gate A 基线**。对本项目而言，`v0.25.1` /
`752a3a504485790a2e8491cacbb35c137339ad34` 可以承担这个角色，前提是 Gate A
先验证它在目标 GPU/模型/功能组合上可安装、可运行、且接缝可维护。

这里需要修正此前“audit target / execution pin”可能造成的误解：它们不应该是
两次任选版本。

```text
现在：冻结一个 source-audit baseline = tag + exact commit
Gate A 通过：将同一个 commit 提升为 execution pin
Gate A 失败：记录失败；若改用新版本，重新开始受影响的源码审计
```

也就是说，两个词描述的是**同一个 commit 的证据状态变化**，而不是允许在审计后
无代价地换一个版本。

## 一手证据

### 1. 上游 vLLM 自身不承诺跨 minor 版本的接口不变

vLLM 的官方 deprecation policy 将 minor 版本（`Y`）定义为可承载 significant
changes、deprecations 与 removals 的边界；patch 版本（`Z`）才用于修复和较安全的
增强。该政策覆盖 CLI、环境变量、配置文件、OpenAI 兼容 API 和 public Python API。

含义是：`0.x.y` 的同一 minor release line 比跨 minor 更适合作为可复现的改造基线，
但即使是“公共 API”，跨 minor 也不应默认安全；更底层的 scheduler / KVConnector 接缝
更不能靠惯性假设稳定。

来源：[vLLM Deprecation Policy](https://docs.vllm.ai/en/stable/contributing/deprecation_policy/)

### 2. 官方托管的 vLLM Ascend 是最强的生态样本：精确配对，不是假设 LTS

`vllm-ascend` 是 vLLM 社区推荐的硬件 plugin。它的版本策略明确要求 release
版本与 vLLM 版本匹配，并公布 release compatibility matrix：例如
`vllm-ascend v0.22.1rc1` 配对 `vLLM v0.22.1`，同时固定 Python、CANN、
PyTorch/torch_npu、Triton Ascend 与 Mooncake 版本。

它还将分支角色分开：

- `main` 对应 vLLM `main`，并通过持续 CI 跟踪；
- `releases/vX.Y.Z` 对应某一个 vLLM release line；
- `main` 的兼容承诺仅覆盖上游 main 和最新一到两个 release；并非历史版本永久支持。

这说明真正维护大型 vLLM 改造的实践不是“挑一个老稳定版永远不动”，而是为某个
明确 release line 建立配对、CI 和 EOL 边界。

来源：[vLLM Ascend Versioning Policy](https://docs.vllm.ai/projects/ascend/en/v0.23.0/community/versioning_policy.html)，
[vLLM Ascend 项目说明](https://github.com/vllm-project/vllm-ascend)

### 3. LMCache 的实践：兼容下限不等于行为等价

LMCache 的官方 quickstart 对 vLLM 版本分流：

- `vLLM < 0.20.0` 时，`LMCacheMPConnector` 必然解析到 vLLM 内置实现；
- `vLLM >= 0.20.0` 时，仍默认使用内置实现，但可以用
  `kv_connector_module_path` 显式切换为 LMCache 自己发布的 connector；
- 文档建议在 `>= 0.20.0` 时优先使用 LMCache 发布的 connector，因为它跟随最新
  LMCache server protocol，并可能先于 vendored 版本发布修复和功能。

这证明版本区间只能说明“存在某条可用路径”，并不能说明同名 connector 在不同
vLLM 版本上具有完全相同的语义或缺陷面。对 ToolGap-KV 而言，不能以
“vLLM >= 某版本”替代精确 commit + 实测 trace。

来源：[LMCache Quickstart](https://docs.lmcache.ai/getting_started/quickstart.html)

### 4. Mooncake 的实践：上游 main 可用于共同开发，不适合作为独立实验基线

Mooncake 的项目记录表明，其与 vLLM 的 KV connector / P-D disaggregation 集成由
上游共同演进；项目历史中曾明确描述某个 integration “based on vLLM's main branch”，
而当前文档则将 Mooncake Transfer Engine 描述为 vLLM v1 的 KV Connector。

这与 Ascend 的分支策略一致：当项目目标是尽快上游化或共同开发时，`main` 有价值；
但这依赖持续适配、版本感知逻辑与 CI，而不是一次性研究结果。Mooncake 的发布记录
也出现“适配 latest vLLM”“version-based proxy selection”等维护项，进一步说明
这种路径本身就是持续维护成本。

来源：[Mooncake 项目说明](https://github.com/kvcache-ai/Mooncake)，
[Mooncake releases](https://github.com/kvcache-ai/Mooncake/releases)

### 5. Hugging Face 在这里提供的是模型协议，不是 vLLM 改造版本政策

Hugging Face model card 通常会给出模型在某类推理框架上的最低支持版本或启动示例，
这可以帮助选择模型和 chat template；但它不会为 vLLM 内部 scheduler、KV block、
connector 或异步 completion 接缝提供兼容承诺。

因此，Hugging Face 社区资料可以用于 ToolGap-KV 的模型 revision、tokenizer、
template 与 tool-call 消息协议 provenance；不能作为“哪个 vLLM 版本最适合二次
改造”的权威答案。该问题应优先由 vLLM release policy、待使用扩展的兼容矩阵和
对应源码测试回答。

## 对 ToolGap-KV 的具体建议

### 版本选择规则

选择 `v0.25.1` 不是因为它被证明为全生态 LTS，而是因为它满足更小、更可审计的
规则：

1. 是编号 release tag，而不是移动分支；
2. 可以记录为精确 commit；
3. 已有本项目关心的 v1 scheduler / KVConnector / CPU offload 源码可审计；
4. 不引入硬件 plugin、LMCache、Mooncake 或分布式依赖作为 Gate A 前置条件；
5. 若有接缝问题，能够把失败归因为一个明确的 release/commit，而不是某天的 `main`。

### 使用规则

| 阶段 | 允许的版本策略 | 不允许的做法 |
| --- | --- | --- |
| Gate A Week 1 | 固定 `v0.25.1` + exact commit，完成 capability matrix。 | 以不断更新的 `main` 混合阅读源码。 |
| Gate A Week 2 | 沿用同一 commit，记录环境、模型 revision、patch hash 与命令。 | 因为 Week 1 不方便就静默换版本继续跑。 |
| 若接缝不成立 | 记录负结论；只有明确说明“新版本含有需要的契约”时才换 tag 并重审受影响项。 | 将另一个版本的源码结论外推到旧 trace。 |
| 未来外部 plugin 集成 | 采用该 plugin 的官方 compatibility matrix 所列的成对版本。 | 只看版本范围或 `latest` 标签。 |

### 对原问题的直接回答

所以，我不建议“先不固定版本，继续审 `main`”；这会让首票的目的——获得可复现的
工程基线——落空。

我也不建议“先审 `v0.25.1`，Gate A 通过时再随意挑一个新的 execution version”；
这会让 Week 1 的源码结论与 Week 2 trace 脱钩。

推荐决策是：**现在就固定 `v0.25.1` / exact commit 作为唯一 baseline；Gate A 只决定
它是否被接受为执行基线，或被明确拒绝并触发一次新的版本选择与重审。**

## 尚未由本调查证明的内容

- `v0.25.1` 是否能在 ToolGap-KV 的目标单 GPU、模型、CUDA/PyTorch 环境构建并运行；
- 原生接口是否足以实现 tool-gap 生命周期，或需要一个窄 core patch；
- retain、offload、recompute 三条路径能否被强制、归因和安全恢复；
- v0.25.1 是否优于 v0.24.x、v0.22.x 或未来版本。这是 Gate A 的工程选择题，不是
  社区资料可以替代的测量结论。

这些不确定性应由 Gate A 的 capability matrix、最小 vertical slice 与 trace 解决。
