# Tasks

- [x] Introduce a canonical versioned `rollout-diagnostic.json` model produced from structured rollout state rather than arbitrary log scraping.
- [x] Map terminal failures to stable stage/category/reason/exit-code fields and preserve the exact selected command only from `DEV_PLATFORM_CHECK_COMMAND:` markers.
- [x] Add `retry_same_inputs = safe|pointless|unknown` as advisory metadata; do not auto-rerun or weaken any safety gate.
- [x] Include already-known structured evidence such as Copier conflict paths while excluding tokens, environment dumps, secrets, and raw logs.
- [x] Render the same canonical diagnostic into a concise GitHub Actions summary/error annotation and upload a predictably named diagnostic artifact on failure.
- [x] Ensure diagnostic-generation/upload failures never replace the original rollout blocker, change its exit status, push a branch, or create a PR.
- [x] Add regression tests for safety-guard, selected-check, runtime/environment, and unknown failure envelopes plus stable-schema/secret-exclusion behavior.
- [x] Add workflow tests proving exactly one canonical terminal diagnostic per failed project rollout attempt and preservation of the original failure if artifact upload/presentation fails.
- [x] Re-run platform CI/OpenSpec validation and semantic verification on the exact final implementation.
- [x] Record `OpenSpec-Verify: PASS` plus verification method for this change; do not release or roll out until instructed.
