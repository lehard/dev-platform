# Verification: decision registry

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review of Requirement #249, the active proposal/design/delta scenarios, registry fields, TeamAI pilot evidence and bounded agent discovery; structural OpenSpec validation and the executed platform checks below.
Automated-Checks-Evidence: automated-checks.json

The registry index defines stable identity, scope, date/revision, current and alternative decisions, evidence, revisit triggers and explicit supersession. The TeamAI record answers why wholesale adoption is rejected and what remains under watch, with a link to the existing v0.25.0 pilot rather than a copied transcript. AGENTS.md and the context map lead supported agents to the relevant record; OpenSpec remains the executable contract. No backlog, task status or ADD ledger was introduced.

Executed before archive:

- `openspec validate establish-decision-registry --strict` — passed.
- `python3 scripts/select_checks.py --base origin/main --declare-behavior-change codex --execute` — compileall, Ruff and every configured test group passed. The selector chose the full suite because no targeted behavioral smoke is configured for the changed agent instruction surface.
- `python3 scripts/check_docs_links.py` — no broken documentation links or anchors.
- `python3 scripts/managed_projects.py validate` — passed.
- `python3 template/scripts/openspec_lifecycle.py check` — passed.
- `git diff --check` — passed.

The archive helper will generate `automated-checks.json` for its own exact check run.
