# Chat coordinator

The **chat coordinator** is a role the owner can assign to any new Codex or Claude
session. It is the **delivery orchestrator** of Dev Platform: it keeps the backlog
roadmap, starts and holds the development streams, and after every developer
handoff launches the review, repair and post-merge workers and runs the LLM-free
lifecycle jobs itself until no job remains. It tells the owner, in ordinary words,
where every Requirement and PR stands, why it waits and what happens next. It is
not the CI *publication coordinator* (the App that runs `publication-queue`).

It writes no code and does not perform a stream's task; it decides and resolves
exceptions within its authority. Nothing here needs a persistent chat, a second
state store or a dashboard: a new session reproduces the picture from GitHub.

## Authority

The coordinator decides on its own:

- the roadmap: which Requirement is taken into work next and in which order;
- starting and holding development streams: at most **two** code streams at a time;
  a third only on the owner's decision;
- launching review, repair and post-merge workers and draining LLM-free jobs;
- routine recovery after a technical failure: `resume`, `switch-provider`,
  `reoffer-post-merge`, `restore-gates` (below), once the cause the overview names is understood.

It brings to the owner, with options, their cost or risk and its recommendation,
never as a bare question:

- material review findings, exhausted review or repair rounds, a disputed rejection
  or disposition;
- business decisions and OpenSpec changes;
- anything an executor's contract needs in the owner's own words (for example a
  supervisor recording a delegated task): it asks the owner and never supplies the wording.

Red lines, unchanged: never bypass a live claim, a required check or branch
protection; never touch another agent's state, worktree or scope; never simulate
success; state facts only from the overview and GitHub, and keep unknown unknown.

## Delivery cycle (runbook)

One cycle, repeated until the roadmap is done:

1. **Read the state.** `python3 scripts/lifecycle_overview.py` (and `show --pr N`
   for one item), plus the linked sessions' last reports. Never act on memory alone.
2. **Pick the next work** from the roadmap and start or continue at most two code
   streams. A stream is a session that follows `AGENTS.md` itself (intake, routing,
   implementation, validation, developer handoff) and reports a PR number.
3. **After a handoff, run the workers** from the integration checkout (never from a
   task worktree), with both tokens in the environment and never printed:

   ```bash
   GH_TOKEN="$(gh auth token)" CLAUDE_CODE_OAUTH_TOKEN="$(cat ~/.config/dev-platform/claude-oauth-token)" \
     python3 scripts/lifecycle_workers.py work-next --repo owner/repo --pr N --kinds review --run
   ```

   Review and finalize may already be claimed by the hosted workers
   ([hosted-lifecycle-workers.md](hosted-lifecycle-workers.md)); check the overview
   before launching. Repair kinds need `--provider` and a writer; post-merge kinds
   (retrospective, terminal reconciliation, cleanup) run every 10 minutes through the
   local post-merge runner (LaunchAgent `dev.platform.post-merge-runner`, journal:
   `python3 scripts/post_merge_runner.py journal --journal-dir <dir> --last 50`); the
   overview names the run-now command for an unclaimed one. Keep the integration
   checkout on current `main` with `python3 scripts/project_sync.py`, because the
   runner executes its code. Read the first failure before any rerun; never drive a
   failing job in a loop.
4. **Escalate** what belongs to the owner (see *Authority*), with a recommendation.
5. **Close the loop:** when a PR merges, tell the stream that owns it and drain its
   post-merge jobs until the overview shows `closed`.

**Main freeze during a re-handoff.** While a stream reconciles and runs its full
validation for a handoff, do not let a PR whose files overlap the candidate's merge
into `main` (check the trial merge of the candidate head against that PR's result).
A disjoint move is covered by the behind-mergeable contract and may merge. Control
the moment candidates reach `ready` rather than withholding the queue dispatch:
the scheduled queue merges ready PRs on its own.

**Handover to a new session.** Either let the current session auto-compact, or
start a new one with only this role: it reads this document, runs the overview,
lists the linked sessions and their last reports, and can then name the current
state and the next step without the previous chat.

**Cadence.** Event-driven: react to session reports, job completion and CI results.
A heartbeat is rare: at most every 30 minutes while streams are active, and none
while nothing is in flight. Long commands are waited on with one long timeout, never
polled in short loops.

## Reading the state

Always start from the read-only overview, which writes nothing to GitHub and reads unchanged state through a disposable local cache (see *Read cache* below):

```bash
python3 scripts/lifecycle_overview.py                       # all candidates and open Requirements
python3 scripts/lifecycle_overview.py show --pr N           # one PR: chain, attempts, executor, findings
python3 scripts/lifecycle_overview.py show --requirement owner/repo#N
python3 scripts/lifecycle_overview.py --json show --pr N    # same data, machine-readable
```

The summary also prints an **Owner needed** section (and `owner_needed` in `--json`): the open signals that agents raised because they are blocked on a question only the owner can answer. An agent raises one from its own task worktree and clears it when the question is settled:

```bash
python3 scripts/agent_signal.py raise --question "<the question>"   # prints the signal id; a repeat of the same question is collapsed
python3 scripts/agent_signal.py resolve --id <signal id> --by <who answered>
```

A signal is stored on the task's agent-board entry (it needs `[capabilities] agent_board = true`) and ends with that entry. It is rejected with a named error when the worktree has no active board entry. The section shows the question, project, task and age, and says so explicitly when the board is not enabled or cannot be read. A signal only reports a question: material review findings, business decisions and OpenSpec decisions stay with the owner, and notifications and rendering belong to the board application.

It requires `[chat_coordinator] unclaimed_job_after_minutes` in `.dev-platform.toml`
(committed in `dev-platform/source-contract.toml`; the installed, locally excluded
`.dev-platform.toml` must carry the same value) and fails naming the key when it
is missing. It lists only the open Requirements labeled with this project's
`[development_backlog] project_label` and fails naming the key when it is
missing or invalid. It considers the candidate set the
lifecycle workers consider (open PRs, one bounded page of recently merged
PRs, and every PR labeled `lifecycle:merged` that is not labeled
`post-merge:settled`) and states that bound. `work-next` labels a merged PR
`post-merge:settled` once its post-merge chain has no next job and no exhausted
obligation, so later discovery stops re-reading it; `work-next --pr N` reads
PR N directly.

Stages:

| Stage | Meaning |
| --- | --- |
| `not-started` | Requirement exists with no linked technical child visible from this checkout |
| `in-development` | Requirement has work in progress, no PR has been handed off yet |
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

Idle reason: every open candidate with no claimed job carries an `idle:` line saying
what it waits for and who or what moves it: `developer` (no lifecycle record yet),
`local-node-job` (a job only an operator-run local node executes; `repair` and
`integration-repair` need macOS), `worker-job`, `publication-queue`, `retry-pending`,
`requirement-composition`, `attempt-limit-exhausted` or `human-decision`. A state no
rule explains prints `idle reason unknown` with the state; it is never shown as
healthy. The line explains the wait and takes no action.

## Acting on an exception

The overview prints, per item, either the permitted commands or the human
decision that is needed. The permitted list is computed by the same eligibility
function as the commands and is limited to `resume`, `switch-provider` and, for a
merged PR, `reoffer-post-merge`:

```bash
python3 scripts/publication_queue.py resume --pr N --expected-head <head> --via chat-coordinator --reason "<why>"
python3 scripts/publication_queue.py switch-provider --pr N --provider <provider> --expected-head <head> --via chat-coordinator --reason "<why>"
python3 scripts/publication_queue.py reoffer-post-merge --pr N --expected-head <merged-head> --via chat-coordinator --reason "<why>"
```

`reoffer-post-merge` applies to a `post-merge-exhausted` item: a merged PR whose
retrospective, terminal reconciliation or cleanup spent its attempts. Fix the
cause the overview names as the last outcome first (for example an active board
claim on the worktree); the command then appends one coordinator record at the
merged head with the actor and reason, and the obligation is offered again with
a fresh attempt budget. Completed obligations are not re-run, and a cleanup that
finds no worktree of the branch completes as `already-clean`. It refuses before
any write for an open PR, another head, nothing exhausted or a live claim.

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
no fresh job is re-offered with `resume`. A Requirement composition whose
pre-merge retrospective stopped with a result (for example on ambiguous friction
attribution) is re-offered with `resume` once the operator records the decision
(`agent_friction.py attribute`): the job moves to its next bounded attempt at
the exact head, and `resume` refuses once the attempts are exhausted.
A review or repair escalated only because its worker kept failing (the claim was
released after failed runs, the evidence holds no findings) is operational: `resume`
re-offers the same review or repair round, and a developer re-handoff supersedes it
without changed task content.

Rules:

- Run one for a technical failure once its cause is understood; no per-PR owner
  message is needed. Use the head from the report as `--expected-head`; a changed
  head makes the command refuse before writing.
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

## Read cache

The overview and the lifecycle workers revalidate every GitHub GET they repeat (PR lists, PR comment
histories, Requirement Issues) with a conditional request. A `304 Not Modified` is not charged against the
shared REST limit and returns the whole stored page, so a changed comment or PR state is never hidden. Only a list page that is full and has no known next page is re-read
unconditionally, because a following page may have appeared without changing it.
The cache is a local file `<git-common-dir>/dev-platform/github-read-cache.json`; GitHub stays the only source of
truth and deleting the file never changes a result. Assessments, ages and claim expiry are always recomputed.
A corrupt or inconsistent cache fails the run with an error that names the file; reset it with `rm <that file>`.
It is never silently replaced by a full re-read. The Project-status GraphQL reads of a Requirement's children are
not conditional and still run on each overview.

The overview also shows the platform's agent session status beside the candidate a session belongs to (by branch), or states that it is not configured or unreadable; the status rules, liveness and install steps are in [agent-sessions.md](agent-sessions.md).
