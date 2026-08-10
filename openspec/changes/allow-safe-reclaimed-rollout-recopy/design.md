# Design

## Ownership boundary

Smart Copier update remains the default. Recopy is a recovery mechanism, never the first path.

A platform-mode conflict has two safe recovery proofs:

1. **Reclaimed target-equivalence.** A narrowly allowlisted migration path already matches the exact target template before update. This proves the downstream override has already been retired.
2. **Recorded baseline-equivalence.** The conflicted path in committed downstream `HEAD` is exactly identical to the same path in the immutable platform tag recorded by `.copier-answers.yml`. This proves there is no current downstream customization for recopy to erase. Missing/missing is equivalent for the same reason.

Any conflict that satisfies neither proof remains blocking. Project-owned harness recovery keeps its existing behavior: declared project-owned collision points may use guarded recopy while their fingerprints are preserved.

## Why the second proof is needed

The v1.4.14 Cuby rollout demonstrated that historical Copier replay can create rejects beyond the one downstream-hotfixed file. It emitted:

- `scripts/project_publish.py.rej` — already exact target, covered by reclaimed target-equivalence;
- `scripts/finish_task.py.rej` — committed Cuby file still exactly v1.4.12 baseline, so it is baseline-equivalent;
- `tests/test_git_lifecycle.py.rej` — absent in both Cuby and the recorded v1.4.12 consumer template, also baseline-equivalent.

Path allowlisting alone cannot model this safely without accumulating repository/history-specific exceptions. Comparing immutable old-template state to committed downstream state does.

## Algorithm

1. Snapshot project-owned files and the non-version platform config contract.
2. Before smart update, compute which reclaimed migration paths already match the candidate template exactly.
3. Run `copier update --conflict rej`.
4. If no rejection exists, continue normally.
5. Read the repository's recorded old platform tag from `.copier-answers.yml` and ensure that immutable tag is available in the exact-release platform checkout.
6. For every platform-mode conflict not already target-equivalent, compare downstream committed `HEAD:<path>` with `<recorded-tag>:template/<path>`. The comparison uses Git tree/blob fingerprints, never the Copier-mutated worktree.
7. Classify conflict targets into project-owned, proven reclaimed-target, proven baseline-equivalent, and unexpected.
8. For `harness_mode=platform`, permit recovery only if every conflict is proven reclaimed-target or baseline-equivalent. For `harness_mode=project`, retain the existing project-owned + reclaimed-target recovery contract.
9. Reset only the ephemeral rollout branch, re-prove baseline equivalence from committed Git state, verify snapshots, run `copier recopy --overwrite --skip-tasks`, then candidate bootstrap.
10. Re-verify protected snapshots, reclaimed target equality, every baseline-equivalent path against the **new** target template state, platform config contract, and harness mode.
11. Any unproven conflict remains fail-closed.

## Rollout service branches

Managed rollout uses the reserved branch form `dev-platform/rollout-vX.Y.Z`. That branch is automation infrastructure, not an interactive agent task. Interactive work continues to use `agent/<task>` through `start_task.py`/`start_worktree.py`; rollout MUST NOT weaken that contract by globally accepting arbitrary `dev-platform/*` branches in task lifecycle validation.

Rollout validation therefore stays on the rollout-specific path (`platform_doctor.py` plus selected downstream checks) instead of invoking an interactive task-branch doctor. If a future validation layer needs branch context, only the exact SemVer service-branch form created by `rollout_branch()` may be recognized in rollout context.

## Blocking diagnostics

A fail-closed rollout is useful only if the operator can identify which safety proof or downstream validation command blocked it. The workflow SHALL preserve a non-zero result while surfacing the final managed-rollout blocker as a GitHub Actions error annotation and step summary. This is observability only: it MUST NOT convert a failed rollout into success, skip a guard, push a branch, or open a PR.

The v1.4.16 acceptance run proved that broad `Error:` scraping is unsafe. The v1.4.17 run proved that a generic `^+ ` marker is still ambiguous because compiler/diff output can itself begin with `+`. Therefore `select_checks.py` emits the reserved marker `DEV_PLATFORM_CHECK_COMMAND:` immediately before each selected downstream command. The workflow prefers the stable `Managed rollout: BLOCKED:` marker, then the last structured selected-check marker, and finally a generic exit-code message for failures outside selected checks.

A product-check failure remains blocking; diagnostics only identify which command failed so the correction is based on evidence. The marker carries no secrets beyond commands already printed to the Actions log.

## Agent-consumable terminal diagnostic

Human-readable annotations are not sufficient for reliable automated diagnosis. The rollout SHALL also construct one canonical diagnostic envelope from structured rollout state rather than by asking a later agent to reinterpret the full log.

The envelope is written as JSON with a stable schema. At minimum it contains:

```json
{
  "schema_version": 1,
  "status": "blocked",
  "project": "owner/repo",
  "target_release": "vX.Y.Z",
  "stage": "prepare|copier_update|recovery|platform_validation|downstream_check|publish|unknown",
  "category": "safety_guard|copier_conflict|downstream_check|runtime_environment|publish_guard|unknown",
  "reason": "stable human-readable blocker",
  "command": "selected command or null",
  "exit_code": 2,
  "retry_same_inputs": "safe|pointless|unknown",
  "evidence": {
    "marker": "stable marker or null",
    "conflict_paths": []
  }
}
```

`reason` is concise and suitable for both the Actions summary and agent consumption. `command` comes only from the reserved selected-check marker, never arbitrary shell/compiler output. `conflict_paths` are included only when rollout already has structured conflict knowledge. Secrets, environment dumps, tokens, and unrestricted raw logs are never copied into the envelope.

`retry_same_inputs` is advisory, not executable policy:

- `safe` means the failure is plausibly transient and a same-input rerun does not bypass a safety decision;
- `pointless` means the same immutable inputs are expected to hit the same deterministic blocker and code/config/template state must change first;
- `unknown` is used when the platform cannot prove either case.

The workflow does not auto-rerun from this field. It only prevents an agent from blindly retrying a deterministic safety or validation failure.

The canonical JSON is saved to a predictable file such as `rollout-diagnostic.json`, rendered into the step summary in a compact human-readable form, and uploaded as a named artifact such as `rollout-diagnostic-<project>-<release>`. Artifact upload runs under `if: always()` or equivalent after preparation diagnostics are available, but is non-authoritative: if upload itself fails, the original rollout exit remains the terminal result and the annotation/summary still attempt to expose the blocker.

Exactly one terminal envelope is produced per failed project rollout attempt. Later diagnostic steps may enrich presentation but must not replace the original failure with a different synthetic cause such as "artifact upload failed".

This contract gives an external agent a deterministic path: inspect the failed run, retrieve the named diagnostic artifact or summary, classify the blocker, then decide whether code/config work is required. Full job-log retrieval remains a fallback for additional evidence, not the primary way to discover the failure.

## Downstream runtime parity

The v1.4.18 diagnostic identified the real remaining Cuby blocker as `cd apps/web && npm run build`. The same web build had just passed Cuby's normal PR gate, whose generated platform workflow explicitly pins Node `20.19.0`. Managed rollout, however, set up Python but relied on the hosted runner's ambient Node executable. That makes rollout validation semantically different from the downstream gate it is supposed to preflight.

Managed rollout therefore pins the same platform-owned Node runtime as the generated platform CI before running downstream selected checks. This is not a Cuby-specific exception: both workflows are platform-owned and must use the same supported Node baseline. Python remains pinned to `3.11` in both paths. Project-owned harnesses still control the commands they execute; rollout only supplies the same base runtime that the platform-generated gate supplies.

If a future platform release changes the generated CI Node baseline, rollout and its tests must change in the same release so validation cannot silently drift again.

## Git/tag handling

Managed rollout already executes tooling from the exact immutable target release. If the older recorded tag is not present in that shallow checkout, rollout fetches only that exact old tag before computing template fingerprints. Failure to fetch or inspect it blocks recovery.

This proof remains reproducible because both sides are immutable Git objects: downstream rollout starts from a clean committed `HEAD`, and the old platform state is a stable SemVer tag.

## Compatibility and rollback

No downstream format changes are introduced. If recovery cannot prove safety, behavior stays fail-closed: rollout stops without pushing a branch. Removing baseline-equivalence recovery restores the stricter v1.4.14 behavior. Removing the diagnostic improvements only reduces observability and does not alter recovery eligibility. Removing runtime parity restores reliance on the hosted runner's ambient Node and is therefore not an acceptable forward configuration while generated CI pins Node.

The diagnostic artifact is additive. Consumers must tolerate unknown future fields and key behavior off `schema_version`, `status`, `stage`, and `category` rather than exact JSON byte shape. A diagnostic-generation failure must degrade to the existing annotation/summary behavior, never to rollout success.

## Validation

Unit tests cover target-equivalent reclaimed recovery, exact old-baseline and missing/missing proof, the actual mixed Cuby reject set, and real-divergence blocking. Workflow/helper tests cover preservation of failure, structured marker precedence, rejection of broad/ambiguous log scraping, gating of push/PR creation, equality of the Node runtime pinned by managed rollout and the generated downstream gate, deterministic diagnostic-envelope generation, category/stage mapping, same-input retry advisory, secret exclusion, and preservation of the original failure when artifact upload/presentation fails. Existing project-harness guarded-recopy tests remain green. The final immutable release is then exercised against real Cuby rollout before archive.
