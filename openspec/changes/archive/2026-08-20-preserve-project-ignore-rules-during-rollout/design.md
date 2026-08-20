# Design: Fail closed on ignore-rule loss

## Ownership boundary

Treat `.gitignore` as a project-owned surface after initial render. The deterministic preservation boundary is the complete existing file: Copier seeds the platform baseline only for new projects and skips `.gitignore` on every later update, regardless of harness mode. This avoids ambiguous section merging and survives repeated Copier updates without machine-local state.

## Rollout safety

Before a managed rollout is considered safe to publish, compare the effective ignore behavior around the render. If a path/class that was ignored before the managed update becomes visible because the rendered managed files removed ignore coverage, stop the rollout with a precise diagnostic. Use representative synthetic paths for local secrets, databases, dependencies and build products; do not inspect or copy real secret contents.

The validation is a defense-in-depth guard, not a substitute for the ownership boundary. A rollout should normally preserve the rules; the guard catches regressions in that mechanism or future template changes.

## Compatibility

New-project rendering still seeds the platform baseline. Existing projects retain project additions. Existing guarded-recopy and project-owned-file safety remain fail closed. The change must not auto-delete, stage or commit newly visible local artifacts.

## Verification

Use a controlled managed-project fixture with project-owned ignore extensions, run the same Copier update path used by managed rollout, and assert both textual preservation where applicable and effective `git check-ignore`/status semantics. Include a negative fixture that deliberately removes coverage and proves rollout publication is blocked.
