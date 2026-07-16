# 13｜C++ 系统编程防守详细知识列表

> 优先级：P1；资源所有权、对象生命周期和基础同步属于面试启动前的 P0 防守要求
>
> 当前状态：已有算法题、WebServer 小项目和基础知识经历；长期未使用，待恢复与限时验收
>
> 目标熟练度：原理 L2 / 源码 L0 / 手写 L2 / 实验 L0
>
> 建议投入：10-15 小时
>
> 关联：[并发、异步与状态机](11-concurrency-async-state-machines.md)
>
> 返回：[AI Infra 面试就绪知识地图索引](../AI_INFRA_INTERVIEW_READINESS.md)

## 能力结果

完成后应能恢复 C++ 系统编程的面试表达与小型实现能力：从对象生命周期和资源所有权解释 RAII、智能指针、拷贝/移动、容器失效和同步；在 Serving 场景中识别 buffer 提前释放、异步完成、数据竞争和关闭清理问题；限时完成一个 move-only RAII wrapper 和一个可关闭的 `BlockingQueue<T>`。

本主题不是从零学习 C++，也不建立新的 C++ 项目。算法题继续使用 C++，但 LeetCode 训练与本主题的非算法系统手写分别验收。

## 当前基础与恢复原则

已有基础：

- 使用 C++ 完成算法题；
- 写过 WebServer 等小型项目；
- 准备过 `malloc/free`、智能指针、虚函数等基础知识。

恢复原则：

- 先通过连续追问定位遗忘点，不按教程顺序重学全部语言；
- 只恢复与资源所有权、并发正确性和系统代码阅读相关的语义；
- 通过两项小型手写证明能力恢复，不重写 WebServer、线程池或内存池；
- 不因为 C++ 出现在推理框架底层，就把路线扩张到 CUDA/operator 或编译器岗位。

## 面试启动前的 P0 防守子集

### 对象生命周期与资源所有权

- 自动、静态、线程和动态存储期的基本区别；
- 构造、析构、作用域退出、异常展开与 RAII；
- `new/delete` 会建立和结束对象生命周期，`malloc/free` 只管理原始存储；
- `new[]/delete[]`、placement new 和释放方式匹配的边界；
- 裸指针、引用、observer 与 owner 的语义区别；
- `unique_ptr` 的独占所有权、移动与自定义 deleter；
- `shared_ptr` 的控制块、引用计数和线程安全边界；
- `weak_ptr` 打破循环引用，以及 `lock()` 的失败语义；
- fd、socket、heap buffer、锁和线程句柄如何通过 RAII 管理；
- double free、use-after-free、泄漏和悬空引用的典型形成路径。

通过标准：能够为一个异步 buffer 处理场景明确 owner、borrower、转移点和最终释放者，而不是只说“使用智能指针”。

### 拷贝、移动与异常安全

- lvalue/rvalue、引用折叠不作为主线，但要能解释移动发生的基本条件；
- 拷贝构造/赋值与移动构造/赋值的职责；
- Rule of Zero、Rule of Five 和资源类为什么通常禁止拷贝；
- moved-from 对象必须保持可析构、可赋值的有效但未指定状态；
- self-assignment、先获取后释放和 copy-and-swap 的正确性直觉；
- `std::move` 只是转换，不保证一定发生移动；
- `noexcept` 如何影响容器扩容时选择移动还是拷贝；
- basic/strong/no-throw exception guarantee 只要求建立边界，不要求系统证明。

### 多态、对象布局与类型边界

- 静态分派与动态分派；
- 虚函数、vptr/vtable 的典型实现模型和一次间接调用成本；
- 基类析构函数为什么在多态删除场景中需要是 virtual；
- object slicing、override 与 overload 的区别；
- `static_cast`、`dynamic_cast`、`reinterpret_cast` 的风险边界；
- 不依赖特定 ABI 声称对象布局的绝对细节。

### STL、内存布局与失效规则

- `vector`、`deque`、`list`、`map`、`unordered_map` 的主要布局和复杂度；
- 连续内存、pointer chasing、缓存局部性与系统性能的关系；
- `vector` 扩容导致 iterator/reference/pointer 失效；
- erase、rehash、insert 等操作的典型失效边界，并以容器契约为准；
- `reserve` 与 `resize` 的区别；
- `emplace_back` 不自动保证比 `push_back` 更快或更正确；
- 哈希表负载因子、rehash 和最坏复杂度的防守解释。

### mutex、condition variable 与 atomic

- data race 与普通的业务竞态不是同一概念；
- mutex 保护共享不变量，而不只是“保护一行代码”；
- `lock_guard`、`unique_lock` 的职责区别；
- condition variable 必须配合共享谓词和 mutex；
- wait 应使用循环或谓词版本处理虚假唤醒；
- notify 不保存事件，状态必须由共享谓词表达；
- atomic 保证某个对象的原子操作，不自动维护跨对象不变量；
- 基本 happens-before、可见性、`seq_cst` 与 acquire/release 直觉；
- 不要求推导复杂 memory order 或实现无锁结构。

通过标准：能够解释为什么 `if (queue.empty()) cv.wait(lock)` 错误，以及为什么只把计数器改成 atomic 不能让整个队列线程安全。

### 关闭、取消与清理

- producer/consumer 的正常关闭语义；
- close 后是否允许 drain 已入队元素必须明确；
- 等待线程必须能被关闭或取消事件唤醒；
- 析构前需要证明没有线程仍访问对象；
- join、detach 和线程所有权的风险；
- 异步 completion 晚到时不得访问已析构状态；
- C++ 同步原语只负责表达机制，生命周期 epoch/fencing 等系统语义仍见 Topic 11。

### 编译与链接宏观链路

- 预处理、编译、汇编和链接的职责；
- declaration、definition、translation unit 与 ODR 的基本含义；
- header guard/`#pragma once`、inline 和模板定义通常放在头文件的原因；
- 静态库与动态库的加载和符号解析直觉；
- 编译错误、链接错误和运行期动态库错误的区分；
- 不要求深入 ABI、name mangling 规则、linker script 或复杂 CMake 工程。

## P1 补充防守

- allocator、free list 和碎片的高层原理，只用于解释 `malloc/free` 与容器分配成本；
- false sharing 和 cache line 的基本直觉；
- `shared_ptr` 原子引用计数不等于 pointee 线程安全；
- `std::span`、`string_view` 等非 owning view 的生命周期风险；
- 动态库全局变量、进程地址空间和内存映射的宏观边界；
- C API 与 C++ RAII wrapper 的接口封装思路。

这些内容只要求讲清原理。没有具体 JD 或真题时，不继续深入 allocator、ABI 或 lock-free 源码。

## 两项系统手写契约

### A. Move-only RAII 资源封装

实现一个 fd 或 heap buffer wrapper，接口可按题目调整，但必须满足：

- 默认状态不拥有资源；
- 构造后拥有且只拥有一个资源；
- 析构时只释放一次；
- 删除拷贝构造和拷贝赋值；
- 移动构造与移动赋值转移所有权，并把源对象置为无资源状态；
- 移动赋值先正确释放当前资源，再接管新资源；
- 提供 `get()`、`release()`、`reset()` 中与题目相关的最小接口；
- self move-assignment 不产生泄漏或 double free。

时间限制：20-30 分钟。

最低测试：

1. 默认构造不释放无效资源；
2. 正常析构只释放一次；
3. 移动构造转移所有权；
4. 移动赋值释放旧资源并接管新资源；
5. `release/reset` 语义正确；
6. 容器或异常路径下无重复释放。

### B. 可关闭的 `BlockingQueue<T>`

固定面试接口：

```cpp
template <class T>
class BlockingQueue {
 public:
  explicit BlockingQueue(std::size_t capacity);
  bool push(T value);
  std::optional<T> pop();
  void close();
};
```

固定语义：

- `capacity > 0`，队列满时 `push` 等待；
- `close()` 幂等，并唤醒所有 producer/consumer；
- close 后禁止新 push，等待中的 push 返回 `false`；
- close 后 consumer 继续 drain 已有元素；
- close 且队列为空时，`pop()` 返回 `std::nullopt`；
- 所有共享状态都在同一互斥保护下维护；
- wait 使用谓词，同时检查容量/数据与 closed 状态；
- 不要求 timeout、优先级、公平队列或 lock-free。

时间限制：45-60 分钟。

最低确定性测试：

1. 单线程 push/pop 保持 FIFO；
2. 空队列 consumer 被后续 push 唤醒；
3. 满队列 producer 被后续 pop 唤醒；
4. close 唤醒空队列上的 consumer；
5. close 唤醒满队列上的 producer，并拒绝写入；
6. close 后 drain 现有元素，再返回 `nullopt`；
7. 多等待者最终都退出；
8. 重复 close 不破坏终态。

## 原理连续追问

### 资源与对象

- `malloc/free` 与 `new/delete` 的核心差异是什么？为什么不能随意混用？
- RAII 为什么能覆盖普通 return 和异常路径？它不能自动解决哪些共享所有权问题？
- `unique_ptr` 和 `shared_ptr` 应如何选择？为什么不应默认全部使用 `shared_ptr`？
- `shared_ptr` 的引用计数线程安全是否意味着对象本身线程安全？
- `weak_ptr` 如何解决循环引用？`lock()` 为什么可能失败？
- `std::move` 为什么可能仍然触发拷贝？
- 为什么多态基类析构函数通常需要是 virtual？

### 容器与性能

- `vector` 扩容时发生什么？哪些 iterator/reference 会失效？
- 为什么 `vector` 常常比 `list` 更快，即使中间插入的理论复杂度更差？
- `reserve` 与 `resize` 的语义区别是什么？
- `unordered_map` 为什么不能保证严格 O(1)？rehash 会影响什么？

### 并发与 Serving

- condition variable 为什么必须检查谓词？notify 为什么不是可靠的事件缓存？
- mutex、atomic 和 condition variable 分别解决什么问题？
- 一个异步 GPU/IO 操作仍在读取 buffer 时，调用方如何保证 buffer 不被提前释放或复用？
- `BlockingQueue` close 时怎样保证所有等待者退出，同时不丢弃已入队任务？
- 为什么对象析构和异步 completion 之间可能发生 use-after-free？应该由谁持有生命周期？
- 为什么只把队列索引改成 atomic 不能得到一个正确的无锁队列？

## 明确不要求

- 重写 WebServer、线程池、内存池或网络框架；
- 手写 `shared_ptr`、`malloc`、STL 容器或生产级 allocator；
- 模板元编程、复杂 ABI、编译器实现和完整 CMake 工程体系；
- lock-free、ABA、hazard pointer、RCU 等高级并发回收；
- CUDA/C++ kernel、PyTorch dispatcher 或推理框架 C++ 内核源码深挖；
- 独立性能 benchmark 或新的 C++ 项目；
- 用 C++ 重写 Transformer、KV Cache 或调度器领域手写。

## 与其他知识及项目的边界

- [并发、异步与状态机](11-concurrency-async-state-machines.md) 负责跨语言并发语义、Python `asyncio` 和 Serving 生命周期状态机；本主题只恢复 C++ 的资源与同步表达能力；
- LeetCode 继续使用 C++，但算法正确率、题型覆盖和刷题计划另行管理；
- ToolGap-KV 项目答辩树独立维护在 `docs/agent-kv/INTERVIEW_MAP.md`，不并入本知识地图；
- 本主题练习与答题记录不能标记为 ToolGap-KV 的 `shipped` 或 `experimentally validated` 证据。

## 完成证据

- 一次 20-30 分钟语言与资源所有权连续追问记录；
- 一次 20-30 分钟 move-only RAII wrapper 限时手写及测试；
- 一次 45-60 分钟 `BlockingQueue<T>` 限时手写及八项测试；
- 一份错题/遗忘点修正记录；
- 能把 buffer 生命周期、异步完成、关闭和数据竞争连接到 Serving 场景；
- 回答没有扩张成候选人拥有 CUDA/kernel、allocator 或生产 C++ runtime 经验。
