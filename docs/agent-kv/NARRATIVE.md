# Career and Interview Narrative

## 1. Claim-State Warning

Everything in this file is a future narrative template. The project currently
has no implementation or measurement. Do not use completed-action verbs until
the corresponding evidence exists.

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
> consumes transfer bandwidth, and dropping everything raises resume TTFT. I am
> building a vLLM lifecycle runtime that chooses among retain, CPU offload, and
> recompute from measured hardware costs and runtime pressure, then validates the
> policy against tuned static baselines with deterministic replay and failure
> injection.

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
> recompute when the tool returns. None is always optimal because GPU compute,
> HBM capacity, host-link bandwidth, gap duration, cancellation, and queue pressure
> change the break-even point.
>
> The project integrates a lifecycle state machine and cost-aware policy into a
> pinned vLLM version. It records a DecisionTrace for each action, handles cancel
> and transfer failure, and evaluates the policy against default recompute, static
> TTL, soft retention, and always-offload baselines. The goal is not to claim a
> new first mechanism; it is to build a defensible runtime artifact and show the
> conditions where dynamic control is or is not justified.

## 5. Ownership Boundary

### Candidate-Owned Work

```text
lifecycle state machine and invariants
vLLM integration or plugin
cost profiler and calibration format
online decision policy
DecisionTrace and attribution
workload compiler and deterministic replay
baseline fairness and experiment protocol
failure injection and fallback tests
hindsight references under documented assumptions
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

The completed answer must name files/modules and tests. The intended categories are:

```text
runtime lifecycle state and hooks
policy and profiler
executors/fallback
decision tracing
deterministic replay
fault-injection and performance tests
```

Do not answer with a list of frameworks.

### What Was the Hardest Problem?

A credible answer should come from an observed failure, not the roadmap. Likely
categories are:

```text
cache identity and correctness
resume/cancel/transfer races
attributing tail latency under queueing
matching policy estimates to asynchronous real execution
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

### Runtime-Focused Version

- Implemented an agent-aware KV lifecycle runtime for vLLM that coordinates GPU
  retention, CPU offload/restore, and fallback recomputation across tool-call
  pauses, including epoch-based resume/cancel handling and cache-compatibility
  checks.
- Built a hardware-calibrated cost policy and request-level DecisionTrace using
  measured prefill and transfer curves; bounded decision overhead at `[X]` under
  `[hardware/model/load]`.
- Developed deterministic agent-workload replay and fault injection covering
  duplicate resume, cancel-during-restore, tier exhaustion, and transfer failure,
  with `[N]` verified failure scenarios and fallback outcomes.
- Evaluated default recompute, tuned static TTL, soft retention, always-offload,
  and dynamic policies across `[workloads/hardware]`, improving `[metric]` by
  `[X]` in `[positive region]` while identifying `[negative region]` where static
  control remained preferable.

### Measurement-Study Version

- Built a real-vLLM agent KV lifecycle testbed and hardware profiler that maps
  retain/offload/recompute break-even regions across context length, tool gap,
  HBM pressure, and host-link contention.
- Compared tuned static and cost-aware lifecycle policies against documented
  hindsight bounds, reporting both positive regions and workloads where dynamic
  control failed to justify its overhead.

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
