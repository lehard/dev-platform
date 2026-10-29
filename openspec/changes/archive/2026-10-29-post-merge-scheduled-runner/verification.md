OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the diff against the lifecycle-workers delta, proposal, design and tasks; 12 targeted unit tests with a fake gh and fake work-next; one real read-only `work-next --dry-run` and `launchagent --print` against the real checkout; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json

## Decisions

- Direct handoff (bounded evidence, no ADD): the Requirement fixes the decision and constraints; frequency (600 s), launchd and the JSON Lines journal were left to the executor.
- No OAuth/LLM token is passed: `run_claimed_post_merge` uses none (the manual coordinator invocation passed one unnecessarily). This was read from the code and not exercised by a live non-dry run.
- The runner is a platform-only script (`scripts/`), not shipped through `template/`.
- Coordinator accepted the `dev-platform/checks.toml` scope overlap with #909 (different lines of one list).

## Completeness

- Chain to idle, max-jobs bound, low remainder at start and between runs, first failure, unparsable output and timeout, lock contention, interrupted previous round, missing configuration, missing token, corrupt journal, plist content and missing gh: `tests/test_post_merge_runner.py`.
- Owner install/rollback and journal reading: `docs/engineering/hosted-lifecycle-workers.md`; the placement table row names the runner.

## Correctness

- Claims, results, attempt limit and attention are untouched: the runner only spawns `lifecycle_workers.py work-next --run` and parses its JSON; a spent obligation stays reported by `ensure_post_merge_attention` and `post-merge-exhausted` in `lifecycle_overview.py`.
- A failed run stops the round and exits 1; the runner never retries within a round.

## Coherence

- Spec delta, design, tasks and docs agree on bounds, journal events and the 600 s interval.

## Not verified / limits

- No live claiming run and no LaunchAgent installation on this machine (owner step). The overview/PR visibility acceptance relies on the existing post-merge-exhausted path, which this change did not modify.
- Counted REST cost of a round grows with each `work-next` poll until the BR-886 read cache lands (remainder was 3139/5000 at check time); the threshold and `--max-jobs` bound it.
- No journal rotation.
