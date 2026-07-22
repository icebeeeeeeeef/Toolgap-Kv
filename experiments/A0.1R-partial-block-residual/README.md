# A0.1R：partial-block residual admission

这是一个独立于 `0001-mechanism-feasibility` 的复核实验目录。它不改写 A0.1 的历史
bundle 或 verdict；只消费其冻结的 fixture 与可复用前缀锚点，回答一个更窄的问题：stock
vLLM APC 是否会把已经被 token-level LCP 证明的 `192` 个完整 block token 实际计入
R1 的 `RequestOutput.num_cached_tokens`。

目录边界：

- `task0.py`：不依赖 vLLM 的判决与不可变 evidence bundle 写入；
- `run_task0.py`：唯一的 GPU 执行入口，直接读取引擎 `RequestOutput`；
- `test_task0.py`：CPU-only regression；
- `a0.1-task0-prefix-anchor.json`：可从干净 clone 重算的 192-token 输入锚点；
- `raw/`：将来每次 GPU ordinal 的不可变五文件 bundle（Git 忽略）。

当前状态是 `roadmap`：源码已可审阅，尚未执行 GPU ordinal，因此不产生任何性能、vLLM
集成成功或 stock APC 成功的声明。

执行前先完成 CPU gate：

```bash
PYTHONPATH=src python3 experiments/A0.1R-partial-block-residual/test_task0.py -v
python3 experiments/A0.1R-partial-block-residual/run_task0.py --help
```

GPU 运行只能在这些输入已提交且干净时进行：

```bash
PYTHONPATH=src python3 experiments/A0.1R-partial-block-residual/run_task0.py \
  --ordinal 1 --attempt 1
```

`--ordinal` 只能取 1、2、3；没有 M、policy、pressure、offload 或 benchmark 参数。这是
admission preflight，不是 A0.2 压力实验。
