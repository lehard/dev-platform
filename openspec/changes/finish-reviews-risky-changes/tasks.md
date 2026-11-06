## 1. Rule and evidence
- [x] 1.1 `risky_paths` and the surface lookup, with explicit errors.
- [x] 1.2 `review_is_required` uses the rule for quick and managed tasks.
- [x] 1.3 Quick review directory, task content, path partition, reviewer inputs and request paths.
- [x] 1.4 Reserved target `quick-task` for the review commands, so next-step messages work unchanged.

## 2. Finish
- [x] 2.1 Review stage for a risky quick task on GitHub and GitLab, and a printed decision for every finish.
- [x] 2.2 Status shows the quick review state.

## 3. Configuration and contract
- [x] 3.1 Enable review in `dev-platform/source-contract.toml` and the installed config; update the template comment.
- [x] 3.2 Decision record replacing item 5 of DEC-0009; workflow documentation and change classes.

## 4. Verification
- [x] 4.1 Tests for the rule, the predicate, quick evidence, a finding, a reviewer that cannot start, reuse and staleness.
- [ ] 4.2 One real `finish` with a real LLM reviewer on a risky change, and one real `finish` with no reviewer on a non-risky change, with time and launch counts.
- [ ] 4.3 Full validation, strict `openspec validate` and semantic OpenSpec verification.
