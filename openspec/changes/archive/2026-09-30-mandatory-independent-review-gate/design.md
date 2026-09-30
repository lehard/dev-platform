# Design: Platform-launched independent review gate

## Runner and adapters

`independent_review.py run <change> [--base origin/main]` prepares (or reuses a current) request and launches one fresh process per perspective. The reviewer provider defaults to the current task route's provider (`model_routing` durable route); `[independent_review] provider` may name another provider explicitly, which is the only way cross-provider review happens. The model comes from the existing `[model_routing]` profile mapping (`[independent_review] profile`, default `standard`), so no model is part of the contract.

- Codex: `codex exec --sandbox read-only --ephemeral --cd <worktree> --model <m> --output-schema <schema> --output-last-message <file>`; the thread id from `--json` events is the context id when present.
- Claude Code: `<claude> -p --tools Read,Grep,Glob --permission-mode dontAsk --no-session-persistence --output-format json --json-schema <schema> --model <m>`, run with the worktree as cwd. The binary is resolved from `DEV_PLATFORM_CLAUDE_BIN` (machine-local), then `claude` on PATH. The allowlist excludes every write-capable and shell tool.

The prompt is built only from the request (candidate identity, perspective objective, contract/guidance paths, and a precomputed diff file under a temporary directory outside the repository). Output must match a findings schema; stdout/stderr and prompts are not persisted. Each report records `reviewer.runtime`, `context_id`, `fresh_context: true`, `write_access: false`, `launch_evidence: "platform-observed"`, the enforced read-only mechanism, the resolved model with `selected` provenance, and a digest of the raw structured output.

Failure modes (binary missing, nonzero exit, timeout, malformed output, workspace mutation) produce an `unavailable` report with an actionable limitation; they never produce findings or silent success.

## Read-only and fresh proof

Before launch the runner snapshots the task worktree and integration checkout with the existing `model_routing` content snapshot; after exit it re-checks. Any mutation invalidates the report (`unavailable`, limitation names the paths) and the runner does not repair or clean anything. Freshness is the new process with no resume/session persistence; independence from the implementer's memory follows from the request-only prompt.

## Candidate binding

Evidence binds to `task_content_identity.content_identity` computed with an exclusion set: the change's `verification.md`, `evidence/`, `automated-checks.json`, `independent-review-request.json`, `independent-reviews/`, the dispositions file, and `openspec/specs/*` paths materialized from the change's own delta specs. `equivalent_proofs` then accepts the archive move and an irrelevant clean main merge and rejects every other change. The legacy exact base/head/diff fields remain as provenance.

## Dispositions

`independent_review.py dispose <change> --perspective P --finding ID --status rejected|blocker --rationale TEXT` writes `independent-review-dispositions.json` bound to the report digest. `fixed` is not recordable against the same candidate: a fix changes the candidate and requires a fresh run. Validation blocks on any material finding without a `rejected` disposition bound to the current report.

## Lifecycle gate and resume

Required when `[independent_review] enabled = true` and the change has managed provenance. `openspec_lifecycle.py archive` preflight: after deterministic cheap checks and before expensive validation, if evidence is missing or stale it runs the reviewer automatically, then validates; a blocking result stops archive with the findings and exact next commands. `verification.md` must cite the evidence. `dogfood_task.py finish` re-validates evidence against the current content identity (locating the archived change) before any publication step. `dogfood_task.py status` and `execute_requirement.py advance` include a derived `independent_review` state (`not-required`, `missing`, `stale`, `blocked`, `ready`) and next command. No new state store: state is the files in the change directory.

## Scope and compatibility

The central `.dev-platform.toml` sets `enabled = true`. In dev-platform that file is the central checkout's machine-local operator configuration (excluded from the public candidate), so the flag is applied to the integration checkout's copy once this change merges; enabling it earlier would block in-flight tasks still running pre-gate code. The template default stays `false`, so Copier updates do not change downstream projects. Quick tasks lack managed provenance and are never reviewed. `record` remains for compatibility but reports without platform-observed launch evidence do not satisfy a required review.
