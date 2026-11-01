## 1. Declaration and order
- [x] 1.1 `add_intents.py`: `delivery` validation.
- [x] 1.2 `execute_requirement.py`: sequential order through the single-child path; explicit error for an unreadable handoff.

## 2. Rebind
- [x] 2.1 `orchestrate_pre_authoring.py`: attribution of changed sources, rebind with carried approval and receipt, explicit stop.
- [x] 2.2 `execute_requirement.py`: rebind before materializing the next sequential child.

## 3. Docs and tests
- [x] 3.1 Docs: task-intake; platform manifest.
- [x] 3.2 Tests: validation; order and one child at a time; rebind after own merge without re-approval; foreign change outside affected sources rebinds; foreign change on an affected spec stops; changed ADD stops; unreadable handoff fails.

## 4. Verification
- [x] 4.1 Full validation and semantic OpenSpec verification.
