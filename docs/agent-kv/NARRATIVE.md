# Career and Interview Narrative

## 1. Claim-State Warning

Everything in this file is a future narrative template. Only engine-independent
Phase 0 scaffolding is shipped; the project has no current-vLLM integration or
measurement. Do not use completed-action verbs until the corresponding evidence
exists.

## 2. Honest Background Narrative

The candidate is a student with ByteDance object-storage data-plane internship
experience and no prior production inference-runtime role.

The coherent bridge is not a fabricated internal-company story. It is:

1. Object-storage data-plane work built intuition about data movement, memory and
   storage hierarchy, admission, backpressure, failure semantics, and observability.
2. Public LLM-serving papers and vLLM source showed that agent KV cache is also a
   data-lifecycle problem, but its state is recomputable and tied to model/runtime
   compatibility.
3. Agent tool calls create idle intervals where keeping, moving, or recomputing
   state has different resource costs.
4. Existing systems provide strong partial solutions, but current interfaces and
   decisions remain fragmented across engines and hardware regimes.
5. The project was selected to transfer storage data-plane reasoning into a real
   inference-runtime mechanism with measurable boundaries.

Do not claim that an internal ByteDance team or document inspired the project
unless that event actually occurred and is safe to disclose.

## 3. Thirty-Second Version

> Agent workloads pause during tool calls. Their KV cache is temporarily idle but
> may be expensive to recompute. Retaining everything wastes HBM, offloading
> consumes transfer bandwidth, and dropping everything may raise resume TTFT. I am
> using a pinned current-vLLM build to make the requested and actual cache path
> auditable, test fallback and stale/failure behavior, and measure where retain,
> CPU restore, or recompute wins or loses. I will add dynamic selection only if
> measurements prove that static behavior cannot cover the reachable regimes.

Use present tense only after implementation starts. Before then, say `I plan to`
or `the roadmap is`.

## 4. Two-Minute Version

> My previous systems experience is in object-storage data plane, where the hard
> problems are often placement, data movement, backpressure, and failure recovery.
> When studying LLM serving, I noticed that KV cache becomes a similar but not
> identical lifecycle problem: it is large and movable, but it is ephemeral and
> can be recomputed from tokens.
>
> In an agent loop, an LLM generates a tool call and pauses. During that gap, the
> runtime can retain KV in GPU memory, offload it to CPU memory, or evict it and
> recompute when the tool returns. GPU compute, HBM capacity, host-link bandwidth,
> gap duration, cancellation, and queue pressure may change the break-even point;
> the project measures whether those changes are reachable on its testbed.
>
> The project first audits one current vLLM version to find the smallest supported
> lifecycle/offload seam. Over that seam I implement an in-process logical
> lifecycle controller for epochs, transitions, asynchronous completion,
> cancellation, fallback, and cleanup. It orchestrates vLLM's existing KV movement
> rather than replacing its block manager or tensor-transfer code, and records
> requested action, actual GPU hit, CPU restore or recompute, and explicit fallback
> in a DecisionTrace. The performance work measures prefill and transfer costs plus
> active-request and tail impact on a declared single-node testbed.
>
> The goal is not to claim a new lifecycle mechanism. It is to produce a real
> runtime work sample with conformance, failure, and break-even evidence. A tuned
> static TTL or action-only policy is allowed to win; a dynamic selector is a
> conditional extension rather than the success criterion.

## 5. Ownership Boundary

### Candidate-Owned Work

```text
lifecycle state machine and invariants
vLLM integration or plugin
cost profiler and calibration format
forced/static action selection and, only after Gate B, an online policy
DecisionTrace and attribution
workload compiler and deterministic replay
baseline fairness and experiment protocol; Gate B0 only after CT3
failure injection and fallback tests
hindsight references under documented assumptions, only if Gate B needs them
performance and validity report
```

### Dependencies, Not Candidate-Owned

```text
vLLM PagedAttention and model runner
SGLang RadixAttention
LMCache or Mooncake transfer implementations
CUDA kernels supplied by engines/frameworks
Prometheus and Grafana
base model capabilities
public benchmark datasets
```

Integration effort may be claimed, but dependency features must not be rewritten
as personal implementation.

## 6. Expected Interview Questions

The complete adversarial question bank, evidence gates, and rehearsal workflow
live in [interview-grill/README.md](interview-grill/README.md). The answers below
are only the short narrative subset.

### Why vLLM Instead of SGLang?

Recommended answer:

> The primary question is lifecycle choice, not which engine wins. I selected one
> engine to control implementation variance. vLLM's current native offload policy
> surface is a practical integration point, and its retention gap is itself useful
> to study. SGLang is relevant to PBKV and radix-tree semantics, but a second engine
> would require a separate fidelity and baseline effort. It remains an extension.

### Why Not Implement Both Engines?

> Because engine adapters can succeed independently and need separate correctness
> and performance validation. Adding both before validating the hypothesis would
> replace depth with integration breadth. I first prove the mechanism on one pinned
> engine and only add another if a specific cross-engine question remains.

### Why Not Just Use LMCache?

> LMCache is a KV storage and transfer dependency, not the complete lifecycle
> decision. The project asks when to retain, move, or recompute and how to recover
> safely. The MVP uses native vLLM offload to minimize dependencies. LMCache becomes
> relevant only if cross-instance or additional-tier capabilities are required.

### What Did You Actually Code?

The completed answer must name files/modules and tests. The unconditional intended
categories are:

```text
minimal runtime lifecycle seam and hooks
requested/observed/fallback contract
native-executor orchestration and safe fallback
decision tracing
deterministic replay
fault-injection and performance tests
```

Do not answer with a list of frameworks.

The state machine is not optional scope. The code must own lifecycle behavior,
while vLLM remains responsible for physical block/refcount management,
PagedAttention, model execution, and native D2H/H2D movement. A module that only
emits DecisionTrace records is observability work, not the runtime mechanism.

### What Was the Hardest Problem?

A credible answer should come from an observed failure, not the roadmap. Likely
categories are:

```text
cache identity and correctness
resume/cancel/transfer races
attributing tail latency under queueing
matching requested actions to asynchronous observed execution
static baseline tuning without test leakage
```

The final story must identify the concrete symptom, competing hypotheses,
instrumentation, root cause, fix, and regression test.

### Does a Better GPU Produce Better Results?

> It improves absolute performance but does not guarantee a larger policy gain.
> Faster compute makes recomputation cheaper, faster host links make offload
> cheaper, and larger HBM makes retention cheaper. I report the decision boundary
> using measured ratios rather than selecting hardware that maximizes uplift.

## 7. Resume Bullet Templates

Use only after evidence exists.

### Integration, Correctness, and Boundary Version

- Integrated paused-agent KV lifecycle experiments into pinned vLLM `[commit]`
  through `[extension/patch]`, tracing requested actions to GPU hit, CPU restore,
  recompute, and explicit fallback while preserving the default request path.
- Defined and tested `[identity/epoch/fallback contracts]` for `[failure cases]`,
  using deterministic fault injection and output/cleanup assertions under
  `[model/runtime configuration]`.
- Measured retain/offload/recompute boundaries on `[hardware]` across
  `[context/KV sizes and pressure condition]`; compared `[baselines]`, reported
  `[metric/result]`, and preserved `[losing region or active-request regression]`.
- Built a deterministic tool-use replay harness from `[workload provenance]`,
  explicitly labeling injected timing and arrival behavior as
  `trace-derived synthetic` and calibrating it with `[real trace]`.

### Measurement-Study Version

- Built a real-vLLM agent KV lifecycle testbed and hardware profiler that maps
  retain/offload/recompute break-even regions across context length, tool gap,
  HBM pressure, and host-link contention.
- Compared forced action paths and tuned static behavior on held-out workloads,
  reporting both positive boundaries and workloads where moving KV was slower or
  harmed active-request tail latency.

### Conditional Gate-B Policy Version

Use only if Gate B passes and the evidence ledger contains the results:

- Implemented a transparent lifecycle selector over shared action executors after
  measurements showed `[regime A]` and `[regime B]` preferred different actions;
  compared it with a separately tuned static baseline, measuring `[result]`,
  `[decision overhead]`, and `[losing condition]` on `[testbed]`.

## 8. Language to Avoid

Do not say:

```text
first retain/offload/recompute system
production-proven distributed KV fabric
implemented PagedAttention
built LMCache or Mooncake
reproduced PBKV when only a simplified score was implemented
simulated an H100 by limiting 4090 memory
optimized p99 without repeated tail measurements
```

## 9. Hiring Signal

The strongest hiring signal is not the number of technologies. It is the chain:

```text
real agent-serving problem
-> owned in-process mechanism
-> concurrency and failure correctness
-> calibrated performance model
-> fair baselines and negative cases
-> reproducible evidence
-> honest validity boundary
```

If the implementation stays entirely outside the serving process, the narrative
must be downgraded to benchmark and policy engineering. Conversely, using an
official runtime plugin does not weaken ownership when it owns real lifecycle
semantics, correctness, and hot-path behavior.
