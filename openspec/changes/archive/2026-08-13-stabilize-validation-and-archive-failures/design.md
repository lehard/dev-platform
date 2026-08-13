# Design: Fail fast, then validate once

## 1. Deterministic parallel validation

Reproduce the shared-workspace failure under the actual group runner. Fix fixture initialization/permissions so temporary repositories do not depend on scheduler interleaving. If the affected group has a real shared mutable invariant that cannot be isolated cheaply, mark only that group non-concurrent.

The controlled `--all --jobs 12` run on current `main` completed without the historical setgid false failure. The recently archived `stabilize-dogfood-validation-failure-signals` change already replaced the confirmed contention-sensitive timing assumptions and added its regressions. This change therefore preserves the existing parallel grouping and permission assertions rather than adding unproven serialization or retries.

## 2. Structured failure classification

The selector/runner exposes a bounded failure descriptor containing the selected check or group and a sanitized failure class. The completion lifecycle passes that descriptor into friction reporting rather than replacing it with a generic exit-code observation.

The descriptor is a compact JSON marker: selected check IDs, the selected command, exit code, broad failure class, and (when the group runner emits it) up to 20 failed group IDs. Raw command output remains on the existing local/command surface and is never copied into friction evidence.

## 3. Archive readiness preflight

Before invoking `select_checks`, archive validates the active change, completed tasks, semantic verification receipt shape, required automated-evidence marker, and the presence of an applicable committed diff/state. A deterministic failure occurs before evidence file creation or overwrite.

## 4. Evidence after readiness

Only a ready archive invocation executes the selected checks and writes authoritative `automated-checks.json`. The existing evidence validation and strict OpenSpec archive sequence remain unchanged afterward.

## 5. No retry masking

Retries are not used to turn timing-sensitive or permission failures green. The fix must either remove the race or narrow concurrency explicitly.
