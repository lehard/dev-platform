# Design: Git-tracked candidate source for public distribution

## Context

`public_files()` in `scripts/public_distribution.py` is the single source of
the "one deterministic candidate file set" required by the accepted
`public-distribution` spec and consumed identically by both `audit` and
`snapshot`. It currently implements this by walking every file physically
present under `root` and filtering only by `EXCLUDED_PARTS`/`EXCLUDED_PATHS`
(plus, for audit's content scan, the cutover policy). That candidate source
conflates "everything on disk under the checkout" with "the repository's own
source" — they are the same thing only in a perfectly clean working tree. A
real cutover run hit exactly this gap: an untracked, `.git/info/exclude`d
local audit note blocked the audit despite never being part of the
repository's committed history and never destined for the fresh public
snapshot.

This is a hardening/correctness fix to an existing, actively-governed
security boundary (this exact file/spec has previously gone through
`productize-public-core-for-external-use`,
`harden-public-distribution-operator-and-gitlab-boundaries`,
`complete-public-snapshot-source-boundary`, and
`finalize-public-snapshot-identity-boundary`), not a new architecture.

## Decisions

1. **Candidate source becomes `git ls-files`, not `rglob`.** `public_files()`
   enumerates the current checkout's Git index (`git ls-files -z --cached`
   run with `cwd=root`) instead of walking the filesystem. The existing
   `EXCLUDED_PARTS`/`EXCLUDED_PATHS`/cutover-policy exclusion logic is applied
   unchanged on top of that list — the fix is scoped to the source of paths,
   not the exclusion policy itself, per explicit instruction not to solve
   this with a blanket `.local`/hidden-directory exclude.
2. **`-z` for correct filename handling.** Use NUL-separated `git ls-files -z`
   output rather than newline-split, so filenames containing newlines or
   other unusual bytes are handled correctly.
3. **Fail closed outside a Git checkout.** If `git ls-files` cannot be run
   (non-zero exit, `git` missing, or `root` is not inside a Git work tree),
   `public_files()` raises immediately with an actionable message; there is
   no filesystem-walk fallback. This matches the existing fail-closed posture
   for cutover-policy loading (`CutoverPolicyError`) and history-audit's own
   "requires a readable Git repository" check.
4. **No change to what counts as excluded.** `EXCLUDED_PARTS`,
   `EXCLUDED_PATHS`, `policy_extra_excluded`, `PROHIBITED_PATHS`,
   `SECRET_PATTERNS`, and the cutover-policy schema are untouched. `git
   ls-files` already never returns `.git/` internals or untracked material,
   so this removes an entire class of accidental inclusion without widening
   or narrowing the deliberate exclusion policy.
5. **Existing guarantees preserved exactly.** Audit and snapshot continue to
   consume the exact same candidate list (`public_files()` is still the
   single call site both use); `tests/`, `openspec/specs/`, and `.github/`
   remain tracked and therefore still included; `openspec/changes/archive`
   remains explicitly excluded via `EXCLUDED_PATHS`; a supplied cutover-policy
   file's own path is still removed from the candidate set via
   `policy_extra_excluded` (unaffected by the source-of-paths change, since
   that logic operates on the resulting path set either way).
   `missing_required_paths`/source-completeness smoke still reuses
   `public_files()`, so it now needs the *extracted* snapshot to be a Git
   checkout before re-deriving candidates from it (decision 7 below) --
   the resulting completeness check itself is unchanged.
7. **Snapshot smoke establishes fresh history before re-deriving
   candidates.** `tests/public_distribution_snapshot_smoke.py` already
   establishes the extracted tree's fresh canonical Git history
   (`establish_fresh_history`) later in the same run, to exercise the
   platform lifecycle scripts. That step moves earlier, immediately after
   extraction, so the completeness re-check
   (`public_files(extracted)`/`missing_required_paths`) has a Git checkout to
   read -- exactly the history a real cutover would already have in place by
   that point. This only reorders two already-present steps; it adds no new
   mechanism and does not change what the completeness check proves.
6. **Working tree, not `HEAD`.** `git ls-files` reflects the current
   index/working tree of the checkout being audited (matching today's
   behavior of scanning the live checkout, not a specific commit), so a
   locally modified-but-tracked file's current on-disk content is still what
   gets audited/packaged — only *untracked* files are newly excluded. This
   preserves the existing "current tree" semantics the spec's "Current-tree
   sanitization and Git-history secret audit are separate truthful gates"
   requirement already relies on.

## Verification strategy

- Unit tests construct a temporary Git repository (real `git init`/`git
  add`/`git commit`, not a mock) with: a tracked file, and an untracked file
  carrying a cutover-policy-style marker. Assert: (a) the untracked file is
  absent from `candidate_files`; (b) `candidate_sha256` is identical whether
  or not the untracked file exists; (c) `audit_tree` reports zero findings
  for the untracked marker; (d) the same marker in a *tracked* file still
  produces a finding; (e) `snapshot()`'s output tar does not contain the
  untracked file.
- A test running `public_files`/`audit_tree`/`snapshot` against a plain
  non-Git temporary directory asserts a clear, non-zero-exit failure rather
  than a filesystem-walk fallback.
- All pre-existing `public_distribution` tests continue to pass unchanged.
- Full validation suite (`compileall`, `run_test_groups.py --all`,
  `openspec_lifecycle.py check`) reruns before archive, per the platform's
  standard completion gate.
