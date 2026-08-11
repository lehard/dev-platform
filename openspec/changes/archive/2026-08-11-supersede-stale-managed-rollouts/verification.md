# Verification: supersede stale managed rollouts

OpenSpec-Verify: PASS

Verification-Method: manual semantic OpenSpec review against proposal/design/delta spec plus targeted unit/workflow tests, full platform validation, GitHub protected-main CI, and reviewed GitHub App dry-run/apply maintenance evidence.

## Semantic review

- Identity is conjunctive: `rollout_supersession.py` accepts only an exact reserved `dev-platform/rollout-vMAJOR.MINOR.PATCH` head, stable SemVer, configured managed base, same-repository head, and expected GitHub App bot author. Titles are not read for eligibility.
- `require_managed()` reads and validates `managed-projects.json` before enumeration or mutation. The maintenance workflow's matrix is built exclusively by `managed_projects.py matrix`; candidate/excluded entries receive neither target token nor write path.
- Normal rollout calls supersession only after an eligible target PR was found or created. A failed prepare cannot reach push, PR creation, or supersession.
- The reconciler closes only lower eligible targets when a validated newer PR is authoritative, or targets at/below coherent committed downstream metadata. It never closes a newer target for an older request.
- PR close is confirmed through GitHub before branch deletion. Ref deletion failures are emitted as warnings and leave a correctly closed PR; no force operation exists.
- Maintenance is explicit `dry-run`/confirmed `apply`, uses the same per-target GitHub App token, and retains the newest eligible validated target while removing only its older predecessors.

## Automated and integration evidence

- `python3 -m compileall -q template/scripts scripts` — passed.
- `python3 scripts/managed_projects.py validate` — passed (`3 managed, 7 candidate, 3 excluded`).
- `python3 -m unittest discover -s tests -q` — passed, including `tests/test_rollout_supersession.py` coverage for identity lookalikes, base coherence, failed-newer safety, newer-target preservation, candidate/excluded rejection, dry-run zero writes, and warning-only delete failure.
- `python3 template/scripts/openspec_lifecycle.py check` — passed.
- `openspec validate supersede-stale-managed-rollouts --strict` with OpenSpec `1.8.0` — passed.
- Protected-main Platform CI passed for implementation [#86](https://github.com/lehard/dev-platform/pull/86) and the maintenance-authority correction [#87](https://github.com/lehard/dev-platform/pull/87).
- Maintenance dry-run [31463657179](https://github.com/lehard/dev-platform/actions/runs/31463657179) was reviewed before mutation; confirmed apply [31463725473](https://github.com/lehard/dev-platform/actions/runs/31463725473) succeeded. Exact target and post-apply evidence is retained in `maintenance-evidence.md`.

## Archive result

`python3 template/scripts/openspec_lifecycle.py archive supersede-stale-managed-rollouts` completed the change-specific strict validation, updated the current `platform-rollout` spec with four added requirements, and moved this change to the archive on 2026-08-11.

The helper's final installed-OpenSpec `1.8.0` global scan separately reported pre-existing incomplete scenario preservation in the still-active `harden-pr-reconciliation-concurrency` and `wire-runtime-delegation-containment` changes. Those changes are outside this archive and were not modified or masked. The repository's pinned CI validator remains OpenSpec `1.6.0`; protected-main CI for #86 and #87 passed with that supported validator.
