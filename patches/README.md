# vLLM patches

This directory is empty until the Phase 0 source audit demonstrates a missing
vLLM contract. Prefer an official extension point. If a patch is required, add:

- the exact upstream commit;
- a minimal patch file generated from that commit;
- the missing capability it supplies;
- build and verification commands;
- a patch-size summary and an upstream issue or PR reference when appropriate.

For the A0.2 pin, upstream #39186's job-scoped offload model is already present:
`store_jobs`/`load_jobs`, worker `completed_jobs`, and scheduler-side
`TransferJobStatus`. D029 records a narrower candidate contribution: native
load failures still assert, while the generic scheduler already has an
`invalid_block_ids` recompute receiving path. A future Patch 1 may bridge only
that failure contract after its fake-worker admission tests pass.

It must report terminal outcomes across workers, identify failed load
destination blocks precisely, use vLLM's existing recompute/fail policy, and
discard failed store jobs without leaking job/fence state. It must not restore
the obsolete `reqs_to_store`/`reqs_to_load` request-scoped interface, duplicate
physical block fencing, or call/replace `complete_store`/`complete_load`.

Do not vendor a full vLLM source tree into this repository.
