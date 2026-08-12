# Verification: optimize-agent-context-map

OpenSpec-Verify: PASS
Verification-Method: documented equivalent OpenSpec review (completeness / correctness / coherence) — the `/opsx:verify` workflow is not exposed by this agent surface — plus focused contract tests, negative-guard tests, real Copier renders of all supported profiles, and the platform-selected automated checks.
Automated-Checks-Evidence: automated-checks.json

## Scope of what was actually checked

Source issue `lehard/development-backlog#28`, change `optimize-agent-context-map`, spec `project-factory`.

## Input reconciliation

The managed package published on issue #28 was updated by the user after import (comment edited at 2026-08-12T19:30Z, replacing the body imported at 17:39Z). The local canonical artifacts were reconciled with that update rather than re-imported:

- the modified requirement was renamed to "…one **compact** cross-agent task protocol" through a `## RENAMED Requirements` block, so the current spec is renamed rather than silently forked;
- the requirement gained the risk-proportional verification rule (focused structural/navigation/render/semantic evidence; no unrelated full software regression suite required solely because instruction/documentation/template text changed; intentional directive-meaning changes reconcile OpenSpec first and carry targeted behavioral evidence);
- two scenarios were added — "Desired behavior change is discovered" and "Instruction-only compaction is verified";
- `proposal.md`, `design.md` (new section 6) and `tasks.md` (4.2, 5.1) were updated to match.

The richer scenario set from the imported package was retained. `.managed-task.json` still records the revision actually imported at 17:39Z; it is an import receipt and was not rewritten to a revision that was never imported.

One repair was needed before intake could run at all: the originally published package's MODIFIED block renamed a scenario in place, which OpenSpec rejects as a silent scenario drop. The package comment was repaired (scenario name restored, `CLAUDE.md` adapter assertion restored) with the user's explicit approval before `start_managed_task.py` succeeded.

## Completeness

All five task groups are covered.

- Preflight and inventory (1.1–1.3): active change `adopt-gh-aw-process-automation` reconciled (it owns `platform-lifecycle`, `agentic-maintenance` and, since `517885f`, `model-routing`; none of its deltas edit either root guidance file, so there was no wording conflict). Directive inventory recorded in `migration-trace.md`. Budget fixed at 120 lines against a measured 85/89.
- Refactor (2.1–2.4): central `AGENTS.md` 131 → 85 lines; `template/AGENTS.md.jinja` 206 → 89 lines. Detail relocated to `docs/engineering/{agent-workflow,openspec-workflow,model-routing}.md` (new, central) and to the existing `template/docs/engineering/{agent-workflow,model-routing}.md`. Adapters unchanged and still thin.
- Guardrails (3.1–3.3): `tests/test_root_guidance_contract.py`.
- Semantic regression (4.1–4.3): `migration-trace.md`; relevant suites re-run; friction/completion semantics preserved.
- Delivery (5.1–5.3): checks below, this receipt, then archive and publication.

Requirement coverage: the MODIFIED requirement's four contract sentences and five scenarios, and the ADDED budget requirement's three scenarios, all map to shipped behavior.

## Correctness

Positive evidence:

- `python3 -m unittest tests.test_root_guidance_contract tests.test_template_contract tests.test_project_harness_doc_ownership` — 33 tests, OK.
- `python3 scripts/select_checks.py --execute` after rebasing onto `517885f` — `local-affected`, reason `high-impact-path`, selection `ready`, all three selected commands successful: `compileall` (0.52s), `managed_projects.py validate` (0.10s), `unittest discover -s tests -v` (331.20s). The full suite is retained as evidence here because the current selector still chooses it for this path; the change does not claim it as a requirement.
- Direct Jinja render of `template/AGENTS.md.jinja` for each profile: 79 / 79 / 83 lines (light / standard / multi-agent).
- Real Copier render of `light`, `standard` and `multi-agent` from a VCS-free copy of the working tree: each rendered `AGENTS.md` is within budget, keeps all six anchors, and every navigation link resolves in the generated project. Rendering from the Git source was deliberately rejected because Copier would have resolved a committed ref and verified `HEAD` instead of the working tree.
- `openspec validate optimize-agent-context-map --strict` — valid; `openspec show --deltas-only` parses exactly three operations (ADDED, MODIFIED, RENAMED).
- `python3 -m compileall`, `python3 scripts/managed_projects.py validate` (3 managed / 7 candidate / 3 excluded), `python3 template/scripts/openspec_lifecycle.py check` — all OK.

Negative evidence — the guard was proven to fail, not assumed to:

- appending 60 lines to `AGENTS.md` fails the budget test with `AGENTS.md is 146 lines; the always-on budget is 120…`;
- renaming `## Ownership` to `## Stewardship` fails the anchor test with an actionable message naming the missing category.

Both files were restored from the index afterwards.

## Coherence

- No directive meaning was intentionally changed; this is relocation plus compaction. The one presentation decision worth naming: pre-change central guidance carried two overlapping start sequences — `start_managed_task.py` in the intake section and `managed_task.py` + `dogfood_task.py start` in the dogfood section. The root map now surfaces `start_managed_task.py`, which the intake section already made canonical (and which this task itself used); the full dogfood sequence is preserved verbatim in `docs/engineering/agent-workflow.md`. No rule was removed.
- The renamed requirement has no other live references: only `openspec/specs/project-factory/spec.md` (which the rename updates) and one archived change, which is historical and untouched.
- Copier ownership boundaries are unchanged. No new downstream file was introduced, so no project-owned path became platform-owned; `AGENTS.md`, `CLAUDE.md` and (for `harness_mode=project`) the two engineering docs remain `_skip_if_exists`.
- Adding `docs/engineering/openspec-workflow.md` to the central repository does not affect `adopt_project.py`'s `PROJECT_GUIDANCE_MARKERS`, which inspect an adoption *target*, never the platform source.
- Observed coherence gap, deliberately not fixed here: `select_checks.py` still classifies `AGENTS.md` as `high-impact-path` and selects the full command set for an instruction-only change. That selector is exactly the scope of open backlog issue `lehard/development-backlog#27` (`reduce-platform-test-cycle-time`); changing it here would have exceeded this change's scope. The full set was run and passed regardless.

## Residual risk

The rename is applied through OpenSpec's `RENAMED` operation, which validates and parses correctly but is exercised for the first time in this repository. If archive rejects it, the fallback is to keep the existing requirement name — the rename is presentational and carries no contract semantics.
