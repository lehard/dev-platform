## 1. Protected surface

- [x] 1.1 Add `template/dev-platform/protected-surface.toml` with categories, protected globs and the explicit hotfixable list; header states it is platform-owned and not edited downstream.
- [x] 1.2 Add a platform test that enumerates plain-copied platform-owned files and fails on any file that is neither protected nor listed hotfixable, and on any Requirement category without an existing protected path.

## 2. Contract text

- [x] 2.1 Add `template/docs/engineering/change-classes.md` (three classes, protected surface, agent never reclassifies, class (c) path) and a concern-table pointer in `template/AGENTS.md.jinja`; update `docs/ownership.md` and root `AGENTS.md` pointers without duplicating policy.

## 3. Delivery

- [x] 3.1 Extend template contract / render and Copier update smoke tests: new files render, an update delivers them, project-owned files are untouched.

## 4. Verification and delivery

- [ ] 4.1 Required platform checks, truthful semantic verification, archive, retrospectives, publication.
