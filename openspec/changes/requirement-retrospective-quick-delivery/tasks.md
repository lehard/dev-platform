## 1. Retrospective

- [x] 1.1 Accept `--quick-pr` (merged PRs, recorded in the receipt); accept an empty child set only with at least one quick PR; validate it in `require_checkpoint`.

## 2. Verification

- [x] 2.1 Tests: Requirement without children with quick PRs records and checks; without quick PRs and with an unmerged PR it is refused; managed children unchanged. Run selected checks and semantic verification.
