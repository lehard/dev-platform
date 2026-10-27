## Why

Platform CI runs on Python 3.11 while local validation runs on whatever `python3` is on PATH (3.13 on the owner's Mac). A test with 21 context managers in one `with` statement compiled on 3.13 and failed on 3.11 with "too many statically nested blocks"; local full checks were green and the defect surfaced only in required CI on the integrated candidate.

## What Changes

- New repository-owned check `scripts/check_ci_python.py`. It reads the `python-version` of the single `actions/setup-python` step of a named job in a named workflow. When the running interpreter's `major.minor` equals it, the check reports the match and passes. Otherwise it locates `python<major.minor>` on PATH, confirms that interpreter reports exactly that version and runs `-m compileall -q` over the named paths with it, failing when compilation fails.
- Refusals name both versions: a workflow or job that cannot be read, no or several `setup-python` steps, a version that is not `major.minor`, a missing interpreter, or an interpreter reporting another version. No default version and no substitute interpreter.
- `dev-platform/checks.toml` adds the check to the full command set and to the Python check set.
- The step catches compile-time errors only; runtime behaviour differences between Python versions are not caught by it. This is stated in the spec and the verification receipt.

## Impact

- `scripts/check_ci_python.py` (new, platform-owned), `dev-platform/checks.toml`.
- `AGENTS.md` and `docs/engineering/agent-workflow.md` validation command lists.
- Tests: new `tests/test_check_ci_python.py`, registered in a test group.
- Spec: platform-ci.
- The owner's Mac needs a `python3.11` on PATH for full local validation; it exists today (no packages are needed for compilation).
