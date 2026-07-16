# 11｜并发、异步与状态机详细知识列表

> 优先级：P0
>
> 当前状态：已敲定范围与手写契约，原理复习、源码 trace 与闭卷手写待完成
>
> 目标熟练度：原理 L3 / 源码 L1 / 手写 L3 / 实验 L0
>
> 预计投入：集中学习约 10-14 小时，实际完成以验收证据为准
>
> 支持：[KV Cache 与内存系统](03-kv-cache-memory-system.md)、[LLM 推理引擎与调度](04-llm-engine-scheduling.md)、[分布式 Serving 数据路径与 PD 分离](09-disaggregated-serving-data-path-and-pd.md)、[Serving 路由与平台控制面](10-serving-routing-and-control-plane.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能从以下五层解释一次异步操作：

```text
执行单元：process / thread / coroutine
                    ↓
调度与等待：preemption / cooperative yield / I/O readiness
                    ↓
同步与容量：lock / condition / queue / semaphore / backpressure
                    ↓
生命周期：queued / running / terminal / timeout / cancellation
                    ↓
正确性：identity / epoch / idempotence / fencing / cleanup
```

回答不能停留在“协程比线程轻量”或“`await` 不阻塞”。必须说明：

- 谁被挂起，event-loop thread 是否仍能运行其他 Task；
- 被等待对象在哪里登记恢复条件；
- timeout 后底层工作是否仍可能继续；
- cancel、timeout、failure 与 success 竞争时谁冻结对外终态；
- late completion 怎样被 fencing；
- 队列、worker slot、Future、Task 和领域资源怎样最终清理。

本节点的实现切片固定为 Python `asyncio`。Go 并发已经在既有学习中覆盖，不纳入秋招知识地图、完成门槛或详情展开；只有目标 JD 明确要求时才临时补充。

## 与领域节点的责任边界

本节点提供通用并发语义和 Python 控制流，不替代领域状态机：

1. Topic 03 负责 KV 生命周期、物理资源所有权、restore/fallback 和 block cleanup；
2. Topic 04 负责请求队列、token/KV budget、Continuous Batching 和抢占恢复；
3. Topic 09 负责跨实例 KV handoff、readiness 和 Decode admission；
4. Topic 10 负责集群级 admission、Endpoint selection、retry 和全局背压；
5. 本节点负责这些系统共同依赖的等待、取消、容量限制、终态竞争、幂等和 fencing。

例如，本节点要解释 epoch 为什么能拒绝旧 completion；Topic 03 仍需解释旧 restore completion 对 block ownership、visibility 和 cleanup 的具体影响。拒绝旧结果与释放旧操作占有的资源是两个独立问题。

## 原理 L3 详细知识列表

### 并发执行模型

- concurrency 与 parallelism 的区别；
- process、thread、coroutine 的隔离、共享、创建和切换成本；
- 抢占式线程调度与协作式协程让出；
- CPU-bound 与 I/O-bound 工作负载；
- async、线程池和多进程的选择边界；
- 共享状态与消息传递的正确性和工程 trade-off；
- 并发提高资源利用率，不保证单任务延迟一定下降。

只要求建立服务端心智模型，不深入 Linux CFS、进程地址空间实现或上下文切换汇编。

### 同步原语与正确性

- mutex、read-write lock、semaphore、condition variable、event 和 bounded queue 的职责差异；
- 临界区、不变量、锁粒度和锁顺序；
- race condition、deadlock、livelock、starvation 和 priority inversion；
- producer-consumer、容量上限和背压传播；
- 原子操作与 CAS 的基本语义及适用边界；
- GIL 约束 Python 字节码执行，不等于业务状态天然线程安全；
- check-then-act、read-modify-write 和跨 `await` 不变量为何仍会产生竞态；
- 为什么不应持锁执行不受控 I/O 或长耗时工作。

不要求形式化学习 C++ memory model、lock-free queue、hazard pointer 或 RCU。

### Python `asyncio` 运行机制

- coroutine object、Task、Future 和 event loop 的职责关系；
- 调用 `async def` 与真正调度 coroutine 执行的区别；
- `await` 怎样挂起当前 coroutine，并在被等待对象完成后恢复；
- `await` 是协作式让出点，不等于创建新线程；
- 连续两个 `await`、`create_task` 后再等待和批量并发等待的时序差异；
- event loop 等待 I/O readiness、timer 和 callback 的高层机制；
- blocking function 为什么会阻塞 event-loop thread；
- Queue、Lock、Semaphore、Event 与 Future 的基本用途和失败边界；
- timeout、cancellation、exception propagation 与 `finally` cleanup；
- structured concurrency 的目标：约束父子任务生命周期和失败传播，而不是背完整 API 清单。

不要求 CPython bytecode、解释器调度、GIL 源码、生成器演进史或从零实现 event loop。

### 异步失败与状态机

- timeout 表示调用方等待边界，不证明底层工作已经停止；
- cancellation 通常是 cooperative，需要操作到达可取消点并执行清理；
- queued cancellation 与 running cancellation 的资源语义不同；
- cancel、timeout、failure 和 success 竞争时必须冻结一个对外可见终态；
- request/job identity、attempt 和 monotonic epoch 用于区分重试与旧操作；
- late/duplicate completion 不得覆盖终态或重新激活已取消对象；
- 幂等 completion 和 cleanup 防止重复返回、double free 和 permit 泄漏；
- bounded queue 的 block、defer、reject、drop 是不同 admission 契约；
- shutdown 必须明确 stop accepting、drain、cancel 和 force-close 的顺序；
- exactly-once 不能靠状态枚举获得，还涉及持久化、去重与外部副作用边界。

### Serving 场景映射

- 请求取消时 KV restore/offload 仍在进行；
- scheduler 已超时，但后台 completion 随后到达；
- producer 产生任务的速度长期高于 GPU/worker 消费速度；
- semaphore permit、KV block、Future 或后台 Task 泄漏；
- retry attempt 与旧 attempt 同时完成；
- client disconnect 后 engine 请求怎样终止和清理；
- shutdown 时新请求、排队请求和运行请求分别怎样处理；
- 为什么只观察成功路径无法证明并发系统正确。

## 源码 L1 契约

### Python 异步链路

学习开始时固定一个 Python 版本，沿以下概念链完成一次轻量 source trace：

```text
asyncio.run
  -> event loop lifecycle
  -> create_task
  -> Task waits on Future
  -> timer / I/O / callback marks completion
  -> Task becomes runnable again
  -> result / exception / cancellation propagates
```

源码笔记必须记录：

- Python 版本与 commit/tag；
- 公开入口和关键对象；
- Task 与 Future 的等待关系；
- 恢复条件在哪里登记并触发；
- cancellation 怎样注入和传播；
- exception/result 怎样回到调用方；
- event loop 和 Task 在何处清理。

目标是把 `await` 的控制流映射到真实实现，不读遍 selector/proactor、解释器和操作系统内核。

### 真实 Serving 异步请求链

固定一个 vLLM release/commit，定位一条请求取消链：

```text
API request
  -> async generation / request stream
  -> engine request submission
  -> client disconnect or cancellation
  -> request termination
  -> resource and stream cleanup
```

读完必须说明：

- API 入口、async generator、Task/Future 和 request stream 边界；
- 请求 ID 在各层怎样传递；
- 谁检测 client disconnect，谁发起取消；
- termination 怎样进入 engine；
- 输出流、后台 Task 与 engine-side request 的清理方向；
- 哪些路径只取消调用方等待，哪些路径会请求底层终止。

不重复 Topic 04 的完整 `schedule -> execute -> update` 源码阅读，也不把源码笔记描述成 ToolGap-KV 已完成集成。

## 手写 L3 契约

### 有界异步执行器

从空文件实现：

```python
class BoundedAsyncExecutor:
    async def start(self): ...
    async def submit(self, job_id, operation, timeout) -> asyncio.Future: ...
    async def cancel(self, job_id): ...
    async def shutdown(self): ...
```

核心代码约 80-120 行，不含测试，只包含：

- bounded `asyncio.Queue`；
- 固定数量 worker tasks；
- `JobRecord`、job identity/attempt 和明确状态机；
- 每个 job 的对外结果 Future；
- timeout、cancel、exception 与 cleanup；
- late/duplicate completion fencing；
- 冻结的 queue-full 契约：立即抛出 `ExecutorOverloaded`。

`submit` 只负责 admission：成功时入队并返回代表对外结果的 Future；队列已满时立即拒绝，不在调用方积累无限个等待 queue space 的 coroutine。调用方再等待返回的 Future 获取成功、失败、超时或取消结果。

### 状态机与 timeout 语义

只允许以下转换：

```text
QUEUED -> RUNNING -> SUCCEEDED
                  -> FAILED
                  -> TIMED_OUT
                  -> CANCELLED

QUEUED -> CANCELLED
```

所有终态不可再次变化。timeout 到达后：

1. executor 冻结对外状态为 `TIMED_OUT`；
2. executor 请求取消 operation，但不假设它已经停止；
3. worker slot 在 operation 真正退出前保持占用；
4. 若 operation 抑制取消并晚到返回，其结果被丢弃；
5. operation 退出并完成清理后才释放并发槽位。

永久不响应取消的工作需要进程隔离或外部强制终止，不属于本手写题。不能为了“恢复容量”而在底层工作仍运行时提前释放 slot，否则实际并发会突破上限。

### 必须保持的不变量

- 同时运行数量不超过配置上限；
- 队列容量有限，生产长期快于消费时不会无限积压；
- 每个 admitted job 只有一个对外可见终态；
- timeout/cancel 后的 completion 不能覆盖终态；
- operation 异常不能杀死整个 worker loop；
- queue slot、worker、Future 和任务句柄最终被清理；
- duplicate cancel/complete 保持幂等；
- shutdown 后不再接收任务，且不遗留后台 Task。

### 六个确定性测试

优先使用 `Event`、受控 Future 或 barrier 主动控制交错，不用大量 `sleep` 猜测时序：

1. 同时运行数不超过上限；
2. queue full 时立即返回 `ExecutorOverloaded`；
3. queued job 能被取消且不再运行；
4. running job 超时后，晚到 completion 不能改写终态，并且 operation 退出前不提前释放 slot；
5. operation 抛异常后 worker 继续工作且容量许可不泄漏；
6. shutdown 正确处理 queued/running jobs，且没有悬挂任务。

duplicate cancel、terminal immutability 和 cleanup 断言合并进上述测试，不再新增重复测试。

### 时间限制

- 45-60 分钟完成正常链路、状态机和基础错误处理；
- 30-45 分钟补齐确定性故障测试；
- 面试只要求大意代码时，先写状态、不变量和核心控制流；
- 正式复习验收仍要求本地测试通过。

该练习验证通用异步控制能力，不实现网络服务器、线程池、完整 RPC 框架、分布式任务系统或生产级 executor。

## 实验 L0 契约

本节点不要求吞吐 benchmark、event-loop 对比、真实多实例服务或独立故障注入平台：

- 六个测试属于手写正确性验收，不提升实验等级；
- example、mock operation 和受控交错最多是 `simulated` 学习证据；
- 没有固定 workload、运行环境和原始测量产物时，不声称吞吐、延迟或资源利用率改善；
- 若未来 JD 明确要求 Python runtime 或高并发网关性能，再单独提升实验和源码深度。

## 面试连续追问

必须脱稿回答：

1. `await` 做了什么，为什么不等于启动线程；
2. 连续写两个 `await` 为什么可能仍然串行；
3. blocking function 为什么会卡住同一 event loop 上的其他 coroutine；
4. GIL 为什么不能保证业务状态线程安全；
5. timeout 以后底层工作是否一定停止；
6. cancel 与 completion 同时发生时怎样冻结终态；
7. Semaphore 和 bounded Queue 分别限制什么；
8. 无限队列为什么会把过载转化为内存压力和尾延迟；
9. 怎样证明资源只释放一次；
10. epoch 为什么能拒绝旧完成，却不能自动保证资源已清理。

至少完成一道 15 分钟连续场景题：

> 一个异步 KV restore 任务有并发上限和有界队列。请求超时并触发 recompute 后，旧 restore completion 晚到；同时客户端取消，系统准备 shutdown。说明任务、请求、KV 可见性和资源所有者，给出合法状态转换、终态竞争规则、fencing、backpressure 和 cleanup 顺序。

回答必须区分“拒绝旧 completion 影响可见状态”和“回收旧 operation 已占资源”，不能把 epoch 当作自动清理机制。

## 与 ToolGap-KV 的边界

本节点为 ToolGap-KV 的 lifecycle identity/epoch、异步 completion fencing、fallback、cancellation、cleanup 和 DecisionTrace 提供通用基础，但不改变当前能力状态：

- Python/vLLM 源码阅读不是 ToolGap-KV runtime `shipped`；
- `BoundedAsyncExecutor` 是独立学习练习，不自动成为项目实现；
- mock operation、受控 Future 和确定性交错最多是 `simulated`；
- 只有仓库内候选人拥有的生命周期实现、测试与证据存在后，才能提升项目声明；
- 不用本节点替代 CT1-CT3 对真实 runtime ownership 的完成要求。

## 明确不要求

- Go 并发、goroutine、channel、`select`、context、Go scheduler 或 GC；
- Python 完整语法、元类、descriptor、完整 GC 或所有 `asyncio` API；
- CPython bytecode、解释器、GIL 源码或完整 event-loop 内部实现；
- Linux CFS、futex、epoll 内核实现和上下文切换汇编；
- C++ 内存模型形式化细节；
- lock-free queue、hazard pointer、RCU 和无锁内存回收；
- 手写 event loop、线程池、网络服务器或生产 RPC 框架；
- 分布式共识、事务消息或把 exactly-once 当成单机状态机问题；
- 独立性能实验、吞吐优化或生产集成声明。

## 完成证据

只有以下材料齐全，节点才能标记为完成：

- 一份 `async/await` 执行时序说明；
- 有界异步执行器和六个确定性测试；
- 固定 Python 版本的 `asyncio` source trace；
- 固定 vLLM 版本的异步请求 source trace；
- 一次闭卷限时手写记录；
- 一轮口述追问、场景题作答和错误修正记录。

验收顺序建议是：先原理与最小 asyncio 练习，再手写执行器和故障测试，最后做源码 trace 与闭卷复测。源码阅读放在能够运行和修改最小代码之后，避免把“看懂调用链”误当成“能独立处理并发正确性”。
