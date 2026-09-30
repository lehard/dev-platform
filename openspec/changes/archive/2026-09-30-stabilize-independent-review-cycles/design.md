## Context

Independent review is enforced by `independent_review.py` (file-backed evidence, `evaluate`, `ensure_review_evidence` at archive preflight, `require_review_evidence` at finish) and launched by `independent_review_runner.py` (provider/model/binary resolution, read-only adapters, content postcheck). The review evidence binds to `task_content_identity.review_content_identity`, which already excludes lifecycle-only paths through `review_exclusion`. Ready-for-integration receipts are written by `execute_requirement._ready_receipt` through `requirement_integration.write_receipt`, which refuses to replace any differing receipt.

## Decisions

### 1. Runtime readiness preflight precedes perspective launch

`independent_review_runner` gains `preflight(root, *, config=None, launcher=None)` returning a small result: `ready`, `provider`, `provider_source`, `model`, `binary`, and `limitation`. It reuses `resolve_provider`, `resolve_model` and `resolve_binary`, then runs one probe through the same launcher abstraction with the exact selected model and the same read-only flags as the real adapter (Claude: headless print mode with the read-only tool list, no session persistence, strict empty MCP config, JSON output; Codex: `exec --sandbox read-only --ephemeral` with the model). The probe prompt asks for a trivial fixed reply, needs no repository content, and has a short bounded timeout (default 120 s, independent of the review timeout). A non-zero exit, error result, timeout or missing binary becomes a limitation that includes the CLI's bounded `runtime_error` message and names the concrete next step (log the CLI in, point `DEV_PLATFORM_CLAUDE_BIN` at the CLI, or change the `[model_routing]` / `[independent_review]` binding for this account). The probe never switches model or provider.

`run_review` calls `preflight` after the dirty-candidate check and request preparation. If it is not ready, both perspective reports are written as `unavailable` with the preflight limitation and no perspective is launched, so archive stops within seconds before expensive validation, exactly as today's unavailable path but earlier and cheaper. The content postcheck also wraps the probe launch, so a probe that mutates the workspace is also unavailable.

The CLI adds `independent_review.py preflight [change]`, printing the JSON result and exiting non-zero when not ready, so an agent can check readiness right after routing and before implementation. `review_state` next-step guidance for a missing review mentions this command. `platform_doctor` is not changed: it also runs in CI, where a live model probe would be wrong.

### 2. Reviewer context equals the identity-bound content

The runner currently writes `git diff merge_base...HEAD` for the whole tree. It will instead diff only the paths the review identity includes: list changed paths with `git diff --name-only merge_base...HEAD`, drop those for which `review_exclusion(root, change, base_ref)` is true, and pass the remaining paths as an explicit pathspec (chunked if needed; an empty remainder yields an empty diff). The request records the excluded lifecycle path list (`excluded_lifecycle_paths`) for auditability, and the prompt states that those paths are lifecycle evidence, are not part of the candidate, and must not be reported as findings. This keeps "what was reviewed" and "what invalidates the review" the same set, so an unchanged candidate with newly committed evidence is neither reviewed about its evidence nor re-reviewed.

The request schema version stays 1; the new field is additive, and `_validate_request` does not require it, so previously recorded evidence remains readable.

### 3. Own stale ready receipt is superseded on proven advancement

`write_receipt(path, payload, *, root=None)` keeps idempotent writes and refusal of foreign content. When the existing file differs, it replaces it only when all hold:

- the existing file parses as a valid receipt (digest verified);
- `requirement`, `source_issue`, `change` and `source_branch` are identical to the new payload;
- the existing head differs from the new head and is a strict ancestor of it (`git merge-base --is-ancestor` in `root`, the child worktree);

otherwise it raises the existing error with a reason (foreign identity, unreadable, divergent/unrelated head, or unprovable). `_ready_receipt` passes the child worktree as `root`. The superseded receipt is not kept as a second active receipt; the replacement is reported in the advance result so the operator can audit it. Receipts consumed by an already composed shared candidate stay safe because `compose_candidate`/`publish_candidate` re-assemble from the current receipts and refuse a manifest mismatch (existing behavior).

## Risks

- A probe costs one tiny model call per review run; acceptable against the long review it can avoid. Probe flakiness fails closed and is rerunnable.
- Pathspec filtering must use literal paths (`:(literal)` magic) to avoid glob interpretation of unusual file names.
- Ancestry proof must run in the repository that owns the child head; when the old head is not resolvable there, supersession is refused.

## Verification

Unit tests for preflight success/failure classes (missing binary, non-zero exit with CLI error, timeout, bad model resolution) with a fake launcher, including that no perspective launches after a failed preflight; reviewer diff excludes lifecycle paths and keeps task paths; request records exclusions; receipt supersession accepts own ancestor advancement and refuses foreign identity, divergent head, equal-head differing content, and unreadable existing receipt; an end-to-end happy path in a temporary repository shows exactly one launch round across archive-style evidence commits and finish-time validation.
