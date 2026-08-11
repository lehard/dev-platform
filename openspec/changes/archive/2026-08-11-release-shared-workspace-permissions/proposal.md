## Why

Development Backlog #12 delivered shared-workspace permission enforcement in
merged source commit `62d1eba`. Managed projects must receive that behavior
from an immutable platform version rather than mutable source history.

## What Changes

- Bump `VERSION` from `1.4.25` to the next unused patch version and publish the
  resulting immutable GitHub release from its merged release PR.
- Verify before publication that the existing release workflow dispatches
  managed rollout for that exact tag.  After the merge, observe its external
  GitHub evidence and record it on the Development Backlog issue; this
  operational observation is deliberately not a prerequisite for archiving
  the source OpenSpec change.
- Preserve the rollout safeguards: no force-push or auto-merge, and no
  mutation of `candidate`/`excluded` inventory entries.

## Impact

- Affected operational behavior: immutable version publication and managed
  rollout only.
- Depends on merged source PR #159 and the existing version/rollout workflows.
