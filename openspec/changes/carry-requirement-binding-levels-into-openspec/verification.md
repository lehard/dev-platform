OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (completeness, correctness, coherence) of the implementation diff against the carry-requirement-binding-levels-into-openspec delta, proposal, design and tasks; repository-owned selected checks on the candidate head; Copier upgrade smoke
Automated-Checks-Evidence: automated-checks.json

Implementation. A delegated native Claude executor (routine route, haiku) wrote every content change. The supervisor reviewed the diff and returned one accuracy fix to the same executor: in the worked example the switch is the report's breakdown switch, not a balance switch. Containment postcheck: clean.

An earlier supervisor-written draft was blocked by the early routing gate, because the plan required a delegated child. The draft was discarded with a reset of the unpublished task branch. The OpenSpec package was restored unchanged, the delegation was opened, and the executor rewrote the content from the specification. No supervisor-written content remains in the candidate.

Completeness. Each requirement clause and scenario of the `openspec-authoring` delta, with where it is implemented:

- Carry each point at its level (fixed, meaning fixed, delegated); never bind more tightly; examples, illustrative values and mockups bind only fixed points; financial, data, technical, security and accessibility constraints never relax. Implemented in `### Carry Requirement binding levels into OpenSpec` in `docs/engineering/openspec-workflow.md` and, identically, in `template/docs/engineering/openspec-workflow.md`. The OpenSpec CLI `specs` rule in `openspec/config.yaml` and `template/openspec/config.yaml.jinja` carries the same constraint.
- The ADD pipeline keeps the levels and does not harden them in ADD elements, intents or handoff envelopes. Implemented as a paragraph in `dev-platform/capabilities/add-intents.md` and its byte-identical template mirror.
- The levels hold on the whole path. Implemented as a pointer paragraph in section 4 of `dev-platform/capabilities/requirement-authoring.md` and its mirror.
- Worked example. It covers a cash-flow report:
  - fixed points written exactly with scenarios: switch order, no "Period totals" card, no horizontal scrolling at 375 px;
  - a fixed-meaning warning about balances, written as one requirement on meaning and placement;
  - delegated presentation and illustrative amounts, which appear in no requirement;
  - two wrong examples, one that hardens a delegated presentation and one that weakens a fixed meaning.
- Scenarios "Meaning fixed, presentation delegated", "Fixed decision stays exact" and "Example is not a requirement" are each demonstrated by the worked example.
- New authoring only; accepted specs are not rewritten. Stated in the guidance. No accepted spec was edited.

Correctness and coherence:

- No new section, stage, gate, validator, classifier or schema field was added.
- Capability provenance and eval-fixture `content_sha256` values were updated to the new canonical files, and `capability_manager.py audit` reports no issues.
- `template/dev-platform/platform-manifest.json` was regenerated with `scripts/generate_platform_manifest.py --write` only.
- Deviation from the Requirement wording, made on purpose: the Requirement asks for the example to be shown on a named private product and its private Backlog Issue. This repository is public, so the example is given by its content, without the project name or the Issue reference. The fixed meaning of the example is kept and only the identifying reference is left out.

Checks actually run on HEAD `ad856827` (contains `origin/main` 5978f471):

- Targeted tests by the executor: `tests/test_template_contract.py`, `tests/test_requirement_authoring.py`, `tests/test_add_intents.py`, `tests/test_project_context.py` — 157 passed.
- `python3 scripts/check_private_backlog_refs.py --root .` — passed.
- `python3 tests/upgrade_smoke.py --profile standard --publish-mode pr` — passed: Copier update from v1.9.6 to the candidate. Project-owned sentinels, including a project-edited `openspec/config.yaml`, were preserved.
- `python3 scripts/select_checks.py --base origin/main --execute --evidence …/automated-checks.json`, after the task freshness gate and the scope gate:
  - `compileall` — passed;
  - `ruff` — passed;
  - `run_test_groups.py --all` — passed in 1244 s.
- Scope gate: the only overlap is the generated `template/dev-platform/platform-manifest.json` with the BR-694 task. It was acknowledged through `agent_board.py acknowledge` and will be regenerated after any reconcile.

Not covered: Explorer editorial drift warnings for the touched sections are warning-only and were not marked reviewed.
