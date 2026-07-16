# 09｜分布式 Serving 数据路径与 PD 分离详细知识列表

> 优先级：P1；包含面试启动前必须完成的 P0 防守子集
>
> 当前状态：已敲定数据路径主线和非传输内核边界，原理、源码、手写与实验均待完成
>
> 目标熟练度：原理 L3 / 源码 L2 / 手写 L2 / 实验 L2
>
> 依赖：[KV Cache 与内存系统](03-kv-cache-memory-system.md)、[LLM 推理引擎与调度](04-llm-engine-scheduling.md)、[性能分析与实验方法](05-performance-analysis-and-gpu-literacy.md)、[多 GPU 模型执行与集合通信](08-multi-gpu-model-execution-and-collectives.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能沿以下链路解释一次请求，并同时画出数据流、状态流、资源所有权和指标流：

```text
请求进入
  -> Prefill 实例排队和执行
  -> 产生 KV Cache
  -> 建立 KV 身份与目标位置
  -> 传输或发布 KV
  -> Decode 等待可见性完成
  -> 验证兼容性并接管
  -> 逐 token Decode
  -> 失败回退与资源清理
```

回答不能只画一条 Prefill Worker 到 Decode Worker 的传输箭头。必须解释谁拥有请求、谁拥有物理 KV、谁判断数据可读、Decode 在什么条件下准入，以及失败、取消或晚到完成时怎样保持状态一致。

这是一个约 12-18 小时的 P1 节点。它回答“请求、KV Cache 和执行阶段怎样跨 Prefill/Decode 实例移动”；后续控制面节点回答“请求应该选择哪个实例，以及整个集群怎样治理”。

## P0 防守要求

开始目标岗位面试前，应能脱稿回答以下问题：

1. Prefill 与 Decode 在计算形态、显存访问、batch 方式和延迟目标上的差异；
2. 混部时，长 Prefill 为什么可能干扰已经运行的 Decode；
3. PD 分离解决的是资源隔离和独立扩缩容，为什么不等于天然提升总吞吐；
4. TTFT 如何拆成路由、排队、Prefill、KV transfer 和 Decode admission；
5. TPOT/ITL 为什么主要受 Decode 资源池、batch 和调度影响；
6. KV transfer 成本如何与重新 Prefill 的成本比较；
7. KV 描述符至少需要哪些身份、范围、布局和兼容性信息；
8. 为什么 `transfer submitted`、`transfer complete` 与 `Decode visible` 是不同状态；
9. 部分传输、超时、Prefill/Decode Worker 失败、取消和晚到 completion 怎样处理；
10. Prefill/Decode 资源比例失衡为什么会形成新的串联排队瓶颈；
11. direct transfer、共享 KV 存储和中间传输服务各自增加哪些成本与故障面；
12. 哪些 workload 更可能获益，短请求或低负载为什么可能退化。

P0 验收是一道 15 分钟连续场景题：设计两组 Prefill Worker、四组 Decode Worker 的在线服务。回答必须覆盖请求流、KV 交接、Decode 准入、资源所有权、失败回退、指标，以及关闭 PD 的条件；还要说明如何证明 TTFT 改善没有牺牲 TPOT、吞吐、goodput 或错误率。

P0 不要求解释 RDMA、NIXL 或 GPU Direct 的底层实现。

## P1 详细知识列表

### 为什么分离 Prefill 与 Decode

- Prefill 对完整 Prompt 做并行计算，Decode 逐步生成 token，两者的计算粒度和访存行为不同；
- Prefill 更容易形成大矩阵计算，Decode 的每步计算更小并反复读取权重与 KV；
- 两者共用 GPU 时会竞争算力、带宽、显存容量、执行队列和 scheduler budget；
- 分离后可以独立配置并扩缩 Prefill/Decode 资源池，并隔离部分尾延迟干扰；
- 分离同时增加路由、排队、KV transfer、同步、目标容量预留和新故障面；
- PD 分离、Tensor/Pipeline Parallel 与 Chunked Prefill 解决的问题不同，可以组合但不能互相替代；
- 判断收益时必须分别讨论 TTFT、TPOT/ITL、E2E latency、吞吐、goodput、成本和错误率；
- “资源隔离更强”“模型或并发终于放得下”和“相同资源下性能更高”是三种不同结论。

### KV 怎样移动

- Prefill Worker 需要描述模型、请求、token/位置范围、layer/block、KV dtype/layout 和并行配置；
- push 模式由来源主动发送，pull 模式由目标拉取，共享存储模式由双方通过共同位置发布与读取；
- direct GPU path、host staging 和远端 KV 存储具有不同的拷贝次数、带宽、固定延迟和故障边界；
- block、layer 或更大批次粒度会改变调度复杂度、内存峰值、流水化机会和失败恢复范围；
- transfer 成本可用固定开销、payload 字节、可用带宽、并发竞争和排队时间建立近似模型；
- 传输与 Decode 是否能够重叠，取决于依赖范围、数据可见性、buffer 生命周期和实现支持；
- 目标 KV 容量、传输队列和链路压力需要形成 backpressure，不能无限接收 handoff；
- GPU Direct、RDMA 和 NIXL 只要求理解接口位置、数据路径和 trade-off，不要求实现传输库或 kernel。

### KV 怎样安全接管

- request/session/turn/lifecycle epoch 用于区分同名请求、重试与旧异步事件；
- 模型 revision、tokenizer/template、RoPE、KV dtype/layout 和 TP 配置属于兼容性契约；
- `PREFILLING`、`TRANSFER_PENDING`、`TRANSFERRING`、`READY`、`CONSUMED`、`FAILED`、`CANCELLED` 表示不同逻辑事实；
- 提交传输不代表完成，传输完成也不必然代表 Decode 已经看到完整且兼容的数据；
- completion 需要幂等；旧 epoch、重复、部分完成和取消后的晚到事件不能重新激活请求；
- Decode admission 必须等待身份、兼容性、完整性、可见性和目标容量条件同时满足；
- retry、reroute、retransfer 与 recompute 的选择取决于剩余数据、排队、源/目标健康和重新 Prefill 成本；
- 请求逻辑所有权、handoff record 所有权和物理 KV block 所有权不是同一个概念；
- terminal state 之后必须清理临时容量、句柄、等待者和陈旧记录；
- 同一份 KV 在共享语义未明确允许时不能被两个 Decode owner 非法接管。

### 串联队列与 Decode admission

- 请求会依次经过 Prefill queue、transfer queue 和 Decode queue，任何一段都可能主导尾延迟；
- Prefill/Decode pool 的配比需要考虑 Prompt 长度、输出长度、并发和设备差异；
- Decode admission 既要等待 KV ready，也要确认目标能够持续承担后续 token 生成；
- 只看平均利用率可能掩盖某一池的长队列和另一池的空闲；
- 静态配比实现简单但难适应 workload 漂移，动态配比增加反馈延迟、迁移和稳定性问题；
- backpressure、overload rejection 和 recompute fallback 会直接改变尾延迟和 goodput；
- 本节点定义路由可消费的 readiness、容量、队列和失败信号，但不实现全局实例选择策略。

### 怎样证明收益

- 将 TTFT 分解为入口路由、各阶段排队、Prefill、KV transfer 和 Decode admission；
- 同时记录 TPOT/ITL、E2E latency、request/token throughput 和 goodput；
- 使用 p50/p95/p99、错误率、timeout、retry 和 fallback 率观察尾部与正确性；
- 记录 Prefill/Decode utilization、队列长度、KV bytes、transfer 时间和有效带宽；
- co-located 与 disaggregated 对照必须固定总 GPU 数、模型副本预算和 workload；
- Prompt/Output 长度、并发、资源配比和拓扑都是实验变量，不能一次全部改变；
- 至少保留一个获益案例和一个退化案例，并解释关闭 PD 的运行条件；
- 一张 GPU 的 co-located 与两张 GPU 的 PD 只能作为容量或非等资源展示，不能直接声称 PD speedup。

## 源码 L2 契约

### 触发依据

PD 分离是目标岗位常见的分布式推理机制，面试会继续追问 KV connector、Decode admission、失败处理和指标权衡。它同时满足真题/场景题价值与核心 Serving 模块门槛，因此必须建立固定实现的源码路径和真实框架运行证据。

### 主实现与阅读路径

主实现选择学习开始时固定 release/commit 的 vLLM，沿一条完整数据路径阅读：

```text
PD 配置与角色初始化
  -> 请求进入 Prefill 实例
  -> Prefill 调度与模型执行
  -> KV connector / transfer metadata
  -> KV 保存或发送
  -> Decode 实例等待和加载
  -> KV ready 后进入 Decode
  -> completion / failure / cleanup
```

读完必须回答：

- Prefill 与 Decode 角色在哪里确定；
- transfer metadata 由谁创建并包含什么；
- scheduler 如何知道 KV 尚未 ready；
- connector、Block Manager、scheduler 和 model runner 的职责边界；
- completion 怎样进入控制流并改变 Decode admission；
- transfer 失败怎样阻塞、重试、回退或终止请求；
- 本地 KV block identity 怎样映射到跨实例交接；
- 哪些能力由 vLLM 提供，哪些由 connector 或外部传输系统提供；
- 取消或超时后，怎样阻止晚到 completion 泄漏资源或恢复旧请求。

源码笔记必须保存项目、release/commit、入口、关键对象、状态流、失败路径、已知版本差异和一张时序图。第二实现只从 SGLang、Dynamo、Mooncake 等选择一个，用于回答一个明确的架构差异；没有具体 JD 或 trade-off 问题时不增加第二套源码。

## 手写 L2 契约

### 最小逻辑系统

从空文件实现一个不搬运真实 KV Tensor 的逻辑交接系统：

- `KVIdentity`：模型、token/位置范围、KV dtype/layout 和并行配置；
- `HandoffRecord`：request、epoch、来源、目标、状态和资源句柄；
- `HandoffController`：合法状态转换、Decode admission、取消、fallback 和清理；
- `FakeTransfer`：只模拟延迟、成功、失败和 completion，不实现网络。

状态主路径为：

```text
PREFILLING
  -> TRANSFER_PENDING
  -> TRANSFERRING
  -> READY
  -> CONSUMED

任意非终态
  -> FAILED / CANCELLED
  -> RECOMPUTE_FALLBACK 或 CLEANED
```

必须通过以下测试：

1. 正常 Prefill-transfer-Decode 链路；
2. KV 未 `READY` 时拒绝 Decode；
3. 重复 completion 保持幂等；
4. 旧 epoch completion 被拒绝；
5. metadata 不兼容时触发 recompute；
6. cancel 后晚到 completion 不能重新激活请求；
7. 失败后临时容量和句柄被清理；
8. 同一个 KV 不能被两个 Decode owner 非法接管。

时间限制：45-60 分钟完成正常链路和基本状态机，再用 30-45 分钟补故障测试。通过标准是能够解释每个状态、所有者和不变量，而不是只写一个异步回调 demo。

不要求手写 RPC、多进程、共享内存、RDMA、NIXL、真实 GPU buffer、生产 connector 或传输引擎。

## 实验 L2 契约

### 逻辑正确性实验

使用可控 `FakeTransfer` 注入延迟、失败、重复完成、晚到完成和取消竞争，输出完整事件 trace。该结果只能标记为 `simulated`，不得用于证明真实 KV 传输性能、vLLM 集成或 ToolGap-KV 已交付能力。

### 真实框架实验

在固定版本 vLLM 上运行 co-located 与 disaggregated 对照，记录：

- 模型 revision、dtype 和框架 commit；
- GPU、互连、网络和软件环境；
- Prefill/Decode 实例数和每实例并行配置；
- Prompt/Output 长度、并发、请求数和测量窗口；
- TTFT 分解、TPOT/ITL 和 E2E latency；
- request/token throughput、goodput 和 p50/p95；
- KV transfer bytes、时间、失败与 fallback；
- Prefill/Decode utilization 和各阶段队列时间。

实验矩阵保持有界：一个长 Prompt 场景、一个短 Prompt 或低负载场景、一个中高并发场景。至少保留一个 PD 获益案例和一个退化案例。

对照必须优先使用相同总 GPU 数、相同模型副本预算和相同 workload。如果 co-located 使用一张 GPU、PD 使用两张 GPU，差异只能标记为容量展示或非等资源比较，不能计算误导性 speedup。没有双 GPU 或可运行 connector 环境时，保留命令、配置、预期指标和待验证假设，实验维度继续标记为待完成。

## 与后续控制面节点的边界

本节点回答“请求与 KV 怎样跨 Prefill/Decode 实例安全移动”。后续“Serving 路由与平台控制面”回答：

- 请求应该选择哪个 Prefill/Decode 实例；
- cache locality 与 load balance 怎样权衡；
- admission、backpressure、health check、retry 和 stale state 怎样在集群层治理；
- 弹性、资源编排、多租户、配额和 SLO 怎样落地；
- Ray、Kubernetes 或其他平台接口需要掌握到什么深度。

本节点只输出可供控制面消费的 readiness、容量、队列、transfer 和失败信号，不实现上述策略。

## 与 ToolGap-KV 的边界

本节点可以复用 ToolGap-KV 中 lifecycle epoch、异步 completion fencing、兼容性检查、取消、fallback、cleanup 和 DecisionTrace 的思想，但两者不是同一个已交付系统：

- ToolGap-KV CT1-CT3 关注单引擎内 retain/offload/recompute 生命周期；
- 本节点练习关注 Prefill 与 Decode 实例之间的 KV 交接；
- toy handoff 只能标记为 `simulated`；
- 阅读 vLLM PD 源码不能标记为 ToolGap-KV `shipped`；
- 只有项目真实拥有跨实例协议、集成测试和实验产物时，才能提升对应声明；
- 不因概念相似就把 ToolGap-KV 主线扩大成分布式 KV 系统；
- 同一份学习产物不能在 ToolGap-KV 和本节点中重复计算完成度。

## 明确不要求

- 实现 RDMA、NIXL、NCCL 或传输 kernel；
- 精读 Mooncake、LMCache 等存储或传输引擎的内部实现；
- 实现 Kubernetes/Ray 调度器、自动扩缩容或多租户平台；
- 实现全局负载均衡、cache-aware routing 或集群准入控制；
- 构建多节点容灾系统或大规模 benchmark 矩阵；
- 把源码阅读、toy 状态机、fake transfer 或非等资源实验包装成项目已交付能力。

## 面试连续追问

- Prefill 和 Decode 为什么适合使用不同的资源池？
- PD 分离为什么可能改善 TTFT，却同时让短请求变慢？
- KV transfer 与重新 Prefill 的成本分界怎样估算？
- `transfer complete` 为什么不等于 Decode 可以直接开始？
- KV metadata 里缺少模型 revision、epoch 或 TP layout 会发生什么？
- Decode 在 admission 前必须验证哪些条件？
- Prefill 成功但 Decode Worker 失败时，应该重传、换实例还是重新 Prefill？
- cancel 与 completion 并发时怎样防止请求复活和资源泄漏？
- Prefill pool 与 Decode pool 比例失衡分别会出现什么队列症状？
- push、pull、共享存储三种模式的所有权和故障面有什么不同？
- 怎样证明 TTFT 改善不是因为 PD 实验多用了一张 GPU？
- 哪些指标能够区分 Prefill、transfer 和 Decode admission 瓶颈？
- 为什么平均 GPU utilization 不能证明 PD 资源配比合理？
- vLLM 中 scheduler、connector、Block Manager 和 model runner 分别负责什么？
- ToolGap-KV 为什么当前不能声称支持跨实例 PD handoff？

## 完成证据

- 一次通过的 P0 场景题，完整覆盖请求、KV、状态、所有权和指标流；
- 一张固定版本 vLLM PD 数据路径与失败路径时序图；
- 一份限时 `KVIdentity`、`HandoffRecord`、`HandoffController`、`FakeTransfer` 实现及八类测试；
- 一份 fake-transfer 故障注入 trace，并明确标记为 `simulated`；
- 有等资源双 GPU 条件时，完成 co-located/PD 三类 workload 对照并保留一个获益和一个退化案例；
- 没有真实环境时保留实验缺口，不把模拟结果外推为框架集成或性能结论；
- 一份开启或关闭 PD 的决策说明，能够根据 workload、队列、transfer 成本和 SLO 给出边界；
- 所有 ToolGap-KV 关联表述保持 `roadmap`、`shipped`、`experimentally validated`、`simulated` 的证据边界。
