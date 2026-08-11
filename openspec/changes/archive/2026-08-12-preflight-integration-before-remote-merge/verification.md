# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic review plus automated lifecycle regression tests and strict OpenSpec validation

## Completeness

- The active delta requirements map to a short serialized pre-merge guard for every ordinary, auto-merge and merge-queue GitHub mutation, with a re-fetch and concrete dirty-path diagnostics.
- Confirmed-merge recovery now classifies the complete local snapshot against the authoritative remote target before it changes the real branch or index.
- Regression coverage includes clean protected publication, dirty state before a merge command, state introduced while required checks wait, task-path overlap with different content, and already-merged equivalent/divergent local state.

## Correctness

- `python3 -m compileall -q template/scripts scripts` passed.
- `python3 scripts/managed_projects.py validate` passed.
- `python3 -m unittest discover -s tests -v` passed (390 tests).
- `openspec validate preflight-integration-before-remote-merge --strict` passed.
- `python3 template/scripts/openspec_lifecycle.py check` passed before all task boxes were completed.
- `git diff --check` passed.

The temporary-index comparison stages the observed worktree into an index created from `origin/main`; this validates file content and mode without touching the real index. The subsequent mixed reset is only reached after equivalence is proven, so it does not overwrite distinct local content.

## Coherence and limitations

- Required-check and merge-queue waits stay outside the integration lock; each protected remote mutation re-acquires the existing lock and re-observes the integration copy.
- Exact-head arguments, GitHub `MERGED` authority, no-force-push behavior, and existing Project/board reconciliation ordering are unchanged.
- Copier is not installed in this runtime (`copier: command not found`), so a render/update smoke test could not be executed. The template change is covered by the repository's unit suite and the new module is excluded for project-owned harness renders consistently with the other platform-owned lifecycle scripts.
