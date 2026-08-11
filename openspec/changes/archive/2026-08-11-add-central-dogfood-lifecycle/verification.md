# Semantic verification

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of proposal/design/delta/spec/task coherence plus targeted adapter tests and full repository validation.

## Completeness

- The committed central source contract covers its branch, protected-main,
  multi-agent workspace, PR publication, merge policy and required adapter
  paths without inheriting the downstream fallback configuration.
- `dogfood_task start` transfers only the already-validated managed package to
  a normal isolated worktree and leaves the integration copy clean; unrelated
  changes fail closed without stash/reset/clean behavior.
- `dogfood_task status` and `finish` delegate to the established
  `finish_task.py` status/reconciliation path. No publication state, GitHub
  query, or merge routine was copied into the source adapter.
- Root guidance states the supported commands and makes draft/open/green PR
  states explicitly nonterminal.

## Correctness

- `tests/test_central_dogfood_lifecycle.py` proves explicit configuration,
  safe managed-package transfer, dirty-copy refusal, and the exact status and
  finish delegation arguments in temporary repositories.
- The existing `test_publication_recovery_cli.py`, `test_publication_state.py`,
  `test_pr_reconciliation_concurrency.py`, and `test_git_lifecycle.py` cover
  the delegated authoritative behavior: no-PR/open/checking/merged states,
  exact-head resume and changed-head refusal, protected merge, and local
  reconciliation.
- Runtime smoke: `python3 scripts/dogfood_task.py status` reported the
  current task's authoritative `not_published` state without mutation.

## Coherence and boundaries

- The source-only adapter imports the self-contained template primitives only
  in the central checkout; generated downstream repositories remain unchanged
  and retain their self-contained runtime contract.
- `durable-publication-recovery` remains active and unchanged. This change
  neither claims nor alters its remaining live-acceptance work.
- No template behavior, Copier answer, release contract, secret, force-push,
  admin bypass, or project rollout semantics were changed.

## Automated evidence

Passed on the implementation head before archive:

```text
python3 -m compileall -q template/scripts scripts
python3 scripts/managed_projects.py validate
python3 -m unittest discover -s tests -v
python3 template/scripts/openspec_lifecycle.py check
openspec validate add-central-dogfood-lifecycle --strict --no-interactive
git diff --check
```
