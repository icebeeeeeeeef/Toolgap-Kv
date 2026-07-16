# 10｜Serving 路由与平台控制面详细知识列表

> 优先级：P1；包含面试启动前必须完成的 P0 防守子集
>
> 当前状态：已敲定源码主线和减负范围，原理、源码与手写待完成；实验维度不独立要求
>
> 目标熟练度：原理 L3 / 源码 L2 / 手写 L2 / 实验 L0
>
> 依赖：[KV Cache 与内存系统](03-kv-cache-memory-system.md)、[LLM 推理引擎与调度](04-llm-engine-scheduling.md)、[性能分析与实验方法](05-performance-analysis-and-gpu-literacy.md)、[分布式 Serving 数据路径与 PD 分离](09-disaggregated-serving-data-path-and-pd.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能解释控制面怎样根据请求特征、Endpoint 状态、KV locality 和 SLO 选择执行实例，并在状态不完整、过载和故障条件下保持可解释、可降级的决策：

```text
请求特征 + Endpoint 状态 + KV locality + SLO
                    ↓
        compatibility / health / freshness
                    ↓
          admission / overload 判断
                    ↓
    cache-aware + load-aware endpoint scoring
                    ↓
       endpoint selection / retry / fencing
                    ↓
              DecisionTrace
```

回答必须说明状态来源与新鲜度、硬过滤条件、软评分因子、无合法候选时的 fail-closed 行为，以及为什么不能只优化 cache hit 或平均 TTFT。

这是一个约 6-10 小时的 P1 节点。实践主线是读通真实 Router 源码和手写 endpoint selection 核心，不建设第二套 Router 项目，也不设置独立性能实验。

## 与前序节点的 admission 边界

三个 admission 层次共享容量和状态信号，但决策所有权不同：

1. [LLM 推理引擎与调度](04-llm-engine-scheduling.md) 负责单引擎内部 token/KV budget、batch 和 preemption；
2. [分布式 Serving 数据路径与 PD 分离](09-disaggregated-serving-data-path-and-pd.md) 负责 KV ready 后 Decode 是否能够安全接管；
3. 本节点负责集群是否接收请求、哪些 Endpoint 合法、最终选择哪个 Endpoint，以及怎样治理过载和 retry。

不能把三层 admission 都塞进一个 scheduler，也不能让 Router 直接拥有 engine block allocation 或 PD handoff 完成状态机。

## P0 防守要求

开始目标岗位面试前，应能脱稿回答：

1. Router、单引擎 scheduler 和集群 control plane 的职责边界；
2. Round-robin、least-request、Power-of-Two、consistent hashing 与 prefix/cache-aware routing 的适用条件；
3. 缓存命中最高的实例为什么不一定是最佳实例；
4. request-history 推断 locality 与 KV event/index 精确状态的成本差异；
5. health 为什么要区分 liveness、readiness、overloaded 和 draining；
6. 事件延迟、丢失、乱序、重复和重启恢复为什么会让 Router 相信错误状态；
7. admission、backpressure、排队和 overload rejection 的关系；
8. retry 为什么可能造成重复执行、缓存污染和负载放大；
9. request ID、attempt、epoch 和幂等语义怎样约束 retry；
10. 为什么只优化平均 TTFT 或 cache hit rate 可能损害 p95/p99、TPOT 和 Goodput@SLO；
11. autoscaling 为什么不能只观察 GPU utilization；
12. 扩容延迟、模型加载、KV warming 和测量滞后为什么会形成不稳定反馈。

P0 验收是一道 15 分钟连续场景题：

> 有 8 个 vLLM 实例，部分实例拥有请求前缀 KV，但队列更长；KV 状态事件存在 500 ms 延迟，同时一个实例正在 draining。设计路由、准入、重试和降级策略，并说明状态所有者、硬过滤条件、评分因子、fallback、指标和关闭 cache-aware 策略的条件。

回答不能只给出一个加权公式。必须先区分 eligibility 与 preference，并覆盖陈旧状态、无合法 Endpoint、retry amplification 和 locality 热点。

## P1 详细知识列表

### 路由策略与决策分层

- Round-robin 状态成本低，但不感知负载和 KV locality；
- random 与 Power-of-Two 用较低状态成本换取不同程度的负载均衡；
- least-request/least-loaded 依赖足够新鲜且可比较的负载状态；
- consistent hashing/session affinity 可以增加会话或前缀复用，但可能制造热点；
- prefix/cache-aware routing 根据已有 KV 减少重复 Prefill，但要支付 locality 状态维护成本；
- eligibility 是 model/revision/parallel compatibility、health、freshness、quota 等硬约束；
- preference 是 locality、queue、capacity、cost 和 SLO 等软评分；
- 硬过滤必须先于软评分，不能用高 locality 覆盖版本不兼容或实例不可读；
- score 应能拆成各因子并写入 DecisionTrace，避免只输出不可解释的总分；
- 没有合法候选时应 reject、defer 或执行明确定义的 fallback，不能随意选一个实例。

### 状态来源、freshness 与 reconciliation

- Endpoint discovery 只提供成员关系，不代表实例已经 ready；
- health、inflight/queue、KV capacity、model revision、TP config 和 locality 可能来自不同数据源；
- pull metrics、request history 和事件流具有不同的成本、时效与一致性；
- 事件驱动 KV index 必须面对 duplicate、reorder、loss、restart 和 propagation lag；
- observed time、source epoch、worker incarnation 和 confidence 可以限制陈旧事实的影响；
- 状态超过 freshness budget 时应降权或失效，不能继续假装它精确；
- reconciliation 用于重新对账事件索引与 Endpoint 当前状态；
- Router 通常只有观测状态，而没有强一致全局真相，因此不确定时应保守降级。

### Cache locality 与负载冲突

- KV 命中可以减少 Prefill，但长队列或容量紧张可能抵消收益；
- cache hit rate、cached token 数和真正避免的 Prefill 时间不是同一个指标；
- 高复用前缀可能导致 affinity 热点，需要候选扩散和负载上限；
- 短 Prompt、低复用或低负载时，维护精确 locality 的成本可能没有回报；
- queue length 需要结合请求阶段、Prompt/Output 长度和并行配置解释；
- routing score 只能使用请求进入时已经存在的信号，不能泄漏事后结果；
- tuned simple baseline 应优先于复杂策略，复杂状态没有稳定收益时应退回基线。

### Admission、backpressure 与 retry

- 集群级 admission 判断是否存在满足模型、容量、健康和 SLO 的候选；
- backpressure 应从 Endpoint、Router 向上游入口传播，不能只在最底层无限排队；
- bounded queue、reject、defer、降级模型和 fallback 具有不同的调用方语义；
- overload 状态需要滞回或稳定窗口，避免 Endpoint 在 ready/not-ready 间抖动；
- retry 必须限制次数、总 deadline 和可重试错误类型；
- 连接失败、请求未开始、部分输出和已执行但响应丢失具有不同的 retry 安全性；
- circuit breaker 隔离持续失败 Endpoint，half-open 探测也需要流量限制；
- draining 实例不接收新请求，但已有请求、KV 和连接需要明确完成或迁移规则；
- retry、reroute 和 recompute 都会消耗资源，错误恢复可能进一步放大过载。

### SLO、观测与控制回路

- 分别理解 TTFT、TPOT/ITL、E2E latency、request/token throughput 和 Goodput@SLO；
- p50 不能替代 p95/p99，cache hit 不能替代端到端收益；
- Router 侧关注 routing latency、candidate count、filter reason、score breakdown、retry 和 rejection；
- Endpoint 侧关注 queue、inflight、KV utilization、model/role 和 health transition；
- DecisionTrace 保存输入状态版本、过滤理由、分数构成和最终动作；
- autoscaling 信号可以来自队列、arrival rate、token demand、SLO miss 和预测负载，而不只是 GPU utilization；
- 冷启动、模型加载、topology placement 和 KV warming 会造成动作到效果的延迟；
- 控制周期过短、状态滞后或同时修改多个变量可能产生振荡；
- autoscaling 只要求场景设计，不进入实现、源码或实验验收。

## 平台能力的非对称深度

### P1 场景能力

要求能够设计并解释：

- Endpoint discovery、状态汇聚和 freshness；
- worker failure、draining、灰度发布和版本兼容；
- autoscaling 的输入信号、冷启动和稳定性；
- topology、模型版本和 TP 配置约束下的 placement；
- 多租户 namespace、quota、公平性和 cache isolation；
- 路由 DecisionTrace、SLO dashboard 和故障归因。

### P2 了解即可

- Kubernetes CRD/controller reconciliation；
- Gateway API Inference Extension 的 InferencePool 与 Endpoint Picker；
- Ray Serve、AIBrix、llm-d 等平台的整体定位；
- leader election、etcd、一致性协议和跨地域容灾。

这些内容用于回答平台场景题和识别系统边界，不产生源码、手写或实验验收要求。

## 源码 L2 契约

### 主实现

固定学习开始时的 [vLLM Router](https://github.com/vllm-project/router) release/commit，沿以下路径阅读：

```text
request parsing
  -> worker discovery / endpoint state
  -> candidate eligibility
  -> routing policy / scoring
  -> endpoint selection
  -> request forwarding
  -> retry / circuit breaker
  -> metrics and state update
```

读完必须回答：

- 请求的 model、session/prefix 和 request ID 在哪里进入路由；
- worker/Endpoint 状态从哪里建立并更新；
- policy 接口的输入、输出和状态依赖是什么；
- Round-robin、Power-of-Two、consistent hashing 和 cache-aware 的选择路径；
- eligibility filter 与 ranking/scoring 是否分离；
- locality 与负载信号怎样组合或冲突；
- unhealthy、draining 或 circuit-open Endpoint 怎样被排除；
- retry 在哪些错误和请求阶段发生，怎样限制放大；
- metrics 和请求完成事件怎样更新路由状态；
- 哪些职责属于 Router，哪些属于 vLLM engine、service discovery 或外部平台。

源码笔记必须保存项目、release/commit、入口、关键对象、控制流、失败路径、已知版本差异和一张请求时序图。

vLLM Router 核心包含 Rust，但不把 Rust、Tokio/async runtime、HTTP proxy 和所有部署集成扩展成新的学习节点。目标是完整讲清关键链路，而不是读遍整个仓库。

### 条件式架构对比

第二实现只阅读 [llm-d KV Cache Indexer](https://github.com/llm-d/llm-d-kv-cache) 的一个差异：vLLM KV events 怎样维护近实时 block locality，以及 locality scorer 怎样向 scheduler 输出每个 Endpoint 的命中分数。

对比需要回答：

- request-history 推断和事件驱动精确索引分别需要什么状态；
- event loss、reorder、duplicate、restart 和 lag 怎样造成 false-locality；
- locality score 为什么仍需与 load-aware score 组合；
- 精确索引的维护成本在什么 workload 下不值得。

不精读完整 llm-d/Kubernetes 栈。[Gateway API Inference Extension 的 InferencePool](https://gateway-api-inference-extension.sigs.k8s.io/api-types/inferencepool/) 只用于理解 Endpoint Picker 和平台资源接口的边界。

## 手写 L2 契约

### 最小核心代码

从空文件实现一个 Python 单进程核心函数：

```python
choose_endpoint(request, endpoints) -> RoutingDecision
```

最小数据对象：

- `RequestContext`：request ID、model/revision、prefix/locality key、tenant 和 deadline；
- `EndpointState`：Endpoint ID、model/revision、health、draining、observed time/epoch、queue/load、KV locality 和 capacity；
- `RoutingDecision`：候选集、过滤原因、score breakdown、最终 Endpoint 或 reject/fallback。

核心逻辑只包含：

1. model/revision/parallel compatibility 过滤；
2. unhealthy、not-ready 和 draining 过滤；
3. state freshness/epoch 检查；
4. cache locality 与 queue/load 的可解释综合评分；
5. overload 或无合法 Endpoint 时 fail closed；
6. 输出每个候选的过滤理由、分数构成和最终选择。

实现控制在约 100-150 行，30-45 分钟内完成。它是面试可讲清的核心大意代码，不是生产 Router。

### 五个表驱动测试

1. 高 locality 与短 queue 冲突时，按冻结的评分规则选择；
2. locality/Endpoint 状态过期后不能继续作为精确事实使用；
3. unhealthy 或 draining Endpoint 被硬过滤；
4. 全部 Endpoint 过载时 fail closed；
5. 没有 model/revision 兼容实例时拒绝请求。

如果面试只要求伪代码，可以先写数据结构、不变量和控制流；复习验收仍要求五个本地测试通过，防止代码只在正常路径成立。

### 不要求手写

- HTTP proxy、流式转发和连接池；
- 服务发现、分布式状态存储和事件 index；
- retry/circuit breaker 完整状态机；
- autoscaler、Kubernetes controller 或 Ray scheduler；
- 生产认证、限流、配额和多租户控制面；
- learned routing 或预测模型。

## 实验 L0 契约

本节点不要求独立 trace simulator、workload replay、多实例 vLLM 实验或 Router 性能 benchmark。

- 源码项目自带 example 可以运行，用于定位调用链，但不阻塞节点完成；
- mock Endpoint 只能辅助验证控制流，标记为 `simulated`；
- 五个表驱动测试属于手写正确性验收，不提升实验等级；
- 没有固定真实 workload、Endpoint 和测量产物时，不声称 TTFT、TPOT、hit rate 或 Goodput 改善；
- 如果未来 JD 明确要求 Router/平台性能工程，再单独提升实验等级，不提前占用当前复习时间。

## 与 ToolGap-KV 的边界

本节点可以复用 ToolGap-KV 中 lifecycle epoch、freshness、compatibility、DecisionTrace、fail-closed 和 stale completion 防护的思想，也可以理解未来 retain/offload/recompute 怎样向 Router 暴露 locality/capacity 信号。

但当前能力状态必须保持：

- ToolGap-KV CT1-CT3 是单引擎生命周期系统；
- router/control plane 仍是 `roadmap`；
- 手写核心 Router 只能标记为 `simulated` 学习产物；
- 阅读 vLLM Router 或 llm-d 不能标记为 ToolGap-KV `shipped`；
- 不把 Topic 10 变成 ToolGap-KV 的新功能或 CT1-CT3 完成要求；
- 只有真实多实例接口、集成测试和实验产物存在后，才能提升对应声明。

## 明确不要求

- trace-driven simulator 和多策略 workload replay；
- 两个以上真实 vLLM 实例及 TTFT/TPOT/Goodput 对照；
- Kubernetes controller、scheduler 或 autoscaler 实现；
- Ray Serve 内部调度源码；
- etcd、Raft、leader election 和分布式一致性实现；
- Envoy/HTTP proxy 数据面；
- 生产级认证、计费、服务发现和跨地域容灾；
- learned router、强化学习或复杂预测模型；
- 大规模多集群 benchmark；
- 把源码阅读、example 或表驱动测试包装成 ToolGap-KV 已交付平台能力。

## 面试连续追问

- Router、engine scheduler 和 control plane 分别拥有什么状态与决策权？
- Round-robin、Power-of-Two、consistent hashing 和 cache-aware routing 各自依赖什么状态？
- 为什么 cache locality 最高的 Endpoint 不一定应该被选中？
- eligibility filter 为什么必须先于 score ranking？
- request-history inferred locality 与 KVEvents 精确索引怎样权衡？
- locality event 延迟 500 ms 时应怎样降级？
- liveness、readiness、overloaded 和 draining 有什么区别？
- 所有 Endpoint 都过载时，为什么不能继续选队列最短的一个？
- retry 在流式生成已经输出部分 token 后为什么危险？
- circuit breaker 的 open 与 half-open 状态分别解决什么？
- cache hit rate 提高为什么可能没有改善 TTFT 或 Goodput？
- autoscaling 为什么不能只看 GPU utilization？
- 模型加载和 KV warming 怎样影响 autoscaling 控制周期？
- vLLM Router 在哪里建立 Endpoint 状态、执行策略并处理 retry？
- llm-d 精确 locality index 怎样受到 event loss、reorder 和 restart 的影响？
- Kubernetes InferencePool 与 Endpoint Picker 的边界是什么？
- ToolGap-KV 为什么当前不能声称拥有 router/control-plane 能力？

## 完成证据

- 一次通过的 15 分钟 P0 场景题；
- 一张固定版本 vLLM Router 请求链路和失败路径图；
- 一份源码笔记，能够回答主源码路径的十类问题；
- 一份 request-history 与 llm-d KVEvents/index 的架构差异说明；
- 一份 30-45 分钟完成的 `choose_endpoint` 核心实现；
- 五个表驱动测试全部通过；
- 一份平台场景说明，覆盖 health、draining、retry、backpressure、autoscaling lag 和多租户边界；
- 明确记录实验维度为 L0，不用 mock、example 或纸面指标冒充真实性能证据；
- 所有 ToolGap-KV 关联表述保持 `roadmap`、`shipped`、`experimentally validated`、`simulated` 的证据边界。
