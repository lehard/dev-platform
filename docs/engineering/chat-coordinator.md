# Chat coordinator

The **chat coordinator** is a role the owner can assign to any new Codex or Claude
session. It is an *observer and exception operator* for Dev Platform delivery: it
tells the owner, in ordinary words, where every Requirement and PR stands, why it
is waiting, and what the next step is. It is not the CI *publication coordinator*
(the App that runs `publication-queue`), and it is not an executor of review,
repair or merge. Those stages continue without it.

Nothing here needs a persistent chat, a second state store, a dedicated dispatcher
model, a dashboard or a new owner step on the happy path. A new chat reproduces
the same picture from GitHub.

## Reading the state

Always start from the read-only overview, which writes nothing:

```bash
python3 scripts/lifecycle_overview.py                       # all candidates and open Requirements
python3 scripts/lifecycle_overview.py show --pr N           # one PR: chain, attempts, executor, findings
python3 scripts/lifecycle_overview.py show --requirement owner/repo#N
python3 scripts/lifecycle_overview.py --json show --pr N    # same data, machine-readable
```

It requires `[chat_coordinator] unclaimed_job_after_minutes` in `.dev-platform.toml`
(committed in `dev-platform/source-contract.toml`; the installed, locally excluded
`.dev-platform.toml` must carry the same value) and fails naming the key when it
is missing. It considers the candidate set the
lifecycle workers consider (open PRs plus one bounded page of recently merged
PRs) and states that bound.

Stages:

| Stage | Meaning |
| --- | --- |
| `in-development` | Requirement exists, no PR has been handed off yet |
| `handed-off` | Developer handoff recorded; no executor has picked it up yet (within the threshold) |
| `delivering` | A review/repair/finalize/integration step is claimed, queued or running its automatic course |
| `merged-open-obligations` | The PR is merged, but retrospective, terminal reconciliation or cleanup is open, or the Requirement is not `Done` |
| `closed` | Merged with nothing open; the Requirement is `Done` |
| `needs-intervention` | A named exception applies (below) |
| `unknown` | A required source is unreadable or contradictory; never read as healthy |

The chain shown for one item is review, repair, re-review, finalize, integration,
retrospective, terminal reconciliation, cleanup, with the current step and the
attempt counters from the lifecycle record. "Merged" and "Requirement `Done`" are
reported separately. A green `publication-queue` run with state `waiting` is not
a merge.

Executor: the overview names a worker only from a valid claim and then still says
`executor activity: not confirmed`. A claim proves intent, not execution; say
"claimed by X until T, activity not confirmed" and never "running". Without a
claim it says `executor not confirmed`. An activity signal from BR-610/BR-433 is
reported only when it exists and is bound to the exact job and head.

Exceptions it names: `unclaimed-next-job`, `expired-claim`, `stale-head`,
`provider-unavailable`, `escalated-operational`, `escalated-finding` (including
exhausted repair or review rounds), `escalated-other`, `post-merge-exhausted` and
`unknown-source`. Each cites its evidence.

## Acting on an exception

The overview prints, per item, either the permitted commands or the human
decision that is needed. The permitted list is computed by the same eligibility
function as the commands and is limited to `resume` and `switch-provider`:

```bash
python3 scripts/publication_queue.py resume --pr N --expected-head <head> --via chat-coordinator --reason "<why>"
python3 scripts/publication_queue.py switch-provider --pr N --provider <provider> --expected-head <head> --via chat-coordinator --reason "<why>"
```

A candidate in `finalize-pending`, `review-pending` or `blocked-retryable` whose
admission gates were lost across the harness's own review-evidence pushes (for
example finalization stops at "fresh semantic verification required" although
the task content is unchanged) is repaired with:

```bash
python3 scripts/publication_queue.py restore-gates --pr N --expected-head <head>
```

It restores only gates proven bound to the current task content through a
chain of trusted harness pushes, keeps the state, and refuses naming the head
where the proof breaks. It runs no review, takes no claim and rewrites no
history. If it refuses, report the reason; the developer re-handoff rules apply.
When the finalize job of that head already holds a result (it stopped on the
lost gates), the same record re-offers finalize under a fresh job id. A
`finalize-pending` candidate whose finalize job already holds a result and has
no fresh job is re-offered with `resume`.

Rules:

- Run one only after the owner explicitly says to (for example "continue" or
  "switch to claude") for that PR. Use the head from the report as
  `--expected-head`; a changed head makes the command refuse before writing.
- Never bypass a live claim, a required check or branch protection, and never
  touch another agent's state, worktree or scope.
- The command records the reason, the authenticated actor, `via`, PR and exact
  head in the candidate record on GitHub. Report its result as it is.
- A material finding, exhausted review/repair rounds, a disputed rejection or
  disposition, or a needed OpenSpec or business change is **not** yours to
  approve or retry. Show the finding and its basis, name the human options the
  overview lists (push a fix, record a disposition, close the PR) and ask the
  owner. If the supported contract cannot apply the owner's decision safely,
  say so; do not simulate success.
- Retries and recovery the platform performs by itself need no message to you.

## What GitHub shows without you

When a candidate becomes `blocked-escalation` (and when a post-merge obligation
spends its attempts), the coordinator posts one human-readable comment on the
PR with the reason, evidence and the permitted action or needed decision, once
per exact escalation. Successful stages post nothing, so ordinary GitHub
notifications stay quiet on the happy path. Final Requirement closure is the
existing close of the Requirement Issue. Provider-unavailable retries are
automatic and appear only in the overview.
