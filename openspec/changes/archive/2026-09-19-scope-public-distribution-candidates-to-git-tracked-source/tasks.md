# Tasks: Scope public-distribution candidate set to Git-tracked source

- [x] 1. Implement `git ls-files -z`-based candidate enumeration in
      `public_files()` in `scripts/public_distribution.py`, replacing
      `root.rglob("*")`, applying the existing
      `EXCLUDED_PARTS`/`EXCLUDED_PATHS`/policy exclusions unchanged on top.
- [x] 2. Fail closed with an actionable error when `root` is not a readable
      Git checkout or `git ls-files` fails (no filesystem-walk fallback).
- [x] 3. Add regression tests: untracked file with a private/cutover-policy
      marker is excluded from candidate set/digest/findings/snapshot; the
      same marker in a tracked file still blocks audit; digest is stable
      whether or not the untracked file exists; running outside a Git
      checkout fails closed with a clear error.
- [x] 4. Run full validation (`python3 -m compileall -q template/scripts
      scripts`, `python3 scripts/managed_projects.py validate`, `python3
      scripts/run_test_groups.py --all`, `python3
      template/scripts/openspec_lifecycle.py check`) and confirm all
      existing `public_distribution` tests remain green.
- [x] 5. Update `openspec/specs/public-distribution/spec.md` via the
      MODIFIED requirement delta declared in this change; write a truthful
      `verification.md`; archive through
      `template/scripts/openspec_lifecycle.py archive`.
- [x] 6. Resolve the friction checkpoint
      (`scripts/agent_friction.py checkpoint --result none`, or the id of a
      recorded event) before reporting completion.
