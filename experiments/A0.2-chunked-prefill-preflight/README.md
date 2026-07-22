# A0.2 chunked-prefill configuration preflight

这是与 `A0.1R-partial-block-residual` 并列的独立实验。它不重写 A0.1R 的 raw bundle，也不
执行 A0.2 的 builder、active probe、CPU connector 或性能矩阵。

## 目的

A0.1R 在 `enable_chunked_prefill=False` 下证明了无压力 APC admission，但该配置在 pinned
vLLM 上有 upstream unsupported warning。本实验仅验证：切换至受支持的
`enable_chunked_prefill=True` 后，同一 canonical R0/R1 pair 是否仍保留已登记的 request
accounting contract。

每个 ordinal 使用 fresh in-process `LLM`，无并发地完成 R0 后立即提交 R1。判决输入直接
读取 `RequestOutput.prompt_token_ids`、completion `token_ids` 和 `num_cached_tokens`；不会
从文本重新 tokenize 重建 R0。

## 冻结判据

三个 ordinal 都必须满足：

```text
prefix caching = true
chunked prefill = true
R0.num_cached_tokens = 0
R1.num_cached_tokens = 192
LCP = 199
R0/R1 assistant tool-call semantic span = [178, 198)
```

`R1 != 192` 不被自动解释为 APC miss 或成功 hit，而是
`accounting_contract_change`：暂停 A0.2，重新审计 accounting mapping。计数缺失、超出 prompt
长度、配置/anchor 漂移是 `invalid_run`；semantic token 漂移是 `semantic_stop`。

单请求 preflight 不证明压力下 chunked-prefill interleaving 的正确性。若本实验通过，A0.2
comparative run 仍须对每个 run 持续执行 mapping/anchor check。

## 目录边界

- `preflight.py`：不导入 vLLM 的 verdict 与不可变 bundle 写入；
- `run_preflight.py`：唯一 GPU 入口；只复用冻结 A0.1R 的 engine-truth 提取 helpers；
- `test_preflight.py`：CPU-only 合约测试；
- `raw/`：每个 GPU ordinal 的五文件 evidence bundle，Git 忽略。

执行前，所有 tracked inputs 必须已提交且无 diff。先运行：

```bash
PYTHONPATH=src python3 experiments/A0.2-chunked-prefill-preflight/test_preflight.py -v
PYTHONPATH=src python3 experiments/A0.2-chunked-prefill-preflight/run_preflight.py --help
```

通过代码审阅并提交后，云机上按 ordinal 独立启动：

```bash
PYTHONPATH=src python3 experiments/A0.2-chunked-prefill-preflight/run_preflight.py \
  --ordinal 1 --attempt 1
```

不得以 majority vote、改 fixture、补跑覆盖原 bundle 或修改 `C=192` 的方式换取通过。
