## Why

Source backlog issue: `lehard/development-backlog#20`  
Prepared against: `lehard/dev-platform@5eb43498ec0ba996932adf9d0a46d1df5993e29a`

Two process-friction reports expose a weak subprocess boundary in platform-owned execution. `lehard/dev-platform#152` shows repository-scoped Git environment variables leaking into validation commands and contaminating temporary repository object-store behavior. `#153` shows Git command failures surfacing as raw `CalledProcessError` tracebacks even though useful stderr had already been captured.

Both problems belong to the same reliability layer: subprocesses should receive only the repository context they actually need, and failures at that boundary should remain actionable and safe.

## What Changes

- Sanitize repository-scoped Git environment overrides from platform-owned validation/check subprocesses by default so child commands can create/use independent repositories safely.
- Scope any required Git repository override to the exact operation that needs it rather than allowing it to leak into later validation commands.
- Convert checked Git command failures into bounded actionable platform diagnostics containing command, cwd, exit code and sanitized useful output.
- Preserve `check=False` semantics for callers that intentionally inspect return codes and preserve existing structured/resumable lifecycle blockers.
- Add regression coverage for temporary-repository isolation and diagnostic redaction/formatting.
- Keep the change bounded; do not introduce a generalized subprocess framework or redesign validation selection.

## Capabilities

### Modified Capabilities

- `platform-ci`: platform-managed validation commands execute in a repository-neutral subprocess environment unless explicit scoped context is required.
- `platform-lifecycle`: Git execution failures exposed by platform-owned lifecycle surfaces are actionable, bounded and sanitized without destroying resumable error semantics.

## Impact

Expected implementation touchpoints include the check runner and common Git execution helper/callers. Implementation preflight should identify the minimum safe Git-environment denylist/scoping boundary from real Python/Git behavior rather than inventing a broad environment scrubber.
