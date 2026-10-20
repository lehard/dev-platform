## 1. Merge call

- [x] 1.1 Replace `gh pr merge --squash --match-head-commit` in the coordinator integration step with `gh api -X PUT repos/{repo}/pulls/{number}/merge -f merge_method=squash -f sha=<head>`, keeping the read-back and waiting outcome.

## 2. Tests and evidence

- [x] 2.1 Update fakes and add tests: exact REST argv with the expected head; refusal (405/409 payload) yields the waiting reason and no merged transition.
- [x] 2.2 Regenerate the platform manifest; run required validation and semantic verification (archive and merge are performed by coordinator finalization and the CI publication queue).
