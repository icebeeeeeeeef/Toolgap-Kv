# Triage labels

The engineering skills use five canonical triage roles. This table maps them to
the labels configured in this repository.

| Canonical role | Repository label | Meaning |
| --- | --- | --- |
| `needs-triage` | `needs-triage` | Maintainer must evaluate the issue |
| `needs-info` | `needs-info` | Waiting for information from the reporter |
| `ready-for-agent` | `ready-for-agent` | Fully specified and safe for AFK agent work |
| `ready-for-human` | `ready-for-human` | Requires human implementation or judgment |
| `wontfix` | `wontfix` | Will not be actioned |

When a skill names a role, use the corresponding repository label. An issue
should have at most one of these state labels at a time unless a transition is
being repaired.
