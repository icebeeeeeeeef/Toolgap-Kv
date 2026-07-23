# A0.2 Stock Sufficiency

状态：`experimentally validated`。

2026-07-23 的最终有效 Attempt 2 已完成 90/90 个 registered runs，正式 gate
判决为 `inconclusive`：没有任何预注册 Stop 或 Continue 条件被触发。完整 cell
数据、条件裁决、Attempt 1 provenance failure 和结论边界见
[A0.2-stock-sufficiency-results-2026-07-23.md](A0.2-stock-sufficiency-results-2026-07-23.md)。
该结论不授权 A1、ToolGapController、性能 bullet 或 lifecycle runtime。

本目录实现冻结的 A0.2 falsification gate：在相同 HND layout 下比较 stock APC（S0）与
stock APC + native `OffloadingConnector`（S1）。它不包含 ToolGapController、custom
connector 或 lifecycle runtime。

## 冻结执行顺序

1. CPU contracts：`PYTHONPATH=src python3 experiments/A0.2-stock-sufficiency/test_a02.py -v`
2. HND calibration：`VLLM_KV_CACHE_LAYOUT=HND PYTHONPATH=src python3 experiments/A0.2-stock-sufficiency/run_calibration.py --attempt N`
3. connector/probe preflight：`VLLM_KV_CACHE_LAYOUT=HND PYTHONPATH=src python3 experiments/A0.2-stock-sufficiency/run_preflight.py --attempt N`；
4. 非比较预算 dry-run：`VLLM_KV_CACHE_LAYOUT=HND PYTHONPATH=src python3 experiments/A0.2-stock-sufficiency/run_budget.py --attempt N`；
5. 预算通过后，按 ordinal `1..90` 执行：`VLLM_KV_CACHE_LAYOUT=HND PYTHONPATH=src python3 experiments/A0.2-stock-sufficiency/run_matrix.py --ordinal N --attempt A`；
6. 只读 raw bundles 的结果聚合：`PYTHONPATH=src python3 experiments/A0.2-stock-sufficiency/aggregate_results.py --attempt A`。

上述命令是历史复核入口，不是继续追加 run 的授权。D028 已关闭当前 A0.2
matrix；新的实验必须有独立 ticket、规格与 attempt provenance。

`raw/` 保存本机不可覆盖的 GPU evidence，并由仓库 `.gitignore` 排除；跟踪的结果报告只引用
其路径与 SHA-256。任何 `invalid_configuration`、`accounting_contract_change` 或预注册的
preflight 失败都会保留 artifact 并停止后续 gate，不会通过改参数或补有利 run 绕过。
预算 dry-run 固定消费 schedule ordinal 42（`L=8192, M=1.10, S0`），只估算成本，不计入
90-run comparative matrix；保守预测超过 12 GPU-hours 时不得启动 matrix。

## 当前已冻结契约

- schedule 恰好 90 项：3 个 L × 3 个 M × 5 pair × 2 policy；
- AB/BA 是 pair order，不增加维度；pair 内 S0/S1 共享 nonce；
- `W` 已包含前台 block，背景目标为 `floor(M*C)-L/block_size`；
- S1 CPU tier 不小于 `1.5*C*block_bytes`，并以整 GiB 向上取整；
- engine 总 cached tokens 与 per-request local/external source accounting 分开记录；无法分源时
  必须 `inconclusive`，不得把总命中伪装成 GPU hit 或 CPU restore。

Gate 1 的受控 load 使用 S1 warm prefix → `M=1.10` pressure → 同 prefix resume，要求
`external_cached_tokens>0` 且 native connector `load_bytes>0`。Gate 2 用一次 pilot 以固定算法
选择 decode-active window 中点，随后十次独立 validation 必须至少 9/10 在该固定 offset 仍有
probe decode-active。当前 pin 没有 request-scoped load start/end seam，
`transfer_overlap_observable=false` 始终保留，不会由累计 stats 冒充区间证据。

## 最终证据入口

- 跟踪的正式报告：
  [A0.2-stock-sufficiency-results-2026-07-23.md](A0.2-stock-sufficiency-results-2026-07-23.md)
- 机器可读聚合：
  [results/attempt-02/a02-matrix-summary.json](results/attempt-02/a02-matrix-summary.json)
- 简版聚合：
  [results/attempt-02/a02-matrix-summary.md](results/attempt-02/a02-matrix-summary.md)
- 本机 raw：
  `raw/matrix/**/ordinal-*-a02/`（`.gitignore` 排除，报告记录哈希与范围）

Attempt 1 因未冻结 GPU KV capacity 而 provenance invalid，原始证据与
`results/attempt-01/` 被保留。Attempt 2 将 3151 blocks 显式传入两臂并逐 run
复核，是唯一进入 D028 判决的 comparative matrix。
