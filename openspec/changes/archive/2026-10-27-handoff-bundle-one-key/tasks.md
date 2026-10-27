## 1. Resolver

- [x] 1.1 Add one handoff-to-bundle resolver (`bundles/<id>` or a single manifest declaring `"handoff": "<id>"`) and use it for materialization and refreshed-handoff reuse; stop swallowing bundle errors.
- [x] 1.2 Name unmapped handoffs and the child's change when a non-terminal linked child maps to no handoff; document the bundle key.

## 2. Verification

- [x] 2.1 Tests: intent and change with different names advance through a declaring bundle; an undeclared change-named bundle fails naming both names; ambiguous declarations fail. Selected checks and semantic verification.
