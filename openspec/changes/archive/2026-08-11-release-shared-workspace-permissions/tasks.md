## 1. Prepare the immutable platform release

- [x] 1.1 Verify `v1.4.25` is immutable/published and `v1.4.26` is unused.
- [x] 1.2 Change `VERSION` to `1.4.26` and verify that the release workflow
  will dispatch rollout for that exact tag.

## 2. Verify and archive the source contract

- [x] 2.1 Run the relevant platform checks and semantic OpenSpec review.
- [x] 2.2 Record the actual verification receipt and archive the change before
  publishing the release PR.

## 3. Prepare delivery and post-merge observation

- [x] 3.1 Prepare the archived release change for delivery through the managed
  lifecycle; delivery is the publication boundary, not an archive prerequisite.

After merge, observe the GitHub release and exact-version rollout run, then
record the release URL and each managed project's reviewed PR or bounded
diagnostic on the Development Backlog issue. This is external operational
evidence, not a source change that would reopen the archived OpenSpec package.
