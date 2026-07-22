# A0.2 Stock Sufficiency

状态：`roadmap`（harness 正在实现；尚无 comparative GPU 结论）。

本目录实现冻结的 A0.2 falsification gate：在相同 HND layout 下比较 stock APC（S0）与
stock APC + native `OffloadingConnector`（S1）。它不包含 ToolGapController、custom
connector 或 lifecycle runtime。

## 固定执行顺序

1. CPU contracts：`PYTHONPATH=src python3 experiments/A0.2-stock-sufficiency/test_a02.py -v`
2. HND calibration：`VLLM_KV_CACHE_LAYOUT=HND PYTHONPATH=src python3 experiments/A0.2-stock-sufficiency/run_calibration.py --attempt 1`
3. connector/probe preflight（实现后由本 README 补充唯一命令）；
4. 只消费已关闭 gate artifact 的 90-run comparative matrix；
5. 只读 raw bundles 的结果聚合。

`raw/` 保存本机不可覆盖的 GPU evidence，并由仓库 `.gitignore` 排除；跟踪的结果报告只引用
其路径与 SHA-256。任何 `invalid_configuration`、`accounting_contract_change` 或预注册的
preflight 失败都会保留 artifact 并停止后续 gate，不会通过改参数或补有利 run 绕过。

## 当前已冻结契约

- schedule 恰好 90 项：3 个 L × 3 个 M × 5 pair × 2 policy；
- AB/BA 是 pair order，不增加维度；pair 内 S0/S1 共享 nonce；
- `W` 已包含前台 block，背景目标为 `floor(M*C)-L/block_size`；
- S1 CPU tier 不小于 `1.5*C*block_bytes`，并以整 GiB 向上取整；
- engine 总 cached tokens 与 per-request local/external source accounting 分开记录；无法分源时
  必须 `inconclusive`，不得把总命中伪装成 GPU hit 或 CPU restore。
