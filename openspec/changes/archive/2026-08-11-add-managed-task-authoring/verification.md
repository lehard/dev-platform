# Verification: add-managed-task-authoring

OpenSpec-Verify: PASS
Verification-Method: equivalent documented semantic review plus automated platform checks

## Semantic review

- **Completeness:** the delta requirements map to the `create --bundle` helper,
  rendered `[development_backlog]` configuration, a narrow existing-project
  migration, canonical generated/root agent guidance, and regression/upgrade
  coverage. The helper validates the contained bundle and a temporary real
  OpenSpec change before remote mutation, checks configured labels and bounded
  same-project/target candidates, creates the human issue, and posts one v1
  transport package.
- **Correctness:** the serializer round-trips through the existing v1 importer;
  its source issue is filled only after issue creation. A receipt in the issue
  body makes a post-create/pre-package interruption resumable without a second
  issue. Existing package parsing rejects a divergent or unsupported package.
  Temporary change roots are removed in `finally`, and no implementation,
  lifecycle, Project-status, dispatcher or publication entrypoint is called.
- **Coherence:** this change was rebased onto `add-central-dogfood-lifecycle`
  (PR #118). Root guidance keeps that change's isolated managed-task start path,
  and its explicit source configuration receives the shared Backlog table; no
  competing root adapter/configuration was introduced. Claude still references
  canonical `AGENTS.md` rather than carrying a forked protocol.

## Automated evidence

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/managed_projects.py validate`
- `python3 -m unittest discover -s tests -q`
- `python3 scripts/openspec_lifecycle.py check`
- `openspec validate add-managed-task-authoring --strict --no-interactive`
- Focused authoring/configuration/template tests passed (42 tests before the
  #118 rebase; the complete repository suite passed after the rebase).
- Copier upgrade smoke exercises `light`, `standard`, and `multi-agent`;
  generated projects retain project-owned sentinels and receive the authoring
  helper/configuration migration.
