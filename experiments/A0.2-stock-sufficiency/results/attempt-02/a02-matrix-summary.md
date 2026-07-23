# A0.2 Stock Sufficiency 实验汇总

- 判决：`inconclusive`
- 原因：valid runs did not satisfy a stable registered Stop or Continue condition
- 触发条件：无
- 证据范围：固定 HND、capacity-pressure 代理、Qwen2.5-7B、pinned vLLM；不代表真实 tool-gap wall-clock 负载。
- `transfer_overlap_observable=false`，因此 Stop 3 与 Continue 2 未参与判决。

## Cell 汇总

| L | M band | S0 paths | S1 paths | Δservice (ms) | θ (ms) | material |
|---:|---|---|---|---:|---:|---|
| 2048 | low | `{"gpu_local_hit": 5}` | `{"gpu_local_hit": 5}` | - | 5.000 | False |
| 2048 | target | `{"full_recompute": 5}` | `{"mixed_cpu_restore": 5}` | 407.449 | 5.000 | True |
| 2048 | overload | `{"full_recompute": 5}` | `{"mixed_cpu_restore": 5}` | 411.405 | 5.000 | True |
| 8192 | low | `{"gpu_local_hit": 5}` | `{"gpu_local_hit": 5}` | - | 5.000 | False |
| 8192 | target | `{"partial_gpu_hit": 5}` | `{"mixed_cpu_restore": 5}` | - | 5.000 | False |
| 8192 | overload | `{"full_recompute": 5}` | `{"mixed_cpu_restore": 5}` | 1828.322 | 5.000 | True |
| 16384 | low | `{"gpu_local_hit": 5}` | `{"gpu_local_hit": 5}` | - | 5.000 | False |
| 16384 | target | `{"partial_gpu_hit": 5}` | `{"mixed_cpu_restore": 5}` | - | 5.000 | False |
| 16384 | overload | `{"partial_gpu_hit": 5}` | `{"mixed_cpu_restore": 5}` | - | 5.000 | False |

## 结论边界

本报告只判定 stock APC/native offload 在受控容量压力下是否留下值得进入 A1 seam 验证的候选缺口。它不证明 ToolGap runtime 已实现、性能更快、真实工具等待一定触发驱逐，或生产 workload 有同等收益。
