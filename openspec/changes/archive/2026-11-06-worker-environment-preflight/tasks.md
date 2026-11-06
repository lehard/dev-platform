## 1. Preflight
- [x] 1.1 `worker_preflight` conditions by kind and the standalone command.
- [x] 1.2 `work-next --run` refuses before claim naming every unmet condition; job-dependent conditions run after selection and before claim.

## 2. Environment class
- [x] 2.1 `EnvironmentFailure`, the release class and counting outside `MAX_RELEASES`.
- [x] 2.2 Separate bound ending in an operational block lifted by `resume`.
- [x] 2.3 Finalize, post-merge runner and overview handle the class.

## 3. Tests and docs
- [x] 3.1 Unit tests for every scenario, including several unmet conditions at once, old `released` comments and an ordinary failure staying ordinary.
- [x] 3.2 Offline acceptance of a refused run and of a post-claim environment failure.
- [x] 3.3 `docs/engineering/chat-coordinator.md`, `docs/engineering/hosted-lifecycle-workers.md`, manifest.
- [x] 3.4 Full validation, strict `openspec validate` and semantic OpenSpec verification.
