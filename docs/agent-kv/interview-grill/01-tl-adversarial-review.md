# Initial Inference-TL Adversarial Review

> Interview-preparation state: `draft`
>
> Project claim state: `roadmap`
>
> Last reviewed: 2026-07-11

## 1. Review Lens

This review assumes the strongest interview-sized version described in
[../NARRATIVE.md](../NARRATIVE.md) has eventually been completed. The real
project currently has no implementation or measurement, so every completed-tense
answer below is a future template gated by the listed evidence.

The provisional TL verdict is:

```text
LLM serving/runtime project: select for a technical interview if evidence exists
research novelty claim: reshape unless an explicit new contribution is proved
kernel/compiler role: insufficient by itself
```

The adverse starting hypothesis is that the candidate combined existing papers,
vLLM offload capabilities, a small policy wrapper, and synthetic workloads into
an over-packaged project. The purpose of the questions is to determine whether
the candidate can disprove that hypothesis.

## Q01. Existing Work Already Does This. What Is Your Contribution?

**State:** `draft`

**TL challenge**

> InferCept, PBKV, Continuum, and other systems already discuss preserving,
> swapping, discarding, predicting, or scheduling KV state around interruptions.
> What did you add?

**What this tests**

Whether the candidate can distinguish prior mechanisms, dependency features,
owned implementation, and an actual research result.

**Recommended answer**

> I do not claim to have invented retain, offload, or recompute. Existing work
> established those actions and several scheduling policies. My owned mainline is
> a pinned-vLLM, in-process lifecycle implementation: request epochs and legal
> transitions, tool-wait/resume hooks, safe fallback, hardware calibration, and
> request-level DecisionTrace. The evaluation contribution is a reproducible map
> of when dynamic control beats a separately tuned static TTL and where it does
> not. If my online policy is not algorithmically distinct from prior work, I
> describe the project as runtime implementation plus measurement study, not as a
> novel scheduling algorithm.

**Likely follow-ups**

- Which line of the related-work matrix is genuinely different?
- Is the policy only a PBKV- or MinWaste-inspired approximation?
- What result would remain publishable if the dynamic policy loses?

**Evidence gate**

- Updated [../RELATED_WORK.md](../RELATED_WORK.md) with a semantic delta table.
- Exact candidate-owned runtime diff and tests.
- Ablation separating lifecycle mechanism, policy, and instrumentation.
- Negative-result report showing the validity boundary.

**Dangerous answer**

> Existing work did not combine all three actions, so this is the first complete
> system.

**Project action if the answer remains weak**

Remove algorithmic novelty language and package the project as a vLLM runtime and
hardware-calibrated decision-boundary study.

## Q02. Is This Too Engineering-Heavy to Count as a Research Project?

**State:** `draft`

**TL challenge**

> You built state machines, metrics, replay, and failure handling. Where is the
> research rather than ordinary engineering?

**What this tests**

Whether the candidate confuses implementation size with research contribution.

**Recommended answer**

> The engineering is necessary because the hypothesis concerns real scheduler,
> memory, transfer, and queueing behavior. It becomes a systems research project
> only through a falsifiable question: under which hardware-cost ratios, HBM
> pressure, tool-gap distributions, and loads does dynamic lifecycle control beat
> a tuned static policy? The implementation supplies causal evidence; it is not
> itself the novelty claim. If I only finish the components without answering that
> question, I will present it as an engineering project rather than research.

**Likely follow-ups**

- State the hypothesis in one sentence.
- What observation would falsify it?
- Which ablation isolates the claimed cause?

**Evidence gate**

- Pre-registered hypotheses from [../EVALUATION.md](../EVALUATION.md).
- Raw runs for positive and negative regions.
- An ablation where executors remain fixed and only the decision policy changes.

**Dangerous answer**

> It is research because nobody has built exactly my architecture.

**Project action if the answer remains weak**

Downgrade the label to `runtime engineering project`; do not use research framing
to compensate for missing experimental insight.

## Q03. Is This Really Agent-Aware or Just Generic Paused-Request Management?

**State:** `draft`

**TL challenge**

> Gap length, KV bytes, queue depth, and HBM pressure apply to any suspended
> request. Why are you calling the policy agent-aware?

**What this tests**

Whether `agent` is a real workload mechanism or a fashionable label.

**Recommended answer**

> The lifecycle mechanism is interruption-aware and can be generic. It becomes
> agent- or tool-gap-aware only if the policy consumes and validates signals such
> as tool class, tool-latency prior, continuation or cancellation probability,
> workflow deadline, and repeated multi-turn context. I will ablate those signals
> against a generic pressure-only policy. If they do not improve decisions, the
> honest name is tool-gap or paused-request KV lifecycle, not agent-aware policy.

**Likely follow-ups**

- Which agent signal is available before the tool returns?
- How do you avoid leaking the true future gap into the online policy?
- Does tool identity remain predictive after distribution shift?

**Evidence gate**

- A versioned online feature schema containing only decision-time information.
- Agent-signal ablation against a generic runtime-pressure policy.
- Calibration/test split and distribution-shift workload.

**Dangerous answer**

> It is agent-aware because requests call tools.

**Project action if the answer remains weak**

Rename the project description to `tool-gap-aware` or `interruption-aware` and
remove semantic-agent claims from the resume bullet.

## Q04. vLLM Already Has Offload and Policy Hooks. What Did You Code?

**State:** `draft`

**TL challenge**

> If vLLM moves the tensors and exposes CachePolicy hooks, are you only choosing
> an enum?

**What this tests**

The ownership boundary and whether the work executes inside the real serving
path rather than in an external Python wrapper.

**Recommended answer**

> vLLM's allocator, model runner, and transfer implementation are dependencies. I
> own the lifecycle semantics around them: detecting tool wait and resume,
> maintaining request epochs and legal state transitions, constructing immutable
> decision snapshots, choosing actions, handling asynchronous completion and
> fallback, and emitting DecisionTrace tied to actual block outcomes. In the
> completed interview answer I must name the exact modified modules, functions,
> tests, and patch commit. If the work stays outside the serving process, I will
> describe it only as policy and benchmark engineering.

**Likely follow-ups**

- Trace one request through the exact functions you changed.
- What behavior disappears if your patch is removed?
- Why could this not be implemented entirely at the gateway?

**Evidence gate**

- Pinned vLLM commit and local patch hash.
- Code-path diagram with exact module and function anchors.
- Integration tests proving the lifecycle behavior disappears without the patch.
- Hot-path overhead measurement.

**Dangerous answer**

> I implemented KV offload in vLLM.

**Project action if the answer remains weak**

Reduce the ownership claim to the actual adapter, policy, replay, and measurement
work; do not claim the dependency's data path.

## Q05. Is Retain Just Doing Nothing?

**State:** `draft`

**TL challenge**

> If the request pauses and you leave its blocks alone, what mechanism did you
> implement for `retain`?

**What this tests**

Whether `retain` has explicit allocator and admission semantics or is merely a
renamed no-op.

**Recommended answer**

> Retain must mean an explicit, bounded residency contract, not simply skipping
> eviction. The runtime records which block set is retained, for how long or at
> what priority, and which safety valve releases it when active allocation would
> otherwise fail. The policy accounts for its HBM-time cost and the scheduler
> records any displaced or delayed work. If the pinned vLLM interface cannot
> express those semantics without a broad fork, I will narrow the MVP to
> offload-versus-recompute or contribute a minimal retention interface first.

**Likely follow-ups**

- Who can revoke retention?
- Can retained blocks starve active decode requests?
- What is the difference between hard retain and soft retention?

**Evidence gate**

- Explicit retention state and allocator interaction.
- Pressure tests showing the safety valve.
- Metrics for retained HBM-time, admission delay, and evictions caused or avoided.

**Dangerous answer**

> Retain is free because the KV is already in GPU memory.

**Project action if the answer remains weak**

Treat retention availability as a calibration-sprint go/no-go condition rather
than hiding a missing runtime contract behind policy terminology.

## Q06. How Do You Price HBM Opportunity Cost and System-Wide Interference?

**State:** `draft`

**TL challenge**

> Store and restore have measured latency, but retain's cost is an externality.
> How can a per-request score represent requests that were never admitted?

**What this tests**

Whether the cost model captures shared-resource effects rather than comparing
three isolated microbenchmarks.

**Recommended answer**

> I begin with measured request-local terms: expected recompute cost is resume
> probability times prefill cost; offload includes store, expected restore,
> transfer contention, and failure penalty. Retain cannot be priced only in
> milliseconds, so its cost includes HBM occupancy under the current working-set
> pressure and the observed admission, preemption, or decode impact. The first
> policy is an analytic approximation, not a proof of global optimality. I test
> its estimates against actual outcomes and report regimes where queueing or
> contention invalidates the model.

**Likely follow-ups**

- How is pressure sampled without racing the scheduler?
- Do you use marginal or average cost?
- What prevents oscillation near a decision boundary?

**Evidence gate**

- Same-path prefill, D2H, and H2D calibration curves.
- Decision inputs and estimated-versus-observed error in DecisionTrace.
- Admission, preemption, and active-decode ablations under controlled pressure.
- Hysteresis or explicit proof that action switching is not harmful.

**Dangerous answer**

> I assigned weights to latency, memory, and queue length and tuned them until the
> benchmark improved.

**Project action if the answer remains weak**

Reframe the policy as a heuristic and focus the study on model error and measured
break-even boundaries.

## Q07. Did You Manufacture a Workload That Makes Your Policy Win?

**State:** `draft`

**TL challenge**

> Synthetic sleeps let you choose any tool-gap distribution. Why should I trust
> your result?

**What this tests**

Workload provenance, realism, and resistance to benchmark overfitting.

**Recommended answer**

> I separate two purposes. Trace- or benchmark-derived distributions provide a
> reality anchor for context lengths, turns, gap durations, cancellation, and
> arrival patterns. A deterministic synthetic harness then sweeps those dimensions
> to identify causal boundaries and negative regions. Sanitized or incomplete
> traces are described as distribution calibration, not exact production replay.
> Policy tuning and final testing use separate splits, and the full workload
> generator configuration is published with the raw runs.

**Likely follow-ups**

- What exact source justified each distribution?
- Which dimensions are measured and which are assumptions?
- How sensitive are results to a shifted gap distribution?

**Evidence gate**

- Workload provenance table and generation seeds.
- Separate calibration and test manifests.
- Controlled parameter sweeps plus at least one trace-derived workload.
- Distribution-shift and cancellation-heavy negative cases.

**Dangerous answer**

> The synthetic workload is realistic because it resembles an agent.

**Project action if the answer remains weak**

Limit the claim to a controlled feasibility study and remove real-agent workload
language.

## Q08. Why Is a Tuned Static TTL Not Enough?

**State:** `draft`

**TL challenge**

> Static TTL is simple, reliable, and cheap. Did you compare against a deliberately
> weak value?

**What this tests**

Baseline fairness and whether dynamic complexity solves a material problem.

**Recommended answer**

> Static TTL is the strongest practical baseline, not a straw man. I tune it on a
> separate calibration split, disclose the candidate values and selected value,
> and run it through the same retain/offload/recompute executors, capacity limits,
> and failure semantics as the dynamic policy. My hypothesis is selective: static
> control should remain competitive in stationary regimes, while dynamic control
> is justified only when several action regions coexist or pressure shifts over
> time.

**Likely follow-ups**

- Why one global TTL rather than per-tool or per-context buckets?
- Did tuning leak test information?
- What is the simplest stronger static baseline?

**Evidence gate**

- Separate tuning logs and untouched test workloads.
- Default, tuned TTL, soft retention, always-offload, and recompute baselines.
- Bucketed or piecewise-static ablation if a single TTL is obviously weak.

**Dangerous answer**

> We used 30 seconds because it is a common default.

**Project action if the answer remains weak**

Strengthen the baseline before improving the policy; otherwise discard the
performance claim.

## Q09. Did You Improve Resume TTFT by Hurting Everyone Else?

**State:** `draft`

**TL challenge**

> Keeping paused KV can make one resumed request fast while delaying unrelated
> active requests. Is resume TTFT a misleading metric?

**What this tests**

Metric selection, system-level causality, and tail-latency discipline.

**Recommended answer**

> Resume TTFT is a diagnostic metric, not the sole objective. The primary result
> must include end-to-end agent JCT or Goodput@SLO, with TPOT, global p95/p99,
> throughput, preemption, and active-request latency as guardrails. I report both
> the resumed request benefit and the externality on the rest of the system. A
> policy that wins resume TTFT but lowers system goodput or violates foreground
> SLOs is classified as a losing policy in that regime.

**Likely follow-ups**

- How is the SLO chosen and frozen before the final run?
- Are agent and non-agent requests weighted equally?
- Does the mean hide a p99 regression?

**Evidence gate**

- Pre-registered primary metric and guardrails.
- Per-class latency distributions, not aggregate averages only.
- Mixed agent/non-agent workload and fairness report.

**Dangerous answer**

> Resume TTFT fell by a large percentage, so the system is faster.

**Project action if the answer remains weak**

Remove isolated resume-TTFT improvement from the lead resume bullet.

## Q10. How Do You Handle Resume, Cancel, and Transfer Races?

**State:** `draft`

**TL challenge**

> What happens when a tool result arrives during D2H, cancellation occurs during
> H2D, or an old DMA completion arrives after the request has restarted?

**What this tests**

Whether the candidate owns real asynchronous runtime semantics rather than only
the decision rule.

**Recommended answer**

> Each request has a monotonically increasing lifecycle epoch. Async completions
> can mutate state only when request identity, epoch, and expected transition all
> match. Block ownership is exclusive across resident, transfer, offloaded, and
> released states. Cancellation is idempotent and prevents stale completions from
> resurrecting a request. Partial or incompatible restore is never consumed; the
> runtime recomputes from preserved tokens or fails explicitly. The completed
> answer must include one concrete race found in testing, its trace, root cause,
> fix, and regression test.

**Likely follow-ups**

- Which transition linearizes cancellation?
- Who releases temporary destination blocks?
- How do duplicate resume events behave?

**Evidence gate**

- State-transition tests for every legal and rejected transition.
- Fault injection for duplicate resume, cancel-during-restore, transfer failure,
  CPU-tier exhaustion, and stale completion.
- One real debugging narrative backed by DecisionTrace.

**Dangerous answer**

> vLLM handles concurrency for me.

**Project action if the answer remains weak**

Do not claim runtime ownership until these semantics execute and are tested in
process.

## Q11. Why Should Results from One GPU Generalize?

**State:** `draft`

**TL challenge**

> A faster GPU makes recomputation cheaper, a faster host link makes offload
> cheaper, and larger HBM makes retention cheaper. What does one machine prove?

**What this tests**

External validity and understanding of hardware-dependent decision boundaries.

**Recommended answer**

> Better hardware does not monotonically increase policy gain. I report exact
> hardware and use normalized axes such as restore-to-recompute ratio, active-KV
> working set over usable HBM, and arrival rate over sustainable service rate.
> Results from one machine establish only that machine's reachable regimes. A
> second GPU or topology strengthens external validity; changing memory limits on
> one GPU controls pressure but is not presented as emulating another architecture.

**Likely follow-ups**

- Why does GQA change the transfer/recompute boundary?
- How do PCIe generation, NUMA placement, and pinned memory affect results?
- Which result is hardware-independent, if any?

**Evidence gate**

- Complete environment manifest.
- Same-path calibration curves and normalized plots.
- Multiple pressure/load regimes and, preferably, a second hardware topology.

**Dangerous answer**

> H100 would produce even better improvements than my consumer GPU.

**Project action if the answer remains weak**

State the result as a single-environment feasibility result, not a general serving
law.

## Q12. Is Your Oracle Infeasible or Misnamed?

**State:** `draft`

**TL challenge**

> If the comparator knows future gap duration and ignores capacity, it cannot be
> replayed. Why do you call it an oracle or upper bound?

**What this tests**

Optimization literacy and honest interpretation of offline comparators.

**Recommended answer**

> I separate three references. A local clairvoyant lower bound chooses the
> isolated cheapest action with future information and is explicitly infeasible.
> A small-instance integer program is exact only for its documented proxy and
> constraints. A larger feasible hindsight heuristic yields an integral plan that
> can be replayed but is not guaranteed optimal. An LP relaxation bounds the proxy
> objective, not real-system performance. I do not collapse these into one oracle.

**Likely follow-ups**

- What objective and capacity constraints does the integer program use?
- How large is the LP/IP gap?
- Which queueing effects are absent from the proxy?

**Evidence gate**

- Formal objective and constraints.
- Exact small-instance validation and LP/IP gap.
- Real-runtime replay of the feasible heuristic.
- Separate reporting of optimizer-model error and runtime interference.

**Dangerous answer**

> The oracle shows my policy is within a few percent of optimal.

**Project action if the answer remains weak**

Remove optimality language and retain the comparator only as a documented
diagnostic reference.

## Q13. Is the Dynamic Policy Worth Its Complexity?

**State:** `draft`

**TL challenge**

> You added calibration, prediction, state, tracing, and new failure modes. Why not
> operate a static TTL?

**What this tests**

Whether the project budgets complexity and recognizes operational costs.

**Recommended answer**

> Dynamic control is justified only when its system-level gain exceeds decision,
> calibration, transfer, and reliability costs. I measure policy overhead and
> action churn, include a disable or fallback path, and identify stationary
> regions where static TTL should remain the production choice. The project is
> successful even if the conclusion is that dynamic control is useful only above
> a particular heterogeneity or pressure threshold.

**Likely follow-ups**

- How quickly does calibration become stale?
- What is the rollback path?
- Which state can be removed without losing most of the gain?

**Evidence gate**

- Policy-disabled overhead baseline.
- Static-versus-dynamic boundary map.
- Failure and rollback behavior.
- Removal ablation for optional signals and components.

**Dangerous answer**

> The dynamic design is more intelligent and therefore more production-ready.

**Project action if the answer remains weak**

Prefer the simpler baseline and reposition the work as a measurement study.

## Q14. Why Do You Call a Single-Node Study a Production KV System?

**State:** `draft`

**TL challenge**

> Your MVP is one vLLM process, one GPU or tensor-parallel group, HBM, and local
> DRAM. Where are the distributed-store and production claims coming from?

**What this tests**

Scope discipline and resistance to keyword inflation.

**Recommended answer**

> I do not call the MVP a distributed KV fabric or production platform. It is a
> single-node vLLM lifecycle runtime and evaluation testbed. LMCache, Mooncake,
> cross-replica routing, NVMe, and multi-tenant control are independent roadmap
> extensions with separate correctness and performance questions. They appear in
> related work or future architecture, not in the completed-project bullet unless
> separately implemented and validated.

**Likely follow-ups**

- What breaks first when moving across nodes?
- Can KV representations be shared across engines?
- What new consistency and failure semantics appear?

**Evidence gate**

- Resume bullet matches the evidence ledger exactly.
- Architecture diagrams label roadmap components.
- No unimplemented technology names in the main bullet.

**Dangerous answer**

> The architecture is production-ready even though I only tested locally.

**Project action if the answer remains weak**

Delete distributed and production language instead of attempting to defend it.

## Q15. How Do I Know You Understand AI Infra Rather Than Repeating Papers?

**State:** `draft`

**TL challenge**

> Your background is object-storage data plane. Did you learn enough inference
> internals to own this project, or did you map familiar storage words onto KV
> cache?

**What this tests**

Inference fundamentals, source-level understanding, and authenticity.

**Recommended answer**

> I use storage experience only as an entry point for data movement, pressure,
> and failure reasoning. KV cache differs from durable storage: it is
> request-scoped, model-layout-dependent, latency-critical, and recomputable from
> exact tokens. I can derive its memory footprint, explain prefill versus decode,
> GQA/MQA effects, PagedAttention blocks, allocator and scheduler interaction,
> pinned-host transfers, CUDA stream synchronization, and compatibility rules. I
> also separate every dependency feature from my code and can trace a real request
> through the modified vLLM path.

**Likely follow-ups**

- Derive KV bytes per token for the tested model.
- Why is recomputation semantically safe, and what inputs must be preserved?
- Why is an asynchronous H2D restore not merely a `memcpy`?
- How do tensor parallelism and KV dtype affect compatibility?

**Evidence gate**

- Source-reading notes tied to the pinned engine commit.
- Exact memory derivation checked against runtime allocation.
- Request-path walkthrough with code anchors.
- A real profiler or trace used to diagnose an unexpected result.

**Dangerous answer**

> KV cache is basically an object stored in GPU memory, so storage principles
> transfer directly.

**Project action if the answer remains weak**

Pause feature growth and close the inference-fundamentals gap before packaging
the project for interviews.

## Q16. If Static TTL Wins, Did the Project Fail?

**State:** `draft`

**TL challenge**

> Suppose a tuned static policy matches or beats your dynamic policy. What remains
> of the project?

**What this tests**

Scientific honesty and whether success was defined only as producing an uplift.

**Recommended answer**

> The policy hypothesis would be falsified for that tested regime, but the project
> would not automatically be worthless. A rigorous result can still establish the
> measured cost curves, the reachable action regions, the complexity threshold,
> and why static control is sufficient under stable workloads. If all reachable
> workloads collapse to one dominant action, I stop policy expansion and publish
> the measurement and feasibility result rather than manufacturing a win.

**Likely follow-ups**

- What is the pre-registered stop condition?
- Would you still put the dynamic policy in the resume bullet?
- Which roadmap branch would you pivot to?

**Evidence gate**

- Go/no-go and pivot conditions in [../ROADMAP.md](../ROADMAP.md).
- Preserved negative runs and unchanged pre-registration.
- Resume bullet rewritten to match the actual result.

**Dangerous answer**

> We would tune the policy further until it wins.

**Project action if the answer remains weak**

Do not begin the full implementation until falsification and pivot conditions are
accepted.

## Q17. Why vLLM Rather Than SGLang or Another Inference Engine?

**State:** `draft`

**TL challenge**

> SGLang has RadixAttention and HiCache and is widely used for agent and shared-
> prefix workloads. Why did you choose vLLM? Was it a technical decision or just
> familiarity and popularity?

**What this tests**

Whether engine selection follows from the causal question, ownership boundary,
and implementation constraints rather than ecosystem fashion or post-hoc
rationalization.

**Recommended answer**

> I do not claim that vLLM is universally better for agent serving. SGLang has a
> stronger out-of-the-box story for radix-tree prefix reuse and hierarchical KV
> caching through HiCache. It would be the more direct choice if my goal were to
> reproduce PBKV, extend workflow prediction, or maximize an SGLang-native agent
> workload.
>
> My main question is narrower: when a tool-paused request should retain,
> offload, or recompute its KV state. I need one real engine with a trustworthy
> HBM-to-DRAM data path, per-request policy hooks, scheduler observability, and a
> manageable integration surface. vLLM provides native CPU KV offload, pluggable
> cache-policy infrastructure, and evolving per-request offload lifecycle hooks.
> That lets me reuse the transfer mechanism while owning tool-wait/resume state,
> decision logic, fallback, and DecisionTrace instead of reimplementing tensor
> movement.
>
> Choosing SGLang first would also couple the experiment to RadixAttention,
> HiCache write/prefetch semantics, and existing PBKV-style workflow prediction.
> That is useful for a different question, but it makes it harder to isolate
> whether lifecycle selection itself caused the result and increases the risk
> that my project becomes a shallow variant of existing SGLang work.
>
> The vLLM choice is provisional rather than ideological. Context-aware
> retention is not yet a stable assumption, so the calibration sprint must prove
> that tool-wait/resume, per-request action selection, bounded retention, and
> actual block outcomes can be expressed through supported hooks or a small,
> isolated patch. If that requires a broad scheduler or allocator fork, I will
> narrow the study to offload-versus-recompute or move the lifecycle experiment
> to SGLang instead of defending the original engine choice.

**Decision matrix**

| Criterion | vLLM | SGLang |
|---|---|---|
| Native lower-tier KV mechanism | Native CPU and multi-tier offload are available | HiCache provides a richer hierarchical-cache path |
| Agent/shared-prefix specialization | Prefix caching exists, but is not the main selection reason | RadixAttention and HiCache are stronger native primitives |
| Collision with existing workflow policy work | Lower for an independent runtime study | Higher because PBKV and related policies already build on this stack |
| Candidate ownership opportunity | Tool-gap lifecycle semantics and tracing remain explicit work | More cache lifecycle behavior may already be supplied by the engine |
| Causal isolation | Easier to hold one offload mechanism fixed | Radix, hierarchy, prefetch, and policy can become simultaneous variables |
| Primary implementation risk | Retention and pause/resume contracts may require unsupported changes | Fidelity to existing HiCache/PBKV semantics may dominate the work |
| Best-fit project | vLLM runtime integration and decision-boundary study | SGLang agent-serving optimization or PBKV reproduction/extension |

**Likely follow-ups**

- What exact vLLM hook receives information at tool wait and at resume?
- Is vLLM's `CachePolicy` a CPU-tier replacement policy or your request-level
  lifecycle policy? Do not conflate the two.
- Why does choosing an engine with a missing retention API improve ownership
  rather than merely manufacture work?
- Which calibration result would trigger a move to SGLang?
- Why not implement both engines to demonstrate generality?
- Why not TensorRT-LLM, llama.cpp, Ray Serve, or AIBrix?

**Evidence gate**

- Pinned vLLM commit with a source-level hook and data-path audit.
- Calibration trace proving tool-wait, resume, and actual offload outcomes are
  observable in the selected version.
- A written change-surface estimate distinguishing supported extension points
  from core scheduler or allocator modifications.
- Explicit pivot criteria in [../ROADMAP.md](../ROADMAP.md).
- Engine comparison based on a small capability spike, not README feature lists
  alone.
- Primary references: [vLLM CPU offload PR](https://github.com/vllm-project/vllm/pull/37874),
  [vLLM releases](https://github.com/vllm-project/vllm/releases),
  [vLLM retention RFC](https://github.com/vllm-project/vllm/issues/37003),
  [SGLang HiCache arguments](https://github.com/sgl-project/sglang/blob/main/docs/advanced_features/server_arguments.md),
  and [PBKV](https://arxiv.org/abs/2605.06472).

**Dangerous answers**

> vLLM is more mature and has a larger ecosystem.

> vLLM did not have the feature, so it gave me more code to write.

> SGLang is optimized for agents, but vLLM is faster overall.

These answers either lack a mechanism, manufacture ownership from a missing
feature, or make an unscoped performance claim.

**Project action if the answer remains weak**

Treat engine selection as unresolved. Run the calibration spike before writing
`vLLM runtime` into the final resume bullet. If the engine choice does not change
the hypothesis or owned evidence, describe vLLM as the testbed rather than a
project contribution.

## 2. Five-Minute Authenticity Test

A TL can quickly distinguish a real owner from a concept-only candidate with this
chain:

1. **Derive KV memory.** Explain
   `2 * layers * num_kv_heads * head_dim * dtype_bytes` per token before parallel
   partitioning, then reconcile the estimate with the tested model and runtime.
2. **Trace one request.** Start at tool-call emission and name every modified
   runtime transition through retain, offload, restore, or recompute.
3. **Remove candidate code.** State exactly which behavior and metric disappear.
4. **Explain the data path.** Cover pinned host memory, asynchronous copies,
   streams, synchronization, capacity reservation, and transfer contention.
5. **Debug one failure.** Show symptom, competing hypotheses, instrumentation,
   root cause, fix, and regression test.
6. **Name a losing regime.** Explain why the selected policy should disable itself
   there.

Generic definitions or framework lists do not pass this test.

## 3. Final TL Grading Boundary

### Strong Candidate Signal

```text
real in-process runtime diff
explicit dependency/ownership boundary
state-machine and failure correctness
fair tuned baselines
system-level metrics and negative cases
reproducible raw artifacts
honest related-work and validity boundary
```

### Borderline Signal

```text
external controller only
mostly synthetic workloads
correct concepts but weak runtime ownership
single winning metric
no concrete failure/debugging story
```

### Reject Signal

```text
claims dependency features as personal work
cannot derive KV size or trace the engine path
uses weak or test-tuned baselines
calls simulation production validation
hides negative workloads
describes roadmap components as completed
```

The defensible project label is:

> **A vLLM tool-gap KV lifecycle runtime and decision-boundary study.**

The label to avoid is:

> **A new production-ready intelligent distributed KV-cache scheduling system.**
