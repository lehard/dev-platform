## Why

The existing public/private guard runs after full completion validation. A private reference in candidate evidence or a new commit message can therefore waste a full validation pass before the candidate is rejected.

## What Changes

- Run the existing source-owned private-reference guard in the cheap completion preflight before full checks.
- Preserve the publication-time guard as a race-sensitive recheck.
- Improve guard diagnostics to identify offending surface categories and direct the operator to the supported opaque-lineage path without exposing private identifiers or unsafe filenames.
- Cover the same supported public candidate surfaces, including files, paths, branch, new commit messages and proposed PR text.

## Impact

Source-owned guard, completion preflight, focused regression tests, and completion contract. No new privacy mechanism or published-history rewrite.
