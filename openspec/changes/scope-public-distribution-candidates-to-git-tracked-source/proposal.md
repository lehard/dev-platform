# Proposal: Scope public-distribution candidate set to Git-tracked source

## Why

`scripts/public_distribution.py` builds its "one deterministic candidate file
set" (the accepted `public-distribution` requirement "Public audit covers the
exact public snapshot candidate set") by walking the filesystem with
`root.rglob("*")`. Any file physically present under the checkout — including
untracked scratch/local files never committed to Git — is treated as
repository source: it is audited, can block the snapshot with an
operator-state/compatibility-marker finding, and would be packaged into the
snapshot archive if it happened to pass.

A live cutover walkthrough hit exactly this gap: an untracked local audit note
(`.local/audits/DEV_PLATFORM_EVOLUTION_AUDIT.md`, listed in
`.git/info/exclude`, never `git add`ed) blocked `audit` even though it is not,
and never was, part of the repository's committed source. The fresh public
repository is supposed to be built "from a verified sanitized snapshot" of
repository source (see the spec's clean-history and
self-contained-source-repository requirements); untracked working-tree state
was never meant to be candidate repository source at all. Solving this by
blanket-excluding `.local/` or hidden directories would only mask this one
instance and leave the same class of gap for the next untracked file anywhere
else in the tree — the fix belongs at the candidate-set source, not in the
exclusion policy.

## What Changes

- Derive the public-distribution candidate file set from Git-tracked files of
  the current checkout (`git ls-files -z`, correctly handling filenames)
  instead of a full filesystem walk, then apply the existing
  `EXCLUDED_PARTS`/`EXCLUDED_PATHS`/cutover-policy exclusions on top,
  unchanged.
- Fail closed with an actionable error when the root is not a readable Git
  checkout or `git ls-files` cannot be run, instead of silently falling back
  to scanning the filesystem.
- Add regression coverage proving untracked local files (including one
  carrying a private/cutover-policy-style marker) never enter
  `candidate_files`, never affect `candidate_sha256`, never produce findings,
  and never enter the snapshot archive — while the same material in a tracked
  file still blocks the audit exactly as before.

## Impact

- `scripts/public_distribution.py` only; no change to the exclusion policy,
  cutover-policy schema, secret patterns, or canonical-repository allowlist.
- The existing `public_distribution` test module gains the new regression
  cases; all existing tests must remain green, unchanged in intent.
- No architecture change, no new mechanism, no GitHub repository admin
  action, no downstream migration, no old-history rewrite.
