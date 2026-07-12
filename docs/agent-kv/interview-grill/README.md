# ToolGap-KV Interview Grill

> Project claim state: `roadmap`
>
> Last reviewed: 2026-07-11
>
> The answers in this directory are evidence-gated templates. They are not
> completed-project claims and must not be recited in completed tense until the
> linked implementation or experiment exists.

## 1. Purpose

This directory turns adversarial interview questions into a maintenance loop:

```text
interviewer challenge
-> expose a knowledge, implementation, evidence, or positioning gap
-> change the project or narrow the claim
-> attach a concrete artifact
-> rehearse the evidence-backed answer
```

It is not a list of polished phrases to memorize. A strong answer must connect
the question to owned code, a measured result, a trace, a failed experiment, or
an explicit validity boundary.

## 2. Reading Order

1. [01-tl-adversarial-review.md](01-tl-adversarial-review.md): the initial
   inference-team TL review, model answers, follow-up questions, and evidence
   gates.
2. [SESSION_TEMPLATE.md](SESSION_TEMPLATE.md): a reusable record for future mock
   interviews and real interview retrospectives.
3. [../NARRATIVE.md](../NARRATIVE.md): the externally presented project story.
4. [../EVALUATION.md](../EVALUATION.md): the experiment protocol required to
   support performance answers.
5. [../RELATED_WORK.md](../RELATED_WORK.md): the novelty and prior-work boundary.

## 3. Question States

Every question uses one of these interview-preparation states:

| State | Meaning |
|---|---|
| `unanswered` | No coherent technical answer exists yet |
| `draft` | The reasoning is coherent, but required project evidence is missing |
| `evidence-backed` | The answer links to exact code, tests, traces, or raw results |
| `invalidated` | Implementation or experiments disproved the previous answer |
| `retired` | The project scope changed and the question no longer applies |

These states do not replace the project claim states `roadmap`, `shipped`,
`experimentally validated`, and `simulated` defined in
[../README.md](../README.md). A question can be `evidence-backed` for a shipped
correctness claim while its performance claim remains unmeasured.

## 4. Entry Contract

Each maintained question should contain:

```text
question ID and state
TL challenge
what the interviewer is actually testing
recommended answer
likely follow-up chain
minimum evidence required
dangerous answer patterns
project change triggered by the question
```

If the recommended answer changes, preserve the reason in the session record or
[../DECISIONS.md](../DECISIONS.md). Do not silently rewrite history after an
experiment fails.

## 5. Initial Question Index

| ID | Theme | Initial state | Source |
|---|---|---|---|
| Q01 | Collision with prior work | `draft` | [Initial review](01-tl-adversarial-review.md#q01-existing-work-already-does-this-what-is-your-contribution) |
| Q02 | Engineering versus research | `draft` | [Initial review](01-tl-adversarial-review.md#q02-is-this-too-engineering-heavy-to-count-as-a-research-project) |
| Q03 | Agent-specificity | `draft` | [Initial review](01-tl-adversarial-review.md#q03-is-this-really-agent-aware-or-just-generic-paused-request-management) |
| Q04 | Candidate ownership | `draft` | [Initial review](01-tl-adversarial-review.md#q04-vllm-already-has-offload-and-policy-hooks-what-did-you-code) |
| Q05 | Retain semantics | `draft` | [Initial review](01-tl-adversarial-review.md#q05-is-retain-just-doing-nothing) |
| Q06 | Cost model and global effects | `draft` | [Initial review](01-tl-adversarial-review.md#q06-how-do-you-price-hbm-opportunity-cost-and-system-wide-interference) |
| Q07 | Workload provenance | `draft` | [Initial review](01-tl-adversarial-review.md#q07-did-you-manufacture-a-workload-that-makes-your-policy-win) |
| Q08 | Baseline fairness | `draft` | [Initial review](01-tl-adversarial-review.md#q08-why-is-a-tuned-static-ttl-not-enough) |
| Q09 | Metric substitution | `draft` | [Initial review](01-tl-adversarial-review.md#q09-did-you-improve-resume-ttft-by-hurting-everyone-else) |
| Q10 | Lifecycle correctness | `draft` | [Initial review](01-tl-adversarial-review.md#q10-how-do-you-handle-resume-cancel-and-transfer-races) |
| Q11 | Hardware validity | `draft` | [Initial review](01-tl-adversarial-review.md#q11-why-should-results-from-one-gpu-generalize) |
| Q12 | Oracle misuse | `draft` | [Initial review](01-tl-adversarial-review.md#q12-is-your-oracle-infeasible-or-misnamed) |
| Q13 | Complexity budget | `draft` | [Initial review](01-tl-adversarial-review.md#q13-is-the-dynamic-policy-worth-its-complexity) |
| Q14 | Scale overclaim | `draft` | [Initial review](01-tl-adversarial-review.md#q14-why-do-you-call-a-single-node-study-a-production-kv-system) |
| Q15 | Concept laundering | `draft` | [Initial review](01-tl-adversarial-review.md#q15-how-do-i-know-you-understand-ai-infra-rather-than-repeating-papers) |
| Q16 | Negative result | `draft` | [Initial review](01-tl-adversarial-review.md#q16-if-static-ttl-wins-did-the-project-fail) |
| Q17 | Engine-selection trade-off | `draft` | [Initial review](01-tl-adversarial-review.md#q17-why-vllm-rather-than-sglang-or-another-inference-engine) |

## 6. Maintenance Workflow

After each implementation milestone or mock interview:

1. Copy [SESSION_TEMPLATE.md](SESSION_TEMPLATE.md) into a dated session file.
2. Preserve the raw answer before editing it into a polished answer.
3. Classify each gap as knowledge, implementation, evidence, or positioning.
4. Update the underlying project document before updating the interview answer.
5. Add exact artifact paths and commands only after they exist and are verified.
6. Change a question to `evidence-backed` only when another engineer can inspect
   or reproduce the supporting artifact.
7. Keep losing workloads and invalidated explanations; they are evidence of
   scientific discipline, not material to hide.

## 7. Pass Standard

The project is interview-defensible only when the candidate can sustain a
20-minute discussion that includes:

```text
one request traced through the modified runtime path
one quantitative retain/offload/recompute break-even argument
one rejected design
one correctness failure and regression test
one fair baseline and one ablation
one workload where the dynamic policy loses
an exact ownership boundary between candidate code and dependencies
```
