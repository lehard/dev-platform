## Context

- `template/` is rendered into downstream projects by Copier; plain files (no `.jinja` suffix) arrive byte-identical, so a path set over them is deterministic across projects. `copier.yml` `_skip_if_exists` lists the project-owned files that survive updates; everything else under `template/` is platform-owned.
- `docs/ownership.md` already splits platform-owned, project-owned and operator-owned surfaces and states the override rule. The protected rules named by the Requirement are implemented by existing scripts (for example `independent_review*.py`, `pr_review_gate.py`, `publication_queue.py`, `project_publish.py`, `merge_to_main.py`, `shared_workspace.py`, `worktree_cleanup.py`, `delegation_containment.py`, `delegated_write_guard.py`, `model_routing.py`, `private_lineage.py`, `managed_work_identity.py`, `openspec_lifecycle.py`, `rollout_identity.py`, `git_hooks/*`, release workflows).

## Decisions

1. **Classes are data, not prose.** `dev-platform/protected-surface.toml` (platform-owned, overwritten by Copier) has a `[categories]` table (one entry per protected rule category with a one-line rationale) and a `[[protected]]` list of `path` globs, each tagged with its category. Prose in `change-classes.md` explains it but the file is authoritative for tooling.
2. **Default deny, fail closed.** A platform test enumerates every plain-copied platform-owned file in `template/` and requires it to be matched by a protected glob or listed in an explicit `hotfixable` list in the same file. A new unclassified file fails the platform's own validation; there is no default class. The protected globs are deliberately broad (whole script groups, not single functions), because a partially protected script cannot be patched safely.
3. **No agent reclassification.** The contract text and the file header state that neither the protected list nor the hotfixable list is edited downstream; both arrive only through a release. The later hotfix gate (separate change) reads this file and treats any downstream edit of it as a divergence of a protected path.
4. **No new authorization channel.** Class (b) uses the ordinary project PR, CI and independent review. Class (c) has no local change path; where a gate already defines an owner-recorded recovery (for example routing `approve-supervisor-diff`), that remains the only recovery and is cataloged by the recoverability change.
5. **Delivery reuses Copier.** The new files are plain template files; new-project rendering and existing-project update are covered by extending the existing template contract and upgrade smoke tests.

## Risks and mitigations

- *Too broad a protected set makes hotfix useless.* Mitigation: the set is data in one file; narrowing it is a normal reviewed platform change with a test showing the guarantee is preserved.
- *Too narrow a set lets a hotfix weaken a guarantee.* Mitigation: default deny plus a test that each Requirement category maps to at least one protected glob that exists.
- *Existing projects with a locally edited protected file.* Out of scope here; handled by the divergence gate of the hotfix change, which reports rather than rewrites.
