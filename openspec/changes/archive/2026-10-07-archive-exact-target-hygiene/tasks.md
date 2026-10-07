## 1. Implementation
- [x] 1.1 Scope the archive-target context to the select_checks validation subprocess and make check_hygiene exempt only a validated exact target, failing closed otherwise.
## 2. Tests and docs
- [x] 2.1 Add unit tests and an end-to-end regression with the real standard check mapping covering the deadlock, second stale change, invalid target, failed archive and post-archive hygiene.
- [x] 2.2 Document the archive-scoped exemption in openspec-workflow.md and its template counterpart.
## 3. Verification
- [x] 3.1 Run relevant tests, the affected precheck and required platform checks; perform semantic OpenSpec verification and independent review; record truthful verification evidence.
- [x] 3.2 Archive and commit through the lifecycle helper; complete the child retrospective and hand off for publication.
