# Design

## Relationship to existing rollout diagnostics

`allow-safe-reclaimed-rollout-recopy` already added the `Managed rollout: BLOCKED:` stable-reason marker, the `DEV_PLATFORM_CHECK_COMMAND:` reserved selected-command marker, and a GitHub Actions error annotation/summary built from them. This change builds strictly on top of that existing, already-shipped mechanism — it does not modify recopy/recovery eligibility, does not reopen that change's scope, and does not edit its files.

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

## Compatibility and rollback

The diagnostic artifact is additive. Consumers must tolerate unknown future fields and key behavior off `schema_version`, `status`, `stage`, and `category` rather than exact JSON byte shape. A diagnostic-generation failure must degrade to the existing annotation/summary behavior, never to rollout success. Removing this change restores the prior human-annotation-only observability without affecting recovery/recopy eligibility or any safety gate.

## Validation

Unit tests cover deterministic diagnostic-envelope generation, stage/category mapping for safety-guard, selected-check, runtime/environment, and unknown failures, the same-input retry advisory, secret/log exclusion, and preservation of the original failure when artifact upload/presentation fails. Workflow tests prove exactly one canonical terminal diagnostic is produced per failed project rollout attempt.
