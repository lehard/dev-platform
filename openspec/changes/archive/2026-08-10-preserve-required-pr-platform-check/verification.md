# Verification: preserve required PR platform check

OpenSpec-Verify: PASS
Verification-Method: equivalent completeness/correctness/coherence review using repository artifacts plus GitHub Platform CI #203

## Completeness

- All implementation tasks are complete.
- The delta covers the observed v1.4.5 failure mode: direct-mode generated CI could no longer produce a required `platform-ci` PR status.
- Template, generated guidance and focused contract tests were updated together.

## Correctness

- `publish_mode=pr` still renders pull-request validation and no main-push platform trigger.
- `publish_mode=direct` now renders pull-request compatibility plus main-push validation and manual dispatch.
- Existing PR-vs-main job behavior is preserved: PR events use selected-check semantics; non-PR direct main runs use full platform-managed checks when the platform owns the harness.
- Concurrency cancellation remains enabled for validation workflows; release/rollout side-effect workflows are unchanged.
- The unrelated stale managed-registry expectation discovered by CI was reconciled with the already-managed `lehard/Jara_Fin` entry.

## Coherence

- The fix stays in Dev Platform-owned workflow/template/docs/tests surfaces and does not modify project-owned product CI.
- It preserves the v1.4.5 cost goal for normal direct publication: one automatic validation on published `main`. An extra platform run exists only when a direct repository explicitly uses a reviewed PR, which is necessary to satisfy stable required-status protection.
- No branch-protection weakening, force-push, auto-merge or new secret/config dependency is introduced.

## Acceptance evidence

Platform CI #203 passed on head `b5f78815064a319e54ba2e508740ed4b9e17e24a`, including:

- shared script compilation;
- managed-project registry validation;
- full unit tests;
- OpenSpec lifecycle hygiene;
- strict OpenSpec validation;
- tested Copier installation;
- all factory profile renders;
- Copier upgrade smokes;
- mature project harness adoption smoke;
- project-harness smart-update fallback smoke.

No CRITICAL or WARNING findings remain. Ready for archive and patch release.
