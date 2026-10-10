## 1. Bounded freshness contract

- [x] 1.1 Add `--proven-base SHA` to `template/scripts/select_checks.py` with `_platform_common.require_proven_task_base`. It is accepted only with `--execute` in coordinator lifecycle mode, refused with `--evidence`, `--contribution-base` or protected-full, and requires `merge-base(HEAD, origin/<main>) == SHA`. It replaces `require_fresh_task_base` only when given; without it the gate is unchanged.

## 2. Finalization on the proven base

- [x] 2.1 `trusted_checks_runner` requires exactly one of `contribution_base`/`proven_base`, passes the matching option and returns its command and freshness description.
- [x] 2.2 `execute_finalize` passes the proven base from the identity it has proven equivalent to the recorded one, and fails loudly on a missing base. `reestablish_gates` records the runner description in the harness-executed `selected-checks` evidence. Finalization never fetches or merges `main`.

## 3. Review reuse on re-admission

- [x] 3.1 In `publication_queue.admit`, carry every lineage gate that is still `reusable` for the new handoff identity into the supersession's `review-pending` record, rebound to that identity. Exclude `required-checks` and the handoff-supplied gates. The `_supersession` guards stay unchanged.

## 4. Regression tests

- [x] 4.1 (a) Two independent reviewed candidates: the first merges and advances `main`; the second finalizes and integrates with no developer action.
- [x] 4.2 (b) After a real review repair and a `main` advance, finalize runs the real `select_checks` under `--proven-base` and is not escalated for freshness. Replace `test_main_task_finalize_keeps_main_freshness`. Extend `parallel_lifecycle_acceptance.py` to assert that the finalize runner receives the identity's proven base after main moved.
- [x] 4.3 (c) A clean main merge re-admitted with unchanged content carries the passed review, and the review job completes as `reused-review` without launching a reviewer.
- [x] 4.4 (d) A content-changing conflict fix or overlapping main merge drops the review and runs a new one.
- [x] 4.5 (e) A failing check under `--proven-base` escalates finalize. A real conflict or a failing required check becomes integration repair. Test every `--proven-base` refusal. A stale developer preflight is still blocked. The finalize commit is a fast-forward of the claimed head only.

## 5. Documentation

- [x] 5.1 Document the two-contour boundary, the proven-base contract, review reuse on re-admission and the #455-style recovery path in `docs/engineering/agent-workflow.md`. Update the finalize paragraph of `docs/engineering/openspec-workflow.md`. The coordinator sections are source-only, so the template docs have no twin to change; record that in verification.

## 6. Readiness and recovery

- [x] 6.1 Readiness gate, before release: obtain real parallel-lifecycle dogfood evidence (BR-391 and its acceptance task) in which `main` is moved by another merge between review and finalize of a repaired candidate, and the finalize worker runs this change's trusted scripts. Record the PRs, heads, transitions and worker runs in `verification.md`. Unit tests alone do not complete this item; if the evidence is missing, the item stays open and blocks archive. The success leg (a candidate reaching `ready` and integrating after such a `main` move) is a separate release gate before tagging v1.9.5, demonstrated on this change's own PR with its finalize run from this change's scripts and recorded in the Requirement retrospective.
- [x] 6.2 Record the in-place recovery path for a finalize-freshness-blocked candidate (resume and a proven-base finalize; developer re-admission in the same PR when content must change) in the docs and in `verification.md`, with the actual #455 outcome.

## 7. Delivery

- [x] 7.1 Required platform checks, truthful verification, archive, retrospectives, publication.
