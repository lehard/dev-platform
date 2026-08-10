# Verification

OpenSpec-Verify: PASS
Verification-Method: manual semantic OpenSpec review plus implementation-head Platform CI and live Cuby rollout failure evidence

## Evidence reviewed

The original v1.4.13 managed rollout to Cuby failed in Dev Platform workflow run `31377166302` because Copier replayed historical downstream changes and left `scripts/project_publish.py.rej`, even though Cuby's repaired `scripts/project_publish.py` had already been reconciled to the exact v1.4.13 platform template. This established that the remaining blocker was rollout recovery semantics rather than the protected-PR merge implementation itself.

Implementation head `5ef4933aac73d2e197110f61257efcf640e3be8e` passed Platform CI run `31378737906` end to end. The run completed shared-script compilation, managed-project registry validation, the full unit suite, OpenSpec lifecycle hygiene, strict OpenSpec validation, factory profile rendering, Copier upgrade smoke tests, mature project-harness adoption smoke tests, and the project-harness smart-update fallback smoke.

## Semantic review

The implementation matches the approved safety contract:

- target-equivalent recovery is available only for a narrow allowlist of platform-owned lifecycle files;
- eligibility is proven before `copier update` by exact-byte fingerprint comparison against the checked-out immutable target release template;
- `harness_mode=platform` permits guarded recopy only when every reject target was in that pre-proven set;
- any real or mixed downstream divergence remains a hard failure before publication;
- project-owned harness recovery remains governed by its existing protected-file snapshot contract;
- guarded recopy still verifies project configuration invariants, preserves `harness_mode`, runs the candidate platform bootstrap, then runs the normal doctor/selected-check validation before a rollout commit can be produced.

Regression coverage includes both the Cuby-shaped `scripts/project_publish.py.rej` recovery case and the inverse case where a genuinely modified platform file is rejected and recopy is not attempted.

## Finding

PASS. The change closes the v1.4.13 rollout dead-end without weakening Copier conflict handling or downstream PR/CI review. Release and managed rollout are operational follow-up after archive/merge, not prerequisites for semantic verification.
