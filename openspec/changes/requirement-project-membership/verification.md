OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review of proposal, delta, design, implementation and regression evidence
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Semantic review

Completeness: both added managed-task-intake requirements are implemented. `managed_project_status.ensure_item` adds a missing Project item idempotently, initializes only an unset Status to `Backlog`, and accepts the result only after an exactly-one read-back. `requirement_intake.create` confirms membership before reporting success, reuses an identical open Requirement on rerun and fails closed naming the durable Issue; `reconcile-board` repairs one or all open Requirements; `requirement_board.claim_started` ensures membership before claiming the card. The connected rule is documented in task-intake and the ChatGPT protocol and pinned by the `connected_fixation_outcome` reference model.

Correctness: fake-GraphQL tests cover auto-add already done (unset Status), auto-add absent, item lagging in the Project list, existing item and Status preserved, repeated reconciliation without a duplicate, duplicate items refused without mutation, unavailable Project API at read and at add, missing authentication, repository-local create success, fail-closed create and rerun reuse, and the connected outcome.

Coherence: proposal, design, delta, runtime and docs agree. No new service or Project migration; GitHub built-in auto-add stays a fast path.

## Evidence and limits

- Live read-back on 2026-10-07 before the change: lehard/development-backlog #415, #416, #433 and #436 each already had exactly one Project item created 2-3 seconds after the Issue. The reported missing auto-add was not reproducible, so the root cause of the original observation is unconfirmed; the delivered defect fix is that membership was never confirmed or repaired by the platform.
- Live `reconcile-board --all` after the change: all 30 open Requirements, including #416, #433 and #436, have exactly one item; nothing needed adding. #416 shows Status Done while open (a side effect of the earlier close/reopen retrigger); it was not changed because the platform does not rewrite lifecycle statuses.
- The connected ChatGPT adapter cannot be executed from this repository; its behavior is a documented contract plus a reference-model test, and the unattended completion depends on the operator invoking `reconcile-board`, which is not scheduled by this change.
- Selected checks: compileall, ruff and the complete canonical suite (17 groups) passed; see automated-checks.json.

## Independent review round 1 (codex, both perspectives)

Both perspectives returned the same two material findings, accepted and repaired: (1) retry lookup compared the stored body, which gains a platform-appended `Work identity` line, with the freshly rendered body, so a rerun after a Project failure created a second Issue; the comparison now ignores that trailing line, and the reuse test uses a body carrying it. (2) `gh api --paginate` output was parsed as one JSON document, which fails beyond one page; reads now use `--slurp` and flatten pages, and the reconcile test supplies two pages. A repeated independent review of the repaired head and fresh selected checks are required.

## Independent review round 2 (codex, both perspectives)

Five findings; all accepted and repaired. Material: downstream template docs (`template/docs/engineering/chatgpt-project-protocol.md`, `task-intake.md.jinja`) lacked the membership gate and unconfirmed outcome, now added; the post-initialization read-back accepted any Status, now it must equal the requested `Backlog` or fail (test with a concurrently claimed card); Status is re-read immediately before the write to narrow the claim race (GitHub has no compare-and-set, so a residual window remains and is reported by the read-back failure rather than hidden). Advisory: `--requirement` reconciliation now requires an open `type:requirement` Issue; an already initialized card costs one Project scan instead of three. A repeated review of the repaired head and fresh selected checks are required.

## Independent review round 3 (codex, both perspectives)

Accepted and repaired: bulk `reconcile-board --all` (and rerun lookup) now select only Requirements carrying this checkout's configured `project:*` label, so other targets sharing the Backlog repository are never added to this Project (test asserts the label query); documentation no longer states Backlog-only success, an existing Status being preserved.

Rejected (both perspectives, `concurrent-status-overwrite` / `status-initialization-overwrites-concurrent-claim`): GitHub Projects offers no compare-and-set on a single-select field, so a write after any read cannot be made atomic. The platform narrows the window by re-reading immediately before the write, only ever writes an unset Status (a fresh card whose built-in "Item added" workflow has not yet set one), and every claim path (`start`/`advance`) itself runs `ensure_item` before claiming, so legitimate claimers cannot race on an unset card. If a claim does land between the re-read and the write, the post-write read-back sees Backlog and cannot detect it; this residual millisecond window on a brand-new card is accepted and reported, not hidden.

## Independent review round 4 (claude reviewer, bound by operator decision after codex usage limit)

Review state `ready`: spec-fidelity returned no findings; engineering-quality returned two advisory findings, not repaired in this task. (1) Reusing an identical open Requirement re-runs label reconciliation with the new call's priority; a different priority hits the existing conflicting-label check and fails explicitly rather than silently relabeling, so no change. (2) `reconcile-board --all` stops at the first Requirement whose membership cannot be confirmed; it is fail-closed and idempotent and a rerun continues, and continuing past failures would be a catch-and-continue path, so it is left as is.
