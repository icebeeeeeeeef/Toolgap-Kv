# Interview Grill Session

> Copy this file to `sessions/YYYY-MM-DD-<interviewer-or-theme>.md`.
>
> Preserve raw answers before polishing them.

## 1. Session Metadata

| Field | Value |
|---|---|
| Date | `[record at session time]` |
| Interviewer or reviewer | `[name or role]` |
| Target role | `[LLM serving/runtime/platform]` |
| Project version | `[document revision or commit]` |
| vLLM commit and patch | `[exact revision when available]` |
| Hardware and model | `[exact environment when relevant]` |
| Question IDs covered | `[Q01, Q02, ...]` |

## 2. Overall Verdict

| Dimension | Rating | Evidence or reason |
|---|---|---|
| Role relevance | `[strong/mixed/weak]` | `[record]` |
| Ownership | `[strong/mixed/weak]` | `[record]` |
| Runtime depth | `[strong/mixed/weak]` | `[record]` |
| Research discipline | `[strong/mixed/weak]` | `[record]` |
| Evidence quality | `[strong/mixed/weak]` | `[record]` |
| Credibility | `[strong/mixed/weak]` | `[record]` |

## 3. Question Records

Duplicate this section once per question.

### Question `[ID and short title]`

**Interviewer wording**

> `[preserve the exact challenge]`

**Raw answer given during the session**

> `[preserve before editing]`

**Follow-up chain**

1. `[follow-up]`
2. `[follow-up]`
3. `[follow-up]`

**Where the answer weakened**

`[name the first unsupported step, not merely the final difficult question]`

**Gap classification**

- Knowledge: `[specific concept or engine path]`
- Implementation: `[missing behavior or test]`
- Evidence: `[missing trace, run, code anchor, or artifact]`
- Positioning: `[overclaim, vague ownership, or wrong project label]`

**Evidence available**

| Claim | Claim state | Artifact | Reproduction command | Validity boundary |
|---|---|---|---|---|
| `[claim]` | `[roadmap/shipped/experimentally validated/simulated]` | `[exact path or none]` | `[exact command or none]` | `[scope]` |

**Revised answer**

> `[rewrite only after fixing the underlying gap or narrowing the claim]`

**Question-state decision**

`[unanswered/draft/evidence-backed/invalidated/retired]`

## 4. Project Changes Triggered

| Priority | Change | Target document or module | Evidence required | Status |
|---|---|---|---|---|
| P0 | `[correctness or credibility blocker]` | `[path]` | `[artifact]` | `[open/complete]` |
| P1 | `[depth or experiment gap]` | `[path]` | `[artifact]` | `[open/complete]` |
| P2 | `[wording or presentation improvement]` | `[path]` | `[artifact]` | `[open/complete]` |

## 5. Claim Audit

Before updating the resume or narrative, answer all five:

1. Did any answer claim a dependency feature as candidate-owned work?
2. Did any answer turn a roadmap, simulation, or proxy result into a real-system
   claim?
3. Did any metric omit the baseline, environment, workload, or validity boundary?
4. Did the session reveal a stronger baseline or negative case that must be added?
5. Did any project term such as `agent-aware`, `runtime`, `oracle`, `distributed`,
   or `production` become indefensible?

Record the conclusion:

`[claims unchanged / claims narrowed / project scope changed]`

## 6. Next Rehearsal Gate

The next session should not repeat the same polished answer until the highest
priority gap has one of these outcomes:

```text
knowledge gap -> derivation or source-level walkthrough completed
implementation gap -> code and regression test exist
evidence gap -> reproducible artifact exists
positioning gap -> narrative and resume claim are narrowed
```
