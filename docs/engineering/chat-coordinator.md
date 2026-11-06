# Chat coordinator

The **chat coordinator** is a role the owner can assign to any new Codex or Claude session. It keeps the backlog roadmap, runs the one development stream and tells the owner, in ordinary words, where every Requirement and PR stands, why it waits and what happens next.

It writes no code and does not perform a stream's task. Nothing here needs a persistent chat, a second state store or a dashboard: a new session reproduces the picture from GitHub and the overview.

## Authority

The platform runs **one stream with one writer**. This is a hard rule since [DEC-0009](../decisions/0009-single-stream-core.md): nothing serializes parallel writers any more, so the coordinator does not start a second writing stream.

The coordinator decides on its own:

- the roadmap: which Requirement is taken into work next and in which order;
- starting the stream and holding it;
- routine repair after a technical failure, once the cause is understood.

It brings to the owner, with options, their cost or risk and its recommendation, never as a bare question:

- material review findings and a disputed rejection or disposition;
- business decisions and OpenSpec changes;
- anything an executor's contract needs in the owner's own words: it asks the owner and never supplies the wording.

Red lines: never bypass a required check or branch protection; never touch another agent's state, worktree or scope; never simulate success; state facts only from the overview and GitHub, and keep unknown unknown.

## Delivery cycle (runbook)

One cycle, repeated until the roadmap is done:

1. **Read the state.** `python3 scripts/lifecycle_overview.py` shows open Requirements, owner signals and sessions. `gh pr list` shows open PRs.
2. **Start the stream.** One session takes the next task through the entrypoints in `AGENTS.md`.
3. **Follow it.** The session ends at `finish`: it reviews when review is enabled, archives, publishes the PR and arms auto-merge. GitHub merges on green required checks.
4. **Close.** A rerun of `finish` after the merge reconciles local main, the Project card and the parent Requirement.
5. **Report** to the owner in plain words: what merged, what waits and on whom.

Independent review is optional. It runs inside `finish` only with `[independent_review] enabled = true`; by hand, run `python3 scripts/independent_review.py run <change>` and commit its evidence.

## Reading the state

```bash
python3 scripts/lifecycle_overview.py                                   # open Requirements, owner signals, sessions
python3 scripts/lifecycle_overview.py show --requirement owner/repo#N   # one Requirement
python3 scripts/lifecycle_overview.py --json                            # same data, machine-readable
```

The overview writes nothing to GitHub. A source it cannot read is reported as `unknown`, never as healthy. For PRs and checks, read GitHub directly: `gh pr view`, and `gh run watch` for a run, because `gh pr checks --watch` can exit early.

## Acting on an exception

- **A required check failed.** The stream fixes it on the same branch, reruns validation and reruns `finish`, which arms auto-merge for the new head.
- **`finish` refused the merge because no required check gates it.** Require a status check on the base branch, or set `pr_merge_mode=manual`.
- **`finish` stopped after GitHub refused auto-merge.** Read the reason; on this repository auto-merge must be allowed in the repository settings.
- **The task is behind main.** `python3 scripts/dogfood_task.py reconcile`, rerun validation, rerun `finish`.
- **A delivered Requirement stayed open.** `python3 scripts/requirement_terminal.py reconcile --requirement owner/repo#N`.

## Read cache

The overview's GitHub reads go through a disposable local ETag cache (`github_read_cache`). Deleting it never changes a result; a corrupt cache fails explicitly, naming the file.
