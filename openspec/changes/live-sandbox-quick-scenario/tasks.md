## 1. Private access
- [x] 1.1 Clone and fetch through the push credential mechanism in `prepare_checkout` and every caller.
- [x] 1.2 Tests: no token in argv, URL or checkout config; missing token error; public behaviour unchanged.

## 2. Sandbox
- [x] 2.1 Fixture project, CI and checks, and the snapshot composition from an exact head.
- [x] 2.2 Idempotent bootstrap of the repository, settings, protection and labels; target guard.
- [x] 2.3 Own operator config and registry in the runner working directory.
- [x] 2.4 Reset and the single-run lock.

## 3. Runner and scenario
- [x] 3.1 Runner command, scenario selection, step limits, failure report, known failures.
- [x] 3.2 Quick task scenario to MERGED on the real sandbox.

## 4. Docs and verification
- [x] 4.1 `docs/engineering/live-scenarios.md`: shape, owner setup, command, limits; manifest.
- [x] 4.2 Full validation, strict `openspec validate`, a recorded real run and semantic OpenSpec verification.
