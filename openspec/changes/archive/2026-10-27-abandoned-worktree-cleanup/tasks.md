## 1. Abandonment proof
- [x] 1.1 `publication_state.ExactHeadPrLookup.exact_closed`: exact-head CLOSED unmerged PR; more than one is unavailable.

## 2. Cleanup
- [x] 2.1 `worktree_cleanup.py cleanup --abandoned` with exact target: GitHub proof, local safety checks, worktree and branch removal, exact board-claim release, truthful status and exit code.

## 3. Verification
- [x] 3.1 Tests: success removes worktree, branch and claim; refusals for open/merged/no closed PR, GitHub unavailable, merged ancestry, dirty, active process, identity mismatch, board identity mismatch; argument validation.
- [x] 3.2 Regenerate the platform manifest; run full validation and semantic OpenSpec verification.
