## 1. Root convergence

- [x] 1.1 Add marker aliasing and `resolve-candidate --same-root|--new-root` for events in `candidate` state
- [x] 1.2 Add idempotent `merge-roots --into --duplicate` for open router-generated friction issues

## 2. Closing on fix

- [x] 2.1 Add `close-fixed --pr --repo` that parses `Fixes-Friction:` references from the PR body and changed `proposal.md` files at the merge commit and closes the referenced friction issues with a comment
- [x] 2.2 Add `.github/workflows/friction-close-on-merge.yml` and document the reference line in the agent workflow guide

## 3. Verification and delivery

- [x] 3.1 Add regression tests for aliasing, candidate resolution, root consolidation, reference parsing, named errors and idempotent reruns
- [x] 3.2 Run the selected checks and full validation, record semantic verification, archive and publish
