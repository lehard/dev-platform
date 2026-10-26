## 1. Job kind and executor
- [x] 1.1 Add `integration-merge` to `JOB_KINDS`; `work-next --run` needs no `--llm-command` for it and `--writer` does not apply; dispatch it to the integration executor.
- [x] 1.2 `integration_contour`: accept the kind without a provider; fail it by name on conflicts or a `required-checks` gate without a writer; the failure offers `integration-repair` next.

## 2. Queue
- [x] 2.1 Offer `integration-merge` for the `integration` gate with a clean trial merge, marking the red gate `merge_only`; keep the kind on republish and validated-push recovery; skip the repair attention for it.

## 3. Hosted class
- [x] 3.1 Add the `integrate` class to `hosted_workers.CLASSES` and `integrated` to the resulted outcomes; update `docs/engineering/hosted-lifecycle-workers.md`.

## 4. Verification
- [x] 4.1 Tests: queue offers the right kind; executor merges without a writer and fails by name on a conflict, then the next job is integration repair; hosted plan/preflight/outcome for the class; recovery keeps the kind.
- [x] 4.2 Run full validation and semantic OpenSpec verification.
