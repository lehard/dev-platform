# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic OpenSpec review plus structural validation

## Semantic review

- Compared the proposal, design, and completed implementation: remote PR/check/queue waits remain outside `main_merge_lock`; only confirmed-`MERGED` local reconciliation takes it.
- Confirmed reconciliation fetches `origin/main` after acquiring the lock, recomputes the local/remote relationship, and serializes main, board, and optional task cleanup.
- Confirmed required-check classification uses `gh pr view --json` plus `gh pr checks --required --json`, validates the PR head SHA, and fails closed on unavailable or unsupported structured state rather than parsing rendered `gh` text.
- Confirmed registration, pending-check, and merge-confirmation timeout paths leave local main untouched and report a resumable remote-pending outcome; already-merged recovery reuses the same serialized reconciliation path.
- Reviewed regression coverage for structured states/head matching, timeout behavior, two confirmed merges sharing an integration checkout, and already-merged lock contention.

## Executed checks

- `python3 -m compileall -q template/scripts scripts`
- `python3 -m unittest discover -s tests -v`
- `python3 scripts/managed_projects.py validate`
- `python3 template/scripts/openspec_lifecycle.py check`
- `openspec validate harden-pr-reconciliation-concurrency --type change --strict --no-interactive`
- Factory render of a `multi-agent`/`pr` project, then generated `compileall` and `platform_doctor.py`.
- `python3 tests/upgrade_smoke.py --profile multi-agent --publish-mode pr`
