## 1. Discovery
- [x] 1.1 `lifecycle_workers.candidate_prs`: complete `lifecycle:merged` label scan minus `post-merge:settled`; `only_prs` reads `pulls/N` directly.
- [x] 1.2 `lifecycle_workers.work_next`: `settle` callback for a settled merged candidate; `work-next` posts the label unless `--dry-run`, passes `--pr` to discovery.
- [x] 1.3 `lifecycle_overview`: bound note names the label scan.

## 2. Tests and docs
- [x] 2.1 Tests: out-of-window merged PR with an open obligation is offered by the worker and shown by the overview; settled PRs are skipped and marked; exhausted/open ones never marked; dry-run writes nothing; `--pr` reads directly; unreadable label listing fails explicitly.
- [x] 2.2 `docs/engineering/chat-coordinator.md` bound wording; regenerate the platform manifest.

## 3. Verification
- [x] 3.1 Full validation and semantic OpenSpec verification; confirm #678 and #681 appear in a dry-run discovery.
