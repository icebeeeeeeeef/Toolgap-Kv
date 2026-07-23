# AI Infra / LLM Serving 项目组合评审提示词

> **历史评审输入，不是现行项目规范。** 本文保存六候选评审发生前的事实、
> 假设和问题结构，其中 policy-centered ToolGap-KV 与候选排序已被
> [`docs/agent-kv/FIRST_PRINCIPLES.md`](../agent-kv/FIRST_PRINCIPLES.md)、
> [`docs/agent-kv/ROADMAP.md`](../agent-kv/ROADMAP.md) 和
> [`docs/agent-kv/DECISIONS.md`](../agent-kv/DECISIONS.md) 取代。引用本文时必须
> 明确它是评审输入，不能把其中 roadmap、候选推荐或待复现缺口写成当前结论。

> 用法：将本文从“提示词开始”到“提示词结束”完整复制给另一个 Agent。
> 如果 Agent 能访问本地仓库，让它先读“本地材料”；如果不能访问，本文的项目摘要仍足以完成第一轮评审。
> 本提示词中的上游状态以 2026-07-13 的核验结果为背景，评审 Agent 必须重新检查可能变化的 PR、Issue、API 和 release 状态。

---

## 提示词开始

你现在扮演三种角色的联合评审者：

1. 负责招聘 AI Infra / LLM Serving 校招生的推理团队 TL；
2. 熟悉 vLLM、SGLang、KV Cache、P/D disaggregation 和 serving control plane 的系统工程师；
3. 对项目新颖性、可行性和因果证据持怀疑态度的 systems reviewer。

你的任务不是帮助候选人美化方案，而是判断：下面六个候选项目中，哪一个最值得作为求职主项目，哪一个只能作为备选、支撑模块或学习材料。请大胆反驳已有方案，但必须给出第一性原理、源码、官方文档、论文、实验设计或工程约束层面的理由。

不要因为候选人已经投入时间就迁就现有方向。不要输出“都很有价值，可以组合成平台”。如果多个机制能够独立成功或失败，它们就是不同项目；必须执行范围否决并做取舍。

## 一、候选人的就业目标与约束

### 目标岗位

- 2027 届校招。
- 第一目标：`AI Infra / LLM Serving / 大模型推理平台 / 推理调度 / 模型服务后端`。
- 希望进入推理团队中偏 serving、KV Cache、调度、数据移动、控制面、可靠性和性能评测的岗位。
- 可以做 vLLM 的运行时集成、connector、scheduler-adjacent extension 和小型可审计 patch。
- 不把纯 CUDA kernel、算子优化、编译器或推理引擎核心研发作为主要求职身份；这些只需达到能解释系统影响和回答面试追问的程度。
- 更安全的后备岗位是后端基础架构、云服务后端、存储后端。

代表性目标 JD 的职责动词包括：构建/维护模型 serving 平台，做请求调度与 routing，管理 KV/Prefix Cache，理解 continuous batching、chunked prefill 和 P/D separation，建立 benchmark/observability，诊断 TTFT、TPOT、throughput 与 p95/p99，并在负载、显存、计算和数据移动之间做在线 trade-off。评审时先匹配这些职责，不要按框架关键词数量评分。

### 已知候选人背景

- 软件工程师，系统/后端经历强于模型算法经历。
- 主要语言与经验侧重 Go、Python、Linux、并发、网络、存储和分布式系统。
- 有字节跳动对象存储数据面相关实习经历，希望把数据移动、状态机、失败语义和可观测性经验迁移到推理基础设施。
- 评审时请将这些信息视为给定背景；如果你认为还缺少决定性信息，先写明假设，但不要停止评审。

### 项目约束

- 个人项目，必须能由一个人完成主要闭环。
- 当前不能假设长期拥有多机多卡、RDMA、CXL 或生产集群。
- 可以租用单机整卡 GPU 做阶段性实验，但任何 GPU 型号、带宽、性能数据都必须现场测量，不能预设。
- 优先使用现有引擎最小、可维护的 extension point；只有证明缺失契约后，才允许做小型 core patch。
- 项目的首要价值是形成可检查的工程证据和 20 分钟以上的深入面试讨论，不要求论文级首创。
- 项目不能靠堆叠 vLLM、SGLang、LMCache、Mooncake、Ray、Kubernetes 等关键词获得价值。

### 希望最终证明的候选人能力

```text
理解并修改真实推理 serving/runtime 路径
识别正确的状态所有权与扩展接口
处理并发、异步、取消、超时、重复事件和失败恢复
建立 workload -> mechanism -> resource -> metric 的因果链
用 baseline、ablation、tail latency 和负结果验证判断
区分个人实现、依赖能力、论文结论与未来计划
```

## 二、强制证据规则

所有实质性结论必须属于以下状态之一：

- `roadmap`：计划或设计，尚未实现；
- `shipped`：已经实现，并在所述系统中实际运行过；
- `experimentally validated`：在明确硬件、版本、workload 和实验协议下得到测量支持；
- `simulated`：仅由 replay、trace、optimizer、cost model 或 simulator 支持，并明确校准限制。

必须分别标记：

```text
候选人仓库的证据状态
上游项目的实现状态
论文在作者实验环境中的结果状态
你根据源码做出的推断
尚待复现的漏洞或性能假设
```

禁止：

- 把上游已经实现的能力写成候选人实现；
- 把论文数字直接外推到候选人的环境；
- 把 simulation 写成真实 serving 性能；
- 在没有 failing test 前把候选缺口称为 bug；
- 用时态把 roadmap 改写成简历成果；
- 在没有穷尽最新 related work 前使用“首次”“唯一”“业界首个”。

## 三、候选项目 A：ToolGap-KV

### 当前事实状态

项目主机制仍为 `roadmap`，但仓库并非完全没有代码。

当前可以标为 `shipped` 的只有 repository/Phase 0 scaffolding：

- engine-independent `ToolGapEvent`、lifecycle action enums 和简化版 `DecisionTrace`；
- Phase 0 config、manifest、三路径 workload/实验协议；
- schema/repository validator 和 7 个 contract tests。

当前不存在：

- vLLM runtime integration；
- lifecycle state machine 与真实 retain/offload/recompute executors；
- GPU/CPU 实验结果或 simulator result；
- dynamic policy 与性能提升；
- upstream contribution 或 production validation。

因此安全表述是：`Phase 0 repository contracts and validation scaffolding are shipped; the serving/runtime mechanism remains roadmap.`

仓库还存在一个需要评审的战略分歧：现有 README/PROJECT 把“dynamic policy 是否胜过 tuned static TTL”作为中心成功问题；较新的 `FIRST_PRINCIPLES.md` 建议把 integration、correctness、measured boundary 和 interview-ready engineering evidence 作为主成功函数，把 dynamic policy 降为条件性分支。该文件仍有 adoption gate，旧文档尚未全部对齐。请明确判断应保留 policy-centered mainline，还是 reshape 为 contract/evidence-centered mainline。

### 招聘可读名称

`KV Cache Lifecycle Runtime for Tool-Using LLM Agents`
`ToolGap-KV` 只作为仓库/系统代号，不作为第一次出现的主标题。

### 核心问题

Agent 在 tool call 期间暂停，已有 KV 暂时空闲但可能继续复用。运行时需要在三种动作间选择：

| 动作 | 收益 | 成本 |
|---|---|---|
| retain | resume 最快 | tool gap 期间占用稀缺 HBM |
| offload | 释放 HBM 且保留计算结果 | D2H/H2D、队列和带宽竞争 |
| recompute | 等待期间不占缓存层资源 | resume 后重复 prefill |

可证伪问题：

> 在哪些 restore/recompute cost ratio、KV working-set pressure、arrival load、tool-gap distribution 和 resume probability 下，动态 lifecycle policy 能显著优于调优后的 static TTL，同时不造成不可接受的 p95/p99、scheduler overhead 或 active-request regression？

第一性原理：token history 与兼容的 model/runtime identity 是权威状态；GPU/CPU KV 是可以丢弃和重算的派生物化状态。

初始成本模型：

```text
C_retain = HBM opportunity cost(bytes, gap, pressure)

C_offload = T_store(bytes, contention)
          + P(resume) * T_restore(bytes, contention)
          + queue/failure penalty

C_recompute = P(resume) * T_prefill(tokens, batch, load)
```

候选人计划拥有的部分：

- tool-wait/resume lifecycle state machine；
- cost profiler 与透明 analytic policy；
- retain/offload/recompute executor orchestration；
- epoch、cancel、duplicate resume、late completion 和 safe fallback；
- request-level `DecisionTrace`；
- workload、baseline、fault injection 和结果归因。

不属于候选人所有权：vLLM 的 PagedAttention、scheduler 主体、native CPU transfer、CUDA kernel 和依赖自身的性能。

### 最小可信 Phase 0

1. pin 一个当前 vLLM commit、模型、驱动、GPU/CPU/NUMA 环境；
2. 确认真实生命周期对象更接近 `session + turn + compatible prefix block set + epoch`，而不是假定原 request 在 tool gap 中持续存活；
3. 生成一个固定 prompt、固定 tool gap、固定 resume 的确定性 workload；
4. 强制出现 GPU hit、CPU restore 和 recompute 三条不同路径；
5. 分解测量 queue wait、store、restore、prefill、first token 和 active-request interference；
6. 输出原始 trace、环境 manifest、运行命令和一份 DecisionTrace 样例。

当前代码还有一个具体 contract gap：实验文档要求 non-fallback run 的 requested action 与 observed action 一致，但当前简化 `DecisionTrace` 主要校验 token accounting，尚未强制 `retain -> gpu_hit`、`offload -> cpu_restore`、`recompute -> recompute`。评审者应判断这是 Phase 0 应立即修正的 invariant，还是某些 fallback/engine behavior 下需要更细的映射语义。

### 主要 baseline

- engine default / recompute；
- tuned static TTL；
- soft retention；
- always offload；
- dynamic policy 只有在多个可到达 regime 确实偏好不同动作后才允许进入主线。

### Stop / pivot 条件

- 当前 vLLM 无法通过可维护 seam 观测或控制必要语义；
- CPU restore 与 recompute 在可用环境中无法稳定区分和测量；
- tuned static TTL 已接近可行 hindsight bound；
- runtime 可观察量不足以支持可归因的 dynamic policy；
- workload 不能产生可信的 tool-wait、resume burst 或 HBM pressure；
- 核心实现需要广泛 core fork；
- 如果动态策略失败，但 integration、correctness 和 break-even study 成立，可重塑为 lifecycle conformance / measurement study，而不是伪造性能胜利。

建议把立项门拆成两层分别评审：

```text
Gate A: mechanism conformance
  三条路径是否真实存在、可强制、可观察、可归因、可安全 fallback？

Gate B: economic feasibility
  是否至少存在两个可到达且分别偏好不同动作的 regime，值得引入动态策略？
```

Gate A 通过不能证明 Gate B；Gate B 尚未验证也不应阻止先形成 runtime integration/correctness 证据。

### 必须质疑的问题

1. 原始 request 已完成后，候选人实际控制的 lifecycle object 到底是什么？
2. vLLM native offload/per-request policy 已覆盖多少，候选人的缺失契约是什么？
3. tool-gap duration 或 resume probability 是否真的能在 decision time 获得？
4. 与 InferCept、Continuum、Astraea、KVFlow、PBKV 相比，剩余价值是新 policy、当前引擎证据、正确性契约还是评测？
5. 如果 static TTL 足够好，ToolGap-KV 是否仍能形成强求职项目？
6. 当前项目成功函数究竟是“dynamic policy 获胜”，还是“CT1 integration + CT2 correctness + CT3 measured boundary”；为什么？

## 四、候选项目 B：NIXL KV Handoff Fencing & Conformance

### 当前事实状态

候选项目为 `roadmap`。vLLM NIXL 的 source lease、heartbeat、expiry reclaim、compatibility hash 和 receive-complete scheduling 是上游能力；SGLang KV-Canary 的 KV byte verification 和 corruption injection 也是上游能力，不能计入候选人所有权。

### 候选缺口

在 pin 的当前 vLLM NIXL 版本上验证 heterogeneous-TP P/D handoff completion 是否缺少：

```text
per-handoff epoch
explicit consumer identity
deduplicated unique-consumer quorum
stale/ABA completion fencing
producer/destination two-sided terminal accounting
```

从公开代码观察到的通知计数行为只是待验证线索，不是已确认漏洞。

### 若缺口成立的最小机制

```text
HandoffAck {
  handoff_id
  epoch
  state_version
  consumer_rank
  manifest_hash
  terminal_status
}

release source KV only when:
  ack epoch/state_version matches current handoff
  AND unique consumer ranks satisfy the expected set
  OR the lease expires and recovery follows an explicit safe outcome
```

同时建立 producer pinned bytes 与 destination reserved bytes 可关联的 terminal ledger。

### 10 个工作日 falsification gate

- 在未修改 vLLM 上注入 duplicate、stale、reordered、retry/ABA、partial heterogeneous-TP completion；
- 必须复现安全性缺口，例如 premature free、unsafe consume 或无法核账的资源终态；单纯 timeout 或吞吐下降不能冒充 correctness bug；
- 若当前实现已经拥有 epoch、identity dedup、pre-consume validation 和双边 ledger，立即撤销 novelty；
- 若 10 个工作日没有最小 failing test，停止协议创新，最多保留 upstream conformance tests；
- 若修复必须深入 attention/scheduler hot path 或维护大 fork，拒绝该方向；
- metadata/fencing gate 必须位于 first decode token 之前；
- 正常路径 p95 TTFT overhead 的预注册失败线可设为 `max(2%, 1ms)`，但评审者应判断该阈值是否合理。

### 必须质疑的问题

1. 通知后端是否已经隐含提供去重、顺序或 sender identity？
2. request id 能否重用，是否真的存在 ABA？
3. lease expiry 是否已经足以保证安全，只缺少 observability？
4. 两端 resource ledger 是新 correctness mechanism，还是普通 telemetry？
5. 该项目是否过窄到只能形成一个 bug fix，而不足以支撑完整项目？

## 五、候选项目 C：KV State Ledger + Reconciliation

### 当前事实状态

`roadmap`。

### 核心问题

当 KV location、tier、owner 和 availability 来自异步事件时，event loss、duplicate、reorder、restart 和 propagation lag 会让 router/admission 使用错误状态。项目维护的是带 freshness/epoch/confidence 的观测账本，而不是假装拥有强一致全局真相。

```text
prefix/block
  -> observed location/tier/owner
  -> last epoch and observation time
  -> confidence/freshness
  -> reconciliation result
  -> routing/admission DecisionTrace
```

### 可证伪问题

> 相比 request-history inferred locality 或未经 reconciliation 的 event index，显式 ledger 是否能在事件异常和进程重启下显著降低 false-locality、错误路由和 orphan state，同时不让 routing latency 失控？

### 主要指标

- false-positive / false-negative locality；
- event lag 和 convergence time；
- reconciliation time；
- avoidable miss / recompute；
- stale-route rate；
- orphan bytes；
- routing p95 overhead；
- DecisionTrace 的事实来源与置信度。

### Stop 条件

- 只是在现有 router 外包一层状态 map；
- 无法比 request-history baseline 更准确解释错误位置；
- 没有真实 KV event/connector artifact，只能手写理想事件；
- reconciliation 语义无法对应任何实际 serving 决策。

### 必须质疑的问题

1. ledger 是事实源、缓存、索引还是观察模型？谁才是 authority？
2. 位置事件的 block/prefix 粒度如何与 scheduler/request 粒度对齐？
3. stale location 的真实代价是 fallback miss、重复传输还是 correctness 问题？
4. 这是不是已有 KV-aware router / event index 的重复实现？

## 六、候选项目 D：Agent KV Regime Lab

### 当前事实状态

`roadmap`；如果只有 trace/replay/simulator，结果只能标为 `simulated`。至少对接一个真实 engine/backend 并报告校准误差后，相关轴才可能标为 `experimentally validated`。

### 核心问题

Agent workload 的 cache value 与 recency 脱钩：tool wait、fan-out、subagent termination、retry、context compaction 和 correlated resume 会形成普通 chat benchmark 看不到的 pressure regime。

项目不再发明 dynamic TTL 或 workflow-aware prefetch，而是构造可重放 workload，寻找策略的收益区、负收益区和容量相变：

```text
tool-gap distribution
fan-out / branch lifetime
success vs failure trajectory
compaction and invalidation
concurrency and correlated resume
HBM / DRAM / storage capacity
compute vs transfer bandwidth
```

### 输出与指标

- workload trace schema 和 generator/replay；
- TTFT、TPOT、JCT、Goodput@SLO；
- cache hit、extra prefill、migration bytes；
- HBM occupancy、CPU-tier occupancy、NIC/PCIe utilization；
- middle-phase thrashing 与 resume burst；
- capacity/bandwidth phase diagram；
- simulator/replay 相对真实 backend 的校准误差。

### Stop 条件

- benchmark 只是随机请求生成器；
- 四周内没有真实 backend 校准；
- workload 参数无法映射到真实 agent execution；
- 只展示命中率改善，没有端到端或资源代价；
- simulator 只能“用自己的假设证明自己的策略”。

### 必须质疑的问题

1. 公开 agent traces 是否足够，还是必须构造 synthetic trace？
2. trace replay 如何保持 scheduler、prefix identity 和 timing fidelity？
3. benchmark 项目是否有足够 candidate-owned hard mechanism？
4. 它更适合成为 ToolGap-KV 的 evidence harness，还是独立主项目？

## 七、候选项目 E：Deadline-aware Transfer-vs-Recompute Controller

### 当前事实状态

候选项目为 `roadmap`。Mooncake TENT 的 deadline-aware RFC、EDF dispatch 和 infeasible-drop hook 属于上游；真实 bandwidth provider、上层 serving deadline 生成和 local recompute 闭环仍需逐版本核验。

### 核心问题

```text
request TTFT budget
  -> queue/prefill estimate
  -> KV transfer deadline and laxity
  -> bandwidth/finish-time estimate
  -> transfer / reorder / drop / local recompute
```

可证伪问题：

> 在带宽波动和 queue estimation error 下，跨层 transfer admission + recompute fallback 是否能提高 Goodput@SLO，并在哪些区域因错误估计、重复计算或干扰 active decode 而失败？

### Phase 0

- trace-driven simulator；
- 对比 FIFO、priority、EDF、least-laxity 和 recompute fallback；
- 输出 feasibility precision/recall、deadline miss、wasted transfer bytes、extra compute、Goodput@SLO；
- 明确 bandwidth estimator error sweep；
- 只有模拟机制成立后再接真实 TENT/serving seam。

### Stop 条件

- 项目只是重写已经 merged 的 EDF；
- deadline 无法从 serving SLO 合理分解；
- 没有真实 transfer path 或带宽 trace；
- 必须拥有多机 RDMA 才能验证核心假设；
- estimator error 让 controller 长期劣于简单 fallback。

### 必须质疑的问题

1. 谁拥有 end-to-end SLO，谁有权 drop 或 recompute？
2. transfer 与 recompute 是否真的可互换，正确性条件是什么？
3. 上游 TENT 留下的是实现缺口、产品集成缺口，还是只是部署工作？
4. 对个人项目来说，网络环境是否让核心证据不可获得？

## 八、候选项目 F：Agentic Serving Hint Gateway + Trace Benchmark

### 当前事实状态

`roadmap`。NVIDIA Dynamo 已公开演进中的 `nvext.agent_hints`，但这不代表候选人的 schema 会被任何引擎采用。

### 核心问题

Agent harness 知道 serving runtime 看不到的生命周期事实，例如：

```text
session / branch / subagent id
interactive vs background priority
expected output length
tool-wait ETA
persistent vs ephemeral token ranges
retention TTL
compaction / subagent termination
```

项目可以构建 OpenAI-compatible gateway，把 hint 映射到 Dynamo、GAIE EPP metadata 或 replay backend；但必须先证明 hint 的因果价值，再讨论通用协议。

### 可证伪问题

> 哪些 harness-known hints 在 workload shift 和 estimation error 下，仍能稳定改善 workflow SLO、减少无效 KV retention 或降低额外 prefill？

### Stop 条件

- 只有漂亮 schema 和 adapter，没有机制收益；
- 少于两个 hint 能独立通过 ablation；
- hint 的真实值在部署中不可获得；
- workload 泄漏未来信息，形成不公平 oracle；
- 项目退化成普通 API gateway。

### 必须质疑的问题

1. 每个 hint 在决策时是否真实可见？
2. hint 错误或缺失时如何 fallback？
3. 这是 ToolGap-KV 的 signal-source 子模块，还是独立项目？
4. 为什么需要新 contract，而不是已有 header/metadata？

## 九、候选项目之间的重叠警告

不要默认把六个方向合并。请重点判断以下关系：

| 关系 | 待评审判断 |
|---|---|
| ToolGap-KV ↔ Agent KV Regime Lab | Regime Lab 可能是 ToolGap 的 workload/evidence harness，而不是第二主机制 |
| ToolGap-KV ↔ Hint Gateway | hints 可能只是 ToolGap policy 的输入来源；若独立做，需要自己的可证伪收益 |
| ToolGap-KV ↔ KV State Ledger | DecisionTrace 是请求级因果记录；Ledger 是跨请求/实例的观测状态，不能只因都叫 ledger/trace 就合并 |
| ToolGap-KV ↔ NIXL fencing | 都涉及 epoch 和 fallback，但前者是 paused-agent lifecycle，后者是 P/D handoff completion；可独立成败 |
| ToolGap-KV ↔ Deadline controller | 都做 transfer-vs-recompute 决策，但 deadline controller 面向网络 transfer SLO，硬件和所有权不同 |
| NIXL fencing ↔ KV State Ledger | terminal ledger 可成为 fencing 的证据对象，但通用 distributed-state reconciliation 是更大的独立问题 |

评审时至少比较三种组合策略：

1. **保留 ToolGap-KV 为主线**：Regime Lab 作为 harness，其他方向全部延期；
2. **以 10 天 falsification spike 挑战 ToolGap-KV**：如果 NIXL 确有安全缺口，转成更窄的 connector correctness 项目；
3. **硬件受限时重塑为 KV State Ledger**：以真实 event/reconciliation 和 serving decision 为主，不伪装成性能项目。

你可以提出第四种方案，但必须证明它没有把两个独立成功条件强行塞进同一主线。

## 十、必须阅读或核验的材料

### A. 如果可以访问本地仓库

先按顺序阅读：

1. `README.md`
2. `src/toolgap_kv/phase0.py`
3. `tests/test_phase0.py`
4. `experiments/0001-mechanism-feasibility/README.md`
5. `experiments/0001-mechanism-feasibility/manifest.json`
6. `docs/agent-kv/README.md`
7. `docs/agent-kv/FIRST_PRINCIPLES.md`
8. `docs/agent-kv/PROJECT.md`
9. `docs/agent-kv/ARCHITECTURE.md`
10. `docs/agent-kv/ROADMAP.md`
11. `docs/agent-kv/EVALUATION.md`
12. `docs/agent-kv/RELATED_WORK.md`
13. `docs/agent-kv/DECISIONS.md`
14. `docs/agent-kv/INTERVIEW_MAP.md`
15. `docs/research/2026-07-13-serving-kv-project-directions.md`
16. `docs/research/2026-07-13-wechat-ai-infra-article-ledger.md`

本地文档只代表项目当前设计，不是事实权威；上游状态仍需外部复核。

### B. 上游实现与接口

- vLLM NIXL KV cache lease design：
  https://github.com/vllm-project/vllm/blob/main/docs/design/nixl_kv_cache_lease.md
- vLLM NIXL lease PR #41383：
  https://github.com/vllm-project/vllm/pull/41383
- vLLM native CPU offload RFC #19854：
  https://github.com/vllm-project/vllm/issues/19854
- vLLM CPU offload CachePolicy PR #37874：
  https://github.com/vllm-project/vllm/pull/37874
- vLLM context-aware retention RFC #37003：
  https://github.com/vllm-project/vllm/issues/37003
- 对应但已关闭的 PR #38514：
  https://github.com/vllm-project/vllm/pull/38514
- SGLang KV-Canary core / fault injection / real-byte verification：
  https://github.com/sgl-project/sglang/pull/26808
  https://github.com/sgl-project/sglang/pull/26816
  https://github.com/sgl-project/sglang/pull/26817
- Mooncake TENT overview：
  https://github.com/kvcache-ai/Mooncake/blob/main/docs/source/design/tent/overview.md
- TENT deadline RFC / EDF / infeasible drop：
  https://github.com/kvcache-ai/Mooncake/issues/2519
  https://github.com/kvcache-ai/Mooncake/pull/2763
  https://github.com/kvcache-ai/Mooncake/pull/2764
- NVIDIA Dynamo agent hints：
  https://developer.nvidia.com/blog/full-stack-optimizations-for-agentic-inference-with-nvidia-dynamo/
- Gateway API Inference Extension：
  https://gateway-api-inference-extension.sigs.k8s.io/
- llm-d KV-cache routing evidence：
  https://llm-d.ai/blog/kvcache-wins-you-can-see
- vLLM Router：
  https://github.com/vllm-project/router
- llm-d Router：
  https://github.com/llm-d/llm-d-router
- LMCache releases：
  https://github.com/LMCache/LMCache/releases

检查 main/目标 commit 的当前源码，不要只读 PR 描述。PR 状态、接口和实现可能已经变化。评审 KV State Ledger 时还必须读取目标 vLLM commit 的 KVEvents 实现、事件粒度与丢失/重放语义。

### C. 最接近的论文与工作

- InferCept：interception 期间 preserve/swap/discard/recompute
  https://arxiv.org/abs/2402.01869
- Continuum：tool-duration-aware lifecycle/TTL
  https://arxiv.org/abs/2511.02230
- Astraea：I/O wait 与 memory-pressure-aware lifecycle
  https://arxiv.org/abs/2512.14142
- KVFlow：agent step graph、workflow-aware eviction/prefetch
  https://arxiv.org/abs/2507.07400
- PBKV：prediction-aware agent KV management
  https://arxiv.org/abs/2605.06472
- Heterogeneous Inference design space：
  https://arxiv.org/abs/2606.29708
- CONCUR：
  https://arxiv.org/abs/2601.22705
- DualPath：
  https://arxiv.org/abs/2602.21548
- HexAGenT：
  https://arxiv.org/abs/2605.16637
- Agentic AI Workload Characteristics：
  https://arxiv.org/abs/2605.26297
- Resident KV Claims：
  https://arxiv.org/abs/2605.24259
- MARCONI：cost-aware prefix-cache admission/eviction
  https://arxiv.org/abs/2411.19379
- MFS：deadline-aware KV transfer scheduling
  https://arxiv.org/abs/2603.17456
- Tair HiSim 官方方法说明：
  https://www.alibabacloud.com/blog/alibaba-cloud-tair-kvcache-simulation-analysis-high-precision-computational-and-caching-simulation-design-and-implementation_603164

对于每篇最相关论文，请至少阅读 abstract、system/mechanism、evaluation、limitations 和 implementation availability。不要只根据标题判断覆盖关系。

## 十一、评审流程

### Step 1：先做事实审计

为六个项目分别建立表格：

| 项目 | 仓库当前状态 | 上游已有能力 | 尚未证明的假设 | 候选人可拥有的 hard part | 最近 prior art |
|---|---|---|---|---|---|

任何事实不确定时标记 `unverified`，并说明需要查看哪个源码、commit、artifact 或实验。

### Step 2：写出每个项目唯一的因果问题

每个项目只能有一个主问题，格式如下：

```text
Observed phenomenon:
Resource or correctness bottleneck:
Owned intervention:
Causal mechanism:
Primary metric:
Guardrail metrics:
Strongest baseline:
Losing condition:
Kill criterion:
```

如果一个项目需要两个独立 intervention、baseline 或 ablation 才能成立，判定为 scope failure，并拆分。

### Step 3：运行硬门槛

逐项目判断 Pass / Fail / Unknown：

1. Target：是否直接对应目标岗位职责；
2. Real problem：是否有源码、trace、Issue、论文或可信 workload 支持；
3. Falsifiability：是否能被明确指标和失败条件推翻；
4. Ownership：候选人是否拥有 hard mechanism，而不只是配置/胶水；
5. Feasibility：个人时间、硬件和数据是否足够；
6. Baseline：是否存在强而公平的比较对象；
7. Measurement：workload、环境、重复次数、尾延迟与归因是否能定义；
8. Reproducibility：第三方是否能通过命令和 artifact 重现；
9. Defensibility：能否支持五层 why/alternative/failure/scale 追问；
10. Credibility：所有主张是否有诚实状态和证据所有者。

任何关键硬门槛 Fail 都优先于总分。

### Step 4：100 分评分

- 岗位相关性与问题价值：15；
- 个人所有权与可归因性：15；
- 机制和跨层深度：20；
- 证据与实验严谨性：25；
- 工程完整性与可复现性：10；
- trade-off 与失败边界：10；
- 表达与包装清晰度：5。

同时给出：

- 当前状态分数；
- 假设按计划完成后的潜力分数；
- 最大不确定性；
- 最弱维度；
- `select / reshape / defer / reject` verdict。

不要用未来潜力掩盖当前证据为零。

### Step 5：做组合与去重判断

明确回答：

1. 哪一个应成为唯一主项目？
2. 哪一个可以作为主项目的必要支撑模块？
3. 哪一个应作为条件性备选？
4. 哪些必须 defer 或 reject？
5. ToolGap-KV 应保留、重塑还是放弃？
6. 六个方向是否覆盖相同招聘信号，导致重复投资？
7. 如果只能投入 8–12 周，最佳证据密度最高的选择是什么？
8. 哪个方向最快产生第一份可信 artifact，而不是最快产生漂亮架构图？

最终只能推荐一个主线和一个备选。不要并列推荐三个以上方向。

### Step 6：为选中主线设计最小可信执行闭环

至少包括：

```text
exact research/engineering question
pinned upstream commit and smallest integration seam
one owned mechanism
one strong baseline
one deterministic workload
one fault or negative case
primary and guardrail metrics
environment manifest
raw artifact layout
week-by-week Phase 0
go/no-go and kill gates
what must stay excluded
```

如果 Phase 0 仍需要多个引擎、多节点 RDMA、训练预测模型或大规模生产 trace，说明范围仍然过大。

### Step 7：招聘与面试压力测试

为主项目生成至少 12 个递进问题，覆盖：

- 为什么是这个问题；
- 为什么是这个 integration seam；
- authoritative state、derived state 和 ownership；
- 并发、取消、late completion、duplicate、partial failure；
- transfer/recompute/HBM 的 break-even；
- workload 与 baseline 公平性；
- mean 与 p95/p99；
- 一个失败实验；
- 一个被拒绝设计；
- 10x scale 后的新瓶颈；
- 哪些来自依赖，哪些由候选人实现；
- 哪项结论仍是 simulated 或 roadmap。

判断它能否支持一次 20 分钟的深入讨论，而不是只回答框架定义。

### Step 8：给出诚实的项目包装

分别输出：

1. **当前状态描述**：只能使用已有证据；
2. **完成后的条件式简历 bullet**：所有数字保留 `[X]`、`[hardware]`、`[workload]` 占位符，除非仓库有原始 artifact；
3. **30 秒面试版本**；
4. **一句话拒绝边界**：明确没有做 kernel、没有做 production、没有拥有依赖实现；
5. **最危险的过度主张**。

## 十二、最终输出格式

请严格按下面顺序回答：

1. **一段话最终 verdict**：直接选主线和备选；
2. **你最强烈的反对意见**：禁止先表扬；
3. **事实与证据审计表**；
4. **六项目硬门槛与评分表**；
5. **重叠/依赖/互斥分析**；
6. **为什么不是其他方向**；
7. **选中主线的因果问题与最小 Phase 0**；
8. **kill gates 和负结果价值**；
9. **岗位/JD 能力映射**；
10. **12 个以上面试追问与合格回答要点**；
11. **当前状态与完成后两套项目包装**；
12. **拒绝合并进主线的技术清单**；
13. **仍需补充或实时核验的信息**；
14. **引用的一手来源列表及核验日期/状态**。

## 十三、评审风格要求

- 结论先行，不要先复述六个项目；
- 使用第一性原理和对抗式审查；
- 不要因为描述完整就假设方案正确；
- 区分“前沿”“新颖”“工程上重要”“适合个人做”四个不同判断；
- 一个成熟问题的高质量复现与扩展可以优于未经验证的新机制；
- 对缺乏硬件、接口或 workload 的方向直接降级；
- 保留负结果，不为获得漂亮简历 bullet 操纵实验范围；
- 如果你的结论依赖最新 upstream 状态，必须联网复核并引用官方仓库、官方文档或论文；
- 微信文章只能作为线索，不能作为上游状态的最终证据；
- 这 45 篇微信文章来自同一信息源且有大量日报重复，热点出现次数不能作为 45 份独立证据；
- 不需要先向我提问。把缺失信息写成假设或敏感性分析，先完成一版完整评审。

## 提示词结束
