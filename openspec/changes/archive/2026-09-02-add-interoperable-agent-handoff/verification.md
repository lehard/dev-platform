# Verification: interoperable agent handoff

## Semantic review

Completeness: all 14 OpenSpec tasks are complete. The capability is a canonical descriptor
(`dev-platform/capabilities/interoperable-agent-handoff.toml`) plus a hash-pinned instruction file
(`interoperable-agent-handoff.md`) and a deterministic eval fixture
(`dev-platform/evals/interoperable-agent-handoff-pilot.json`). It reuses the existing #87 optional
engineering capability lifecycle for identity, provenance, opt-in (`dev-platform/capabilities.toml`
stays `enabled = []`), provider materialization, update and removal; it adds no registry, config
schema, provider-copy path, orchestrator, or second task state machine.

Correctness: the instruction defines one compact provider-neutral navigation envelope with bounded
fields — repository, exact revision, workspace, managed task/OpenSpec, provider routing record,
canonical evidence, verified facts (each with evidence), unresolved assumptions, blockers, next
intent — and keeps facts separate from assumptions, forbidding promotion of an unsupported claim to
a fact. The receiver validates repository / exact revision / managed-task identity first and treats
a mismatch (moved `HEAD`, rebase, superseded task) as stale, re-establishing context from canonical
references and surfacing missing references. The authority boundary is explicit: no branch,
worktree, commit, comment, GitHub, Development Backlog, Project, or OpenSpec mutation and no
execution grant. The boundary with the existing provider routing handoff
(`.claude/model-routing/<change>.json`) is stated in both the instruction and `design.md`: routing
owns executor selection and delegated write containment; this envelope covers only the uncovered
cross-session / cross-provider / agent-to-human navigation gap and references the routing record
rather than restating it. Secrets, raw prompts, chain-of-thought, and large diff/spec copies are
excluded. The deterministic fixture covers ten positives (Claude → Codex, Codex → Claude, agent →
human, fresh-session and cross-provider continuation, fact/assumption separation, navigation-envelope
request, receiver freshness validation, end-of-session managed task, stale-handoff detection) and ten
hard negatives (ordinary same-context compact, existing task state is enough, routine quick tasks,
executor routing) — 20/20 pass, distribution 30 triggered / 30 not-triggered — and its four
objective comparisons verify fact/assumption separation, revision + task-identity validation, the
no-authority / no-routing-duplication boundary, and the same-context-compaction exemption.

Coherence: the canonical descriptor / instruction / fixture, the Copier template copies
(`template/dev-platform/capabilities/`, `template/dev-platform/evals/`), the
`docs/engineering/engineering-capabilities.md` guidance and its template mirror,
`tests/test_capability_manager.py` (new `test_interoperable_agent_handoff_is_navigation_only_and_optional`),
and `tests/test_template_contract.py` (three new required template paths) all follow the existing
optional-capability conventions. `openspec validate --strict` passes; the delta adds three
`agent-workflow` requirements, each scenario-backed. The capability stays opt-out by default and
materializes no provider surface until a project enables it.

OpenSpec-Verify: PASS
Verification-Method: Manual semantic review against proposal (outcome + success criteria), delta spec, design, tasks, descriptor/instruction, and the deterministic eval fixture, plus `openspec validate --strict`, focused capability/template/docs checks, the fixture eval (20/20), and the full platform test suite (`scripts/run_test_groups.py --all`).
Automated-Checks-Evidence: automated-checks.json
