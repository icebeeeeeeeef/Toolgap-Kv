# Interview-First Project Principles

> Status: `roadmap`
>
> Last reviewed: 2026-07-14
>
> Governance status: adopted on 2026-07-13
>
> These principles define how ToolGap-KV chooses scope and evidence. They do
> not claim that the runtime, experiments, or interview evidence already exist.

## 1. Primary Purpose

ToolGap-KV is first a work sample for LLM serving, inference-runtime, and AI
infrastructure engineering roles. Its purpose is to provide inspectable evidence
that the candidate can:

```text
read and modify a real inference runtime
identify the correct integration contract
reason about state, concurrency, pressure, and failure
compare alternatives through reproducible tests
explain both positive and negative results
transfer storage data-plane judgment into inference infrastructure
```

Publishing a novel mechanism is optional. Demonstrating owned engineering
judgment is mandatory.

### Recruiting Lens

This lens must be rechecked before every material roadmap change:

| Constraint | Frozen value |
|---|---|
| Candidate | 2027 campus-recruiting candidate |
| Target | LLM Serving / inference platform / AI Infra engineering; not research, kernel, or operator ownership |
| Existing advantage | ByteDance object-storage data-plane experience: tiering, transfer queues, backpressure, partial failure, and tail latency |
| Project role | Translate the profile from storage backend toward inference serving; do not replace the internship story |
| Time | About 20 hours/week |
| Hardware | One 24 GB consumer GPU; no required multi-node environment or production traffic |
| Interview objective | Produce a work sample that can survive a 45-minute source-, failure-, and measurement-level drill-down |

## 2. Evaluation Model

Project value is governed by hard credibility gates and then evaluated as:

```text
interview project value
  = hands-on credibility
  x trade-off narrative density
  x organic depth-hook coverage
  x candidate-pool differentiation floor
```

Score each dimension from 1 to 10. Differentiation stops adding value after it
clears a floor of 6:

```text
score = 100 * [
  (credibility / 10)
  * (tradeoff_density / 10)
  * (hook_coverage / 10)
  * min(1, differentiation / 6)
] ^ (1 / 4)
```

The score is subordinate to gates and must be reported twice:

- **current evidence score:** counts only repository artifacts that exist now;
- **conditional attainable score:** a planning estimate if named evidence is
  delivered, never presented as a current achievement.

An investment decision also reports evidence-conversion risk under the declared
time, hardware, and workload constraints. This prevents a new project from being
rejected merely because its planned measurements do not exist yet while still
preventing roadmap work from receiving achieved credit.

### Credibility Gates

Every material project claim must satisfy all applicable gates:

1. **Owned execution:** the candidate can point to the code, test, trace, or
   experiment they personally produced.
2. **Reproducible evidence:** important choices are supported by a command,
   fixture, raw result, or deterministic failure reproduction.
3. **Honest attribution:** dependency behavior, paper results, and candidate
   work are named separately.
4. **Declared validity:** hardware, workload, runtime commit, and known limits
   accompany any measured conclusion.
5. **Correct claim state:** `roadmap`, `shipped`, `experimentally validated`,
   and `simulated` retain the meanings defined in [README.md](README.md).
6. **Owned runtime mechanism:** CT1-CT3 completion includes a candidate-owned,
   in-process logical lifecycle controller. Instrumentation that only observes
   vLLM-owned decisions cannot satisfy this gate.

A polished explanation does not compensate for a missing gate.

An honesty failure invalidates the current wording or packaging. It does not
automatically make the underlying engineering useless; correct the positioning
and rerun the review. An unsupported trade-off simply does not count.

### Scored Dimensions

1. **Hands-on credibility:** artifacts resemble target-team work: a pinned real
   engine integration or patch, regression/fault tests, traces, diagnosis, and
   benchmark evidence rather than a toy framework or paper-style report.
2. **Trade-off narrative density:** count closed decision cards. A planned card
   has no value until measurement or deterministic fault evidence closes it.
3. **Organic depth-hook coverage:** count only target-role topics reached through
   owned code, a measured decision, or a closed card. Naming an adjacent topic is
   not a hook.
4. **Candidate-pool differentiation:** clear the floor above RAG/Agent apps and
   tutorial engine rewrites, then stop optimizing for uniqueness.

Role overlap, ownership, transferability, and credibility are tested through
these dimensions and the hard gates rather than rewarded as keyword count.

### Current Review Snapshot

As of 2026-07-14:

| Item | Current assessment |
|---|---|
| Verdict | `修方案后做` has been completed at document level; execute Gate A before committing the full project |
| Hands-on credibility | 3/10: local contracts/tests exist, but no real-engine work sample |
| Trade-off narrative density | 1/10: no decision card is closed |
| Organic hook coverage | 1/10: planned hooks receive no evidence credit |
| Pool differentiation | 6/10: the direction clears the common application/tutorial floor, with no extra uniqueness reward |
| Current evidence score | approximately 23/100 under the declared formula |
| Conditional attainable vector | 8/10, 8/10, 7/10, 6/10 if CT1-CT3, five cards, and real measurements close |
| Conditional attainable score | approximately 82/100; this is a planning ceiling, not a current claim |
| Principal conversion risk | whether a current-vLLM seam allows one non-duplicative candidate-owned lifecycle transition/fallback plus attributable outcomes on one 24 GB GPU without a broad fork |

The low current score is not averaged away by polished documents. Gate A exists
to convert the first roadmap card into real evidence or stop the project early.

## 3. Technical First Principle: KV Is Derived State

The token sequence and compatible model/runtime configuration are authoritative.
KV blocks in GPU HBM or CPU DRAM are derived materializations that may be retained,
moved, invalidated, or recomputed.

This creates a useful analogy with data migration:

| Data migration concept | ToolGap-KV concept |
|---|---|
| Authoritative source record | Token history and compatible runtime identity |
| Materialized destination copy | GPU- or CPU-resident KV blocks |
| Partial commit or stale replica | Partial transfer or stale lifecycle completion |
| Repair from current source state | Recompute from the current token sequence |
| Load-sensitive migration rate | Transfer admission under decode, HBM, and link pressure |
| Cutover state machine | Wait, store, restore, resume, cancel, and fallback transitions |

The important difference is that KV is intentionally recomputable. Recovery may
therefore reject or discard a damaged materialization and regenerate it instead
of repairing it in place.

## 4. Three Contract Trunks

The project is organized around three contracts, not around a list of
technologies.

### Integration Contract

Answer why the chosen vLLM extension point is the smallest place that can own
the required semantics:

```text
what lifecycle state the hook observes
what state the connector and scheduler each own
when a transfer result becomes visible
why an external proxy, old paper fork, or broad core patch is insufficient
how ordinary requests remain on the default path
```

The required ownership is logical, not physical. Candidate code must own
lifecycle claims/epochs, legal transitions, idempotence, asynchronous-completion
fencing, action orchestration, fallback, cancellation, cleanup, and DecisionTrace.
It should reuse vLLM's shared-block/refcount rules, eviction, PagedAttention,
model execution, and native D2H/H2D transfer. Gate A decides whether this fits a
supported extension or needs a small auditable patch; it does not allow a
logging-only path to replace the controller.

### Correctness and Recovery Contract

Define safe reuse and fallback:

```text
cache identity and token compatibility
monotonic lifecycle epochs
partial store or load failure
cancel during asynchronous transfer
duplicate resume and late completion
failed-block invisibility
fallback recompute and output equivalence
```

### Performance Control Contract

Explain when optimization should proceed, wait, or disable itself:

```text
offload versus recompute break-even
transfer contention with active decode
HBM and CPU-tier capacity pressure
restore queue ordering and bounded concurrency
batch-size versus wait-time trade-offs
resume bursts and tail latency
negative regions where static behavior is preferable
```

A lifecycle policy may connect these trunks, but policy novelty is not required
to make the project successful.

## 5. Unit of Progress

The unit of progress is a closed decision card:

```text
background
+ at least two real alternatives
+ falsifiable expectation
+ real measurement or deterministic fault evidence
+ selected decision
+ rejected alternative and losing boundary
+ exact artifact links
+ one reproduction command
+ one organic follow-up tree
```

An artifact pack contains, as applicable:

```text
runtime patch or extension
regression or fault-injection test
raw trace or benchmark result
decision or incident note
explicit validity boundary
```

Question trees and artifacts are paired deliverables. A question tree without
artifacts is rehearsal; an artifact without a defensible decision narrative is
an underused work sample.

Milestones do not multiply card counts by hook counts because that can reward one
shallow card duplicated across topics. Track them as separate gates. The target
is at least five closed cards and organic coverage of at least half of the
JD-calibrated Serving/KV knowledge set.

## 6. Role of Prior Art

Prior art is used to:

- prevent false novelty and ownership claims;
- select strong baselines and implementation references;
- explain rejected alternatives;
- identify conditions worth reproducing or stress-testing;
- demonstrate research discipline during an interview.

Prior work does not automatically invalidate an interview project. Reproduction
is valuable when it produces owned implementation, current-runtime evidence,
failure analysis, or a measured boundary. A paper covering the same high-level
mechanism changes positioning and baseline requirements before it changes scope.

## 7. Scope Rules

1. Prefer three or four deep evidence-backed question trees over broad feature
   coverage, while retaining at least five closed engineering decisions across
   those trees.
2. Add a feature only when it closes a real contract gap or produces a measured
   decision.
3. Keep adjacent topics such as MLA or speculative decoding outside the project
   unless a real implementation or experiment creates an organic connection.
4. Do not require a faithful port of an old paper fork when a paper-inspired
   baseline on pinned current vLLM answers the engineering question more directly.
5. Preserve negative results when they demonstrate diagnosis, boundary finding,
   or sound stopping judgment.
6. Stop expanding a branch when it cannot produce candidate-owned evidence or a
   natural follow-up beyond technology-name coverage.
7. Rebuild the hook denominator from representative target JDs when the hiring
   market or target role changes. Do not force MLA/GQA, speculative decoding, or
   kernel work into a serving/KV project merely to improve coverage.
8. An upstream issue or PR is a bonus. External acceptance is not an owned
   milestone and must not become a project success gate.

## 8. Interview-Ready Success Condition

The project is interview-ready when it provides:

```text
one pinned current-vLLM integration
one request traced through the owned runtime path
three evidence-backed core question trees
at least five closed decision cards
at least half of the target Serving/KV hooks reached organically
one rejected design with concrete reasons
one correctness failure or injected failure with a regression test
one negative performance or applicability result
one exact ownership and validity boundary
```

This is a work-sample threshold, not a publication threshold. An upstream issue,
PR, or novel result is useful additional evidence but is not a prerequisite.

## 9. Document Responsibilities

- [PROJECT.md](PROJECT.md) defines the technical problem and falsifiable questions.
- [ARCHITECTURE.md](ARCHITECTURE.md) defines runtime contracts and invariants.
- [EVALUATION.md](EVALUATION.md) defines acceptable evidence.
- [INTERVIEW_MAP.md](INTERVIEW_MAP.md) maps future claims to follow-ups and
  evidence gates.
- [interview-grill/README.md](interview-grill/README.md) records adversarial
  practice and real interview retrospectives.
- [DECISIONS.md](DECISIONS.md) records scope changes when evidence alters a major
  project choice.

## 10. Adopted Governance

The user adopted this specification on 2026-07-13. The project therefore uses:

1. interview-ready engineering evidence as the project-level success function;
2. retain/offload/recompute as the bounded technical scenario;
3. CT1 integration, CT2 correctness/recovery, and CT3 measured boundary as the
   unconditional mainline;
4. dynamic-policy superiority only as conditional CT4 after Gate B;
5. one work sample, closed-card update, and claim-state audit per roadmap gate;
6. append-only decision and negative-result history when evidence changes scope.
