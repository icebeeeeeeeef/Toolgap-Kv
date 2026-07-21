# Issue tracker: GitHub

Issues, PRDs, and Wayfinder maps for this repository live in GitHub Issues at
`icebeeeeeeeef/Toolgap-Kv`. Use the `gh` CLI for all operations and pass
`-R icebeeeeeeeef/Toolgap-Kv` explicitly so commands are unambiguous.

The repository is public. Treat every issue title, body, comment, attachment,
and relationship as public information. Do not publish credentials, private
notes, employer data, or unreviewed resume claims.

## Authentication preflight

Before a session that reads or writes GitHub state, run:

```bash
gh auth status --hostname github.com
```

If authentication has expired, restore it with:

```bash
gh auth login --hostname github.com --git-protocol https --web
```

Do not infer success from the browser alone; re-run the status command.

## General operations

- Create: `gh issue create -R icebeeeeeeeef/Toolgap-Kv --title "..." --body "..."`
- Read: `gh issue view <number> -R icebeeeeeeeef/Toolgap-Kv --comments`
- List: `gh issue list -R icebeeeeeeeef/Toolgap-Kv --state open`
- Comment: `gh issue comment <number> -R icebeeeeeeeef/Toolgap-Kv --body "..."`
- Edit labels: `gh issue edit <number> -R icebeeeeeeeef/Toolgap-Kv --add-label "..."`
- Claim: `gh issue edit <number> -R icebeeeeeeeef/Toolgap-Kv --add-assignee '@me'`
- Close: `gh issue close <number> -R icebeeeeeeeef/Toolgap-Kv --comment "..."`

When a skill says to publish an issue or PRD, create a GitHub issue. When it
says to fetch a ticket, read the issue and its comments.

## Wayfinding operations

Use these labels:

| Label | Meaning |
| --- | --- |
| `wayfinder:map` | Canonical Wayfinder map |
| `wayfinder:research` | AFK investigation of external or local evidence |
| `wayfinder:prototype` | HITL rough artifact used to make a decision concrete |
| `wayfinder:grilling` | HITL decision resolved one question at a time |
| `wayfinder:task` | Work that must happen before a decision can be made |

Create the canonical map first. Create child tickets in a first pass, then add
dependencies in a second pass after every issue has an identity.

### Parent and child issues

Create a child under a map:

```bash
gh issue create -R icebeeeeeeeef/Toolgap-Kv \
  --parent <map-number> \
  --title "..." \
  --body "..." \
  --label "wayfinder:grilling"
```

Attach an existing issue as a child:

```bash
gh issue edit <map-number> -R icebeeeeeeeef/Toolgap-Kv \
  --add-sub-issue <child-number>
```

Inspect the map's children:

```bash
gh issue view <map-number> -R icebeeeeeeeef/Toolgap-Kv \
  --json subIssues,subIssuesSummary
```

### Blocking relationships

Declare that one issue is blocked by another:

```bash
gh issue edit <blocked-number> -R icebeeeeeeeef/Toolgap-Kv \
  --add-blocked-by <blocker-number>
```

Use GitHub's native relationship. Do not encode blockers only in issue prose.

### Frontier

The Wayfinder frontier is the map's direct child issues that are open,
unassigned, and have no open blocker. Query it in one pass:

```bash
gh api graphql \
  -F owner=icebeeeeeeeef \
  -F repo=Toolgap-Kv \
  -F number=<map-number> \
  -f query='query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){issue(number:$number){subIssues(first:100){nodes{number title url state assignees(first:1){totalCount} blockedBy(first:50){nodes{state}}}}}}}' \
  --jq '.data.repository.issue.subIssues.nodes[] | select(.state=="OPEN" and .assignees.totalCount==0 and ([.blockedBy.nodes[]|select(.state=="OPEN")]|length)==0) | {number,title,url}'
```

GitHub currently permits at most 100 direct sub-issues per parent, eight levels
of nesting, and 50 dependencies in either direction. Split the effort rather
than relying on truncated queries if a map approaches those limits.

### REST fallback

The installed `gh` version supports native sub-issue and dependency flags. If a
future CLI regression requires REST, send the API version header
`X-GitHub-Api-Version: 2026-03-10` and use:

- `GET` / `POST repos/{owner}/{repo}/issues/{map}/sub_issues`
- `DELETE repos/{owner}/{repo}/issues/{map}/sub_issue`
- `GET` / `POST repos/{owner}/{repo}/issues/{blocked}/dependencies/blocked_by`
- `DELETE repos/{owner}/{repo}/issues/{blocked}/dependencies/blocked_by/{issue_id}`
- `GET repos/{owner}/{repo}/issues/{blocker}/dependencies/blocking`

REST relationship payloads use database issue IDs, not visible issue numbers.

## Human-readable references

In map bodies, comments, and user-facing narration, refer to issues by a linked
title, never by a bare issue number. The title carries meaning; the number is
only an implementation detail inside the link.
