# Verification: ADD -> Intents -> OpenSpec authoring pipeline

## Semantic review

**Completeness.** All 27 tasks across the six task groups are complete. The change adds:
a compact versioned ADD JSON schema and an intent-set JSON schema; a `scripts/add_intents.py`
CLI (`new-add`, `validate-add`, `decompose`, `validate-intents`) with a matching
`template/scripts/add_intents.py` implementation and a dogfood shim, following the existing
`browser_verification.py`/`source_adapter.py` pattern; a new opt-in `add-intents` capability
descriptor/instruction/eval fixture under the existing #87 optional-capability lifecycle
(`kind = "tool-backed"`, mirrored into `template/dev-platform/capabilities/` and
`template/dev-platform/evals/`); a composition note added to `selective-domain-interrogation.md`
(with its `content_sha256`/eval fixture hash updated to match, also mirrored); and documentation
in `docs/engineering/engineering-capabilities.md` and `docs/engineering/agent-workflow.md`. Both
delta specs (`specs/agent-workflow/spec.md`, `specs/openspec-authoring/spec.md`) are satisfied:
every requirement/scenario maps either to a deterministic gate in `add_intents.py` (schema,
provenance, freshness, approval-blocks-on-open-choice/contradiction, coverage, dependency-graph
acyclicity, overlap-without-reason, ready-with-blocker) or to a documented behavioral rule in
`dev-platform/capabilities/add-intents.md` for the properties design.md §5 explicitly leaves to
agent/human judgment (ADD correctness, decomposition quality, OpenSpec-conflict routing) rather
than deterministic tooling overclaiming semantic completeness.

**Correctness.** `validate-add` structurally proves schema version, a bound requirement digest,
an exact 40-hex `prepared_against` revision plus freshness against the current worktree HEAD,
well-formed evidence/element/unresolved-choice/contradiction entries, and refuses `approved: true`
while any `unresolved_choices` entry is `open` or any `contradictions` entry is `resolved: false`
-- an evidence-resolved choice never blocks approval. `decompose` refuses an ADD that is not
`approved` or that fails structural validation. `validate-intents` proves a matching `add_id`,
that every ADD element with `status` `new`/`changed` is covered by an intent or has an explicit
`non_implementation` disposition (a `preserved` element needs neither, encoding "reuse the
existing decision"), that intent/dependency references exist and the dependency graph has no
cycle, that two intents sharing an ADD element each record an explicit `overlap_reason`, and that
no intent is `ready` while it still records a `blocker` (encoding "return the gap to ADD
refinement" rather than silently guessing). 30 unit tests in `tests/test_add_intents.py` exercise
every one of these paths, including explicit positive and negative cases for existing-decision
reuse, a missing design decision returned to refinement, stale-vs-fresh `prepared_against`, and a
full CLI end-to-end flow. The `dev-platform/evals/add-intents-pilot.json` fixture adds 10
positive/10 hard-negative applicability prompts (20/20 pass under the deterministic-fixture
adapter) plus 5 objective quality comparisons covering the proposal's success-evidence list.

**Coherence.** The capability follows the existing `browser-verification` tool-backed pattern
(descriptor, hash-pinned instruction, `tool_adapter`, eval evidence) rather than inventing a new
capability shape; `add_intents.py` only reads/writes the local JSON files its caller names and
local Git history, never a provider API, `openspec/changes/`, Backlog, or Project state -- no
second backlog/registry/status ledger, matching the explicit non-goals. The capability was
designed with a third-party "Intents" skill bundle and its author's transcript inspected
out-of-band as reference-only material (staging: preflight/context -> ADR-equivalent with a
mandatory human-approval gate -> atomic decomposition -> downstream materialization -> summary);
no files, scripts, or corporate/provider assumptions (Jira/Confluence/GigaCode/Sber/Kafka/
functional-area/provider-session) from that bundle are vendored, matching the proposal's reference
boundary. `dev-platform/capabilities/add-intents.{toml,md}` and
`dev-platform/evals/add-intents-pilot.json` are byte-identical to their `template/` mirrors, as is
the updated `selective-domain-interrogation.{toml,md}`/eval fixture and
`docs/engineering/engineering-capabilities.md`, each proven by new/updated assertions in
`tests/test_template_contract.py`. `dev-platform/checks.toml` registers `test_add_intents` in the
`fast-b` group; `run_test_groups.py --all` proves the declared groups collect exactly what
`unittest discover` collects (932/932, no gaps, no duplicates). `python3 scripts/check_docs_links.py`
reports no broken links/anchors for the new cross-references. The capability stays disabled by
default (`dev-platform/capabilities.toml` `enabled = []` unchanged), consistent with every other
optional capability in this repository.

**Known pre-existing limitation (not introduced by this change).** `python3 scripts/managed_projects.py
validate` is blocked in this local environment by a missing `rollout.registry_path` in the
machine-local `~/.config/dev-platform/operator.toml`; the identical command fails the same way on
a clean `main` checkout in this environment, so it is pre-existing local-environment configuration,
not a regression. It is also not part of `dev-platform/checks.toml`'s `full_commands` automated
evidence set (`compileall` + `run_test_groups.py --all` only), which both pass cleanly.

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review against proposal (outcome + success evidence), both delta specs, design, tasks, the new capability descriptor/instruction/eval fixture, `tests/test_add_intents.py`, `tests/test_template_contract.py`, `tests/test_capability_manager.py`, `tests/test_docs_semantic_checks.py`, `scripts/check_docs_links.py`, `scripts/capability_manager.py validate`/`audit`/`evaluate`, and the full platform test suite via `scripts/select_checks.py --mode protected-full --execute`.
Automated-Checks-Evidence: automated-checks.json
