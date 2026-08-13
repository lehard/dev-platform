## 1. Add single-writer ownership

- [x] 1.1 Define the bounded active-writer identity for one assigned worktree.
- [x] 1.2 Refuse a second write-capable Codex launch while the existing writer is live or ambiguous.
- [x] 1.3 Keep ownership updates race-safe for concurrent local launch attempts.

## 2. Make abnormal cleanup authoritative

- [x] 2.1 Track the launched child/process tree through the existing observed delegation path.
- [x] 2.2 On timeout, cancellation or abnormal return, terminate and reap relevant descendants before releasing writer ownership.
- [x] 2.3 Preserve truthful failure/containment reporting while cleanup runs.

## 3. Verify

- [x] 3.1 Add controlled duplicate-launch regression coverage.
- [x] 3.2 Add abnormal-return/orphan cleanup regression coverage.
- [x] 3.3 Run relevant model-routing/delegation/lifecycle checks and strict OpenSpec validation.
