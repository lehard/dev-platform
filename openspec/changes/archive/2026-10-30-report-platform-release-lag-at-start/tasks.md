## 1. Lag observation
- [x] 1.1 `rollout_preflight`: `PlatformLagError`, `platform_source_repository`, `latest_platform_release`, `observe_platform_lag` (current / behind with the exact command / not-applicable for the source).
- [x] 1.2 `start_task`: evaluate after pending-rollout reconciliation with a re-read config, print the report when behind, continue; a `PlatformLagError` stops the start.

## 2. Tests
- [x] 2.1 Behind prints both versions and the command and the task starts; current prints nothing; source repository is not applicable; each undeterminable input fails with its cause; `_src_path` forms parse. Regenerate the platform manifest.

## 3. Verification
- [x] 3.1 Full validation and semantic OpenSpec verification.
