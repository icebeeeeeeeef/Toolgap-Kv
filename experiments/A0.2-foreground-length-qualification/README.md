# A0.2 Foreground-Length Qualification

## Purpose

This is a prerequisite evidence experiment, not the A0.2 pressure matrix. It
qualifies one immutable foreground fixture for each registered full-prefix
target: `2048`, `8192`, and `16384` tokens. A fixture only becomes a usable
A0.2 input after a separate five-fresh-process engine-truth qualification and
an `admission_pass` promotion.

The builder changes only `initial_messages[0].content`: it appends a fixed
archival-context section and measures the full pinned chat-template token
sequence. It never changes the user question, tool schema, tool result, model
revision, or a tool-call ID.

## Required sequence

1. On the GPU host with the pinned model snapshot already local, prepare one
   fixture per target. This uses the tokenizer only; it does not start vLLM.

   ```bash
   PYTHONPATH=src python3 experiments/A0.2-foreground-length-qualification/build_fixtures.py --target 2048 --output experiments/A0.2-foreground-length-qualification/fixtures/foreground-2048.json
   PYTHONPATH=src python3 experiments/A0.2-foreground-length-qualification/build_fixtures.py --target 8192 --output experiments/A0.2-foreground-length-qualification/fixtures/foreground-8192.json
   PYTHONPATH=src python3 experiments/A0.2-foreground-length-qualification/build_fixtures.py --target 16384 --output experiments/A0.2-foreground-length-qualification/fixtures/foreground-16384.json
   ```

2. Review and commit those three fixtures. For each target `L`, the recorded
   prompt length must be inside `[L-21, L-6]`; selection is closest to `L-13`,
   then the smaller archival record count. If the pinned tokenizer cannot reach
   that window, stop: do not alter padding after the result.

3. Qualification has passed for all three targets. The five-process runner
   preserved raw bundles under `raw/`; only an `admission_pass` bundle was
   promoted into `anchors/foreground-<L>.json`. See
   [the reviewed result record](A0.2-foreground-length-qualification-results-2026-07-23.md).

4. All three anchors are independently reviewed and committed. A0.2 remains
   `roadmap` until its comparative runner, calibration and preflights are
   implemented and reviewed; this directory makes no cache-miss, offload,
   latency, throughput, or lifecycle-runtime claim.

## Local checks

```bash
PYTHONPATH=src python3 experiments/A0.2-foreground-length-qualification/test_qualification.py -v
make check
```

Raw bundles are intentionally ignored by Git. Fixture, anchor, source, test,
and reviewed result-summary files are tracked evidence.
