## Context

- `run_worker(root, mode, env)` runs the full preflight and then candidate work in either mode. In CI the workflow exports an App installation token as `GH_TOKEN`; locally the worker uses the operator's `gh` login.
- `_preflight_runtime` ends with a CI installation-token probe or, locally, a `repos/{repo}` probe that requires `permissions.push`.
- `harness_push_env(checkout, env)` accepts a `file://`/local origin without credentials, requires an uncredentialed `https://github.com/...` origin otherwise, and raises `harness GitHub push requires coordinator GH_TOKEN` when `GH_TOKEN` is absent. Local `work-next` operators export `GH_TOKEN` by hand; `requirement_contributions.push_fast_forward` (reached from `execute_requirement.py advance`) inherits the process environment and fails when it is absent.
- `gh auth token` prints the active token with gh's documented precedence (`GH_TOKEN` environment, then the stored login) and exits non-zero when none exists.

## Decisions

1. **Local worker refuses before any GitHub read.** `run_worker` with `mode == "local"` returns `{"state": "error", "reason": ...}` without running preflight or reading candidates. The reason names the CI `publication-queue` workflow as the only integrator and the supported local commands (`status`, `preflight --mode local`). The CLI keeps `--mode local` accepted for `worker` so the refusal is a named diagnostic, not an argparse error. Exit code stays the existing non-zero error code.
2. **Local preflight stops proving push.** The local branch of `_preflight_runtime` no longer calls the repository-permission probe; pull-request read remains the last runtime proof. The CI branch is unchanged.
3. **One credential source for the harness push.** `harness_push_env` runs `gh auth token` with the given environment (`GH_PROMPT_DISABLED=1`, stdin closed, output captured) and uses its stdout. A non-zero exit or empty output raises `WorkerError("harness GitHub push requires an authenticated gh credential (gh auth token failed)")` without echoing gh output. There is no second path: gh itself resolves `GH_TOKEN` first, so the CI App token keeps working unchanged, and a local operator login is used when nothing is exported. Local `file://` harness origins keep requiring no credential. The token is placed only in the existing `http.<origin>.extraheader` config of the push process.
4. **Docs.** Replace the local worker retry sentence in `agent-workflow.md` with: the scheduled CI workflow is the only integrator; locally use `status` and `preflight --mode local` to diagnose.

## Rejected alternatives

- Keeping `GH_TOKEN` as required and only rewording the message: leaves the `advance` blocker in place.
- "Use `GH_TOKEN` if set, else ask gh" in platform code: a two-path fallback; delegating precedence to gh keeps one source of truth.
- Removing `--mode local` from `worker` entirely: an argparse error is less actionable than a named diagnostic.

## Risks and mitigations

- *Owner token can still call the merge API.* Not closed by code; the parent Requirement's ruleset on `main` (bypass only the App in pull-request mode) closes it. This change only removes the platform's own local merge path.
- *Token leakage in diagnostics.* gh output is never included in errors; existing tests asserting no token in argv/errors are extended to the gh path.
