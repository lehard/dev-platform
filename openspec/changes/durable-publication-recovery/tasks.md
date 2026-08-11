## 1. Publication-state foundation

- [ ] 1.1 Add a versioned, atomic, machine-local publication-state and lease helper, default configuration path, and ignore coverage without storing credentials.
- [ ] 1.2 Add unit coverage for state validation, candidate-SHA mismatch, corrupt/missing state recovery, lease contention/expiry, and sanitized status output.
- [ ] 1.3 Commit the state foundation and tests as an independently reviewable change.

## 2. Safe publication and authentication

- [ ] 2.1 Refactor platform-owned PR publication into persisted idempotent phases that reuse the existing feature branch and PR.
- [ ] 2.2 Add `finish_task` status/resume behavior, single-flight protection, phase milestones, and merge-only board/worktree completion behavior.
- [ ] 2.3 Change GitHub credential selection to validate explicit-token, sanitized local-session, and credential-helper candidates independently without exposing credentials.
- [ ] 2.4 Add temporary-repository and mocked-GitHub tests for interrupted publish/resume, duplicate publisher prevention, failed checks/auth, manual mode, and valid-local-session fallback.
- [ ] 2.5 Commit publication/auth behavior and tests as an independently reviewable change.

## 3. Guidance and browser-QA diagnostics

- [ ] 3.1 Update generated AGENTS/engineering workflow and doctor output so sealed automatic publications are actionable incomplete delivery, while project-owned harnesses remain untouched.
- [ ] 3.2 Add generic browser executable/cache discovery guidance or helper, with tests proving unsupported managed download alone does not produce a false unavailable result.
- [ ] 3.3 Update template contract/render tests for new configuration, scripts, ignores, and generated guidance.
- [ ] 3.4 Commit guidance/diagnostic/template-render coverage as an independently reviewable change.

## 4. Validate, release, and roll out

- [ ] 4.1 Run `python3 -m compileall -q template/scripts scripts`, `python3 scripts/managed_projects.py validate`, `python3 -m unittest discover -s tests -v`, `python3 template/scripts/openspec_lifecycle.py check`, strict OpenSpec validation, and applicable temporary Git/Copier render-update smoke tests.
- [ ] 4.2 Perform semantic OpenSpec verification, record a truthful PASS receipt and method, archive the change through the lifecycle helper, and commit the archive.
- [ ] 4.3 Publish an immutable SemVer platform release and prepare reviewable exact-version Copier update PRs for managed platform-owned projects; report project-owned-harness compatibility separately.
