# Verification

OpenSpec-Verify: PASS
Verification-Method: equivalent semantic completeness/correctness/coherence review plus Platform CI gate

## Evidence

- The change writes only to the current clone's Git metadata under `.git/info/exclude`; it does not modify a mature project's tracked `.gitignore`.
- Existing tracked files under `.claude/` remain tracked because Git ignore rules do not hide modifications to already tracked paths.
- Generated untracked Claude/Codex integration paths are suppressed before OpenSpec refresh.
- The helper is idempotent and regression-tested by invoking it twice and asserting each pattern appears once.
- Platform CI must pass unit tests, strict OpenSpec validation, all rendered profiles, Copier upgrade smoke and mature project harness smoke on the final PR head.
