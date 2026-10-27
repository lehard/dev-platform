## 1. Regression test
- [x] 1.1 Build the composition fixture (sealed manifest, two archived children, one changing the generated manifest), a main that changes a neighbouring manifest entry, and a trusted checkout declaring the generated file.
- [x] 1.2 Run `publication_queue.worker` through the real derived merge to `merged`; assert the merge shape, regenerated manifest, unchanged composition identity, and no repair or merge job, no update-branch and no attention comment.

## 2. Verification
- [x] 2.1 Run full validation and semantic OpenSpec verification.
