# Tasks

- [x] 1. Research and document, in design.md, the actual pre-write enforcement points Claude Code and Codex expose today; do not claim hard enforcement where only detection is possible.
- [x] 2. Implement a snapshot/diff module: capture `integration/main`'s git state before and after a delegation, and classify changed paths as pre-existing vs newly introduced.
- [x] 3. Implement the containment check: given `assigned_worktree` and the two snapshots, determine violation vs clean, fail closed on ambiguity or on a snapshot step itself failing.
- [x] 4. Wire cwd-based launch (`cwd=assigned_worktree`) wherever the platform directly controls subprocess/subagent launch, documented as partial mitigation only.
- [x] 5. Record a friction event via `agent_friction.py` on violation, after the safety check, independent of GitHub auth availability.
- [x] 6. Add tests: delegated writer writes only inside its assigned worktree (PASS); delegated writer writes into `integration/main` (BLOCKED, exact violating path reported); `integration/main` already dirty from unrelated pre-existing changes before delegation (not touched, correctly distinguished from a new violation).
- [x] 7. Run platform validation (`compileall`, managed-project validation, unit suite, OpenSpec lifecycle check) and semantic OpenSpec verification; record the real verification receipt before archive.
