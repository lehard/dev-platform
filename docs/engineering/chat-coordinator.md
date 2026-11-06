# Chat coordinator

The **chat coordinator** is a role the owner can assign to any new Codex or Claude
session. It is the **delivery orchestrator** of Dev Platform: it keeps the backlog
roadmap, starts and holds the development streams, and after every developer
handoff sees that each job has an executor: it starts the jobs that run only on the
operator node (see *Job placement*) and any job left unclaimed, until no job remains. It tells the owner, in ordinary words,
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
- launching operator-node workers (see *Job placement*) and draining unclaimed jobs;
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
3. **After a handoff, see that every job has an executor** (see *Job placement*).
   Run an operator-node job from the integration checkout (never from a task
   worktree), with no exported credential: the worker uses the active `gh` login and reads the
   Claude credential from `[independent_review.login.claude] token_file`, and an exported
   token is removed, not used:

   ```bash
   python3 scripts/lifecycle_workers.py work-next --repo owner/repo --pr N --kinds review --run
   ```

   `work-next --run` first proves its environment and refuses, with exit 3 and no claim,
   naming every unmet condition; `python3 scripts/lifecycle_workers.py worker-preflight --kinds <kinds> --repo owner/repo`
   prints the same conditions without reading a job. A registered condition that fails
   after claim releases the claim as `released: environment: <condition>`: it spends none of the job's
   three releases, attempts or finalize verdict. Five such releases of one job give an operational
   block that `resume` lifts.

   Review and finalize are normally claimed by the hosted workers
   ([hosted-lifecycle-workers.md](hosted-lifecycle-workers.md)); check the overview
   before launching. Repair kinds take `--writer claude-sandboxed`, which names its
   own provider, or `--provider` with `--llm-command`; `--writer` exists only for
   `repair` and `integration-repair`. Post-merge kinds
   (retrospective, terminal reconciliation, cleanup) run every 10 minutes through the
   local post-merge runner (LaunchAgent `dev.platform.post-merge-runner`, journal:
   `python3 scripts/post_merge_runner.py journal --journal-dir <dir> --last 50`); the
   overview names the run-now command for an unclaimed one. Friction recorded after
   the Requirement retrospective blocks the terminal job with a key of those events;
   the runner then repeats retrospective and terminal under that key, up to three
   times, with no hand-run checkpoint. Past that the overview reports the block and
   `reoffer-post-merge` gives a new bound. Keep the integration
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

## Job placement

| Job | Runs on | Started by |
| --- | --- | --- |
| `review` | hosted worker | automatically |
| `review` of a composition of a private Requirement | operator node | coordinator |
| `finalize` | hosted worker | automatically |
| `finalize` of a composition, with its full checks | operator node only | coordinator |
| `integration-merge` | hosted worker | automatically |
| `contribution-integration` | publication queue | automatically |
| `repair`, `integration-repair` | operator node | coordinator |
| `retrospective`, `terminal-reconciliation`, `cleanup` | post-merge runner on the operator machine | LaunchAgent, every 10 minutes |

The operator node is `lifecycle_workers.py work-next --run` on the operator machine. The coordinator also runs there a job that an automatic executor left unclaimed. Hosted kinds are the ones enabled in `DEV_PLATFORM_HOSTED_KINDS`.

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
`integration-repair` need macOS), `worker-job`, `publication-queue`,
`requirement-composition`, `attempt-limit-exhausted` or `human-decision`. A state no
rule explains prints `idle reason unknown` with the state; it is never shown as
healthy. The line explains the wait and takes no action.

## Acting on an exception

A contribution conflicted by a sibling merge needs no CI dispatch: GitHub runs no
checks on a conflicted PR, so the contribution-integration job evaluates the
conflict before required checks and offers an integration repair naming the
paths. A conflict-free head without required checks is refused naming the wait,
and the publication queue integrates it once they pass. To bring main into a requirement branch before
its composition is queue-owned:

```bash
python3 scripts/execute_requirement.py absorb-main --requirement owner/repo#N
```

It merges main in a disposable checkout and pushes by fast-forward from the exact
observed head. Open contributions keep their base. Once the queue owns the
composition, main arrives through its integration repair instead.

An assembled Requirement branch is repaired only through its composition PR's
queue job. From the coordinator checkout, request the existing repair writer:

```bash
python3 scripts/execute_requirement.py repair --pr N --expected-head <head> --reason "<bounded composition fix>"
```

The command requires an open composition PR at that exact head, its complete
owned contribution manifest, intact child receipts and no live job claim. It
records the reason and authenticated actor and offers one `repair` job using
the normal provider routing and attempt budget. Repeating it while that repair
is pending returns the existing job. A finding escalation or spent repair budget
still requires the owner's decision. Never repair `requirement/BR-N` with a
manual commit or edit its manifest instance by hand.

Run the offered job through the usual `lifecycle_workers.py work-next` repair
writer, whose scope is the PR's changed paths. The harness regenerates declared
generated files and the composition manifest, then runs `validate_children`
before push. Every child's verification, automated checks and independent review
files must remain byte-for-byte identical to the reviewed contribution, including
after archive moves. A mismatch fails naming the child and receipt; nothing is
restored silently or pushed. A successful repair returns to composition review,
finalization and full checks for the changed content.

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
no fresh job is re-offered with `resume`. A Requirement listed as waiting for the owner
(`awaits-owner-acceptance` in the overview) closes only after the owner's word on each
operator acceptance item, recorded with the printed
`requirement_terminal.py accept ... --via chat-coordinator --reason "<owner's words>"`. A Requirement composition has no pre-merge
retrospective: its finalize job runs the full final-head checks, records any
wait for required CI on that exact head, and admits it only once CI passes. The
existing publication queue resumes the recorded wait on a CI completion event;
it does not repeat the full checks. A clean, proven main-only update retains the
original full-check evidence and requires new exact-head CI. An interrupted
integration-repair push without final-check proof is explicitly blocked. A
composition left `blocked-retryable` on a red `full-checks` gate at its current
head with no job (for example its full checks could not run) is moved only by
`resume`: it re-offers the finalize job when the head contains current main, and
otherwise one integration-repair job whose repaired head runs the full checks once
and is admitted after exact-head CI. Any other red full-checks case is refused
naming why. Composition finalize and full checks run only on the local operator
node, which has the managed project registry. The
post-merge retrospective job records the Requirement checkpoint after the merge. A record still carrying a pre-merge retrospective job fails
derivation naming the PR; re-offer finalization or recover the candidate.
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
