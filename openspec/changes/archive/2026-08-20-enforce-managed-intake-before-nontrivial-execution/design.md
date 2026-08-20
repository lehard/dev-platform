# Design: Unified managed intake for execution from any entrypoint

## Decisions

### 1. Intent, not UI, chooses the lifecycle

The platform treats ChatGPT, Codex and Claude Code as entrypoints into the same repository contract. The semantic intents are:

- **Discuss** — inspect/design/compare; no durable task state by itself.
- **Fix** — author or update the accepted managed task, then stop.
- **Quick execute** — immediately execute a small bounded change without managed ceremony.
- **Fresh non-trivial execute** — author/find the managed task and immediately continue through managed start before implementation.
- **Execute existing managed task** — start/resume the supplied Development Backlog task through the current managed path.

The user phrase is evidence of intent, not a magic keyword list. “Сделай”, “реализуй”, “почини” or equivalent execution intent authorizes author+start for non-trivial work; it does not require a second fixation prompt.

### 2. Compose existing primitives instead of creating another lifecycle

A single standard orchestration entrypoint owns the fresh non-trivial execution transition. It composes existing operations:

1. resolve repository/config/current target state;
2. perform bounded duplicate/context checks required by managed authoring;
3. reuse an unambiguous existing managed task or author one with `managed_task.py create` semantics;
4. start/resume that exact task through `start_managed_task.py` semantics;
5. return the canonical task checkout/materialized OpenSpec to the normal implementation lifecycle.

The implementation may expose this as a new helper/command or a supported mode on an existing entrypoint, but it must remain a thin idempotent composition rather than a second state machine.

### 3. Fixation-only and execution remain separate irreversible intents

Authoring-only remains the path for “зафиксируй”. It never implicitly starts implementation or changes the task to an execution state. The combined path is used only when the user's current request already asks to execute the change.

This preserves the current safety boundary while removing the unnecessary human handoff between authoring and start for a direct execution request.

### 4. OpenSpec is a practical escalation boundary

Quick-vs-managed remains risk/scope based rather than diff-size based. The existing material-change signals remain authoritative. In addition, if an agent decides the work needs a full active OpenSpec change as its implementation contract, the normal path must become managed before implementation continues. This makes “OpenSpec without managed provenance” exceptional/recovery state rather than a normal workflow branch.

### 5. Enforce the invariant mechanically

Instruction text alone is insufficient. Platform-owned start/completion/publication checks should detect an active non-trivial OpenSpec change lacking matching managed provenance on ordinary supported execution paths and fail closed with an actionable transition/recovery message.

The guard must not misclassify genuine quick work that never created an OpenSpec change, and it must retain explicit bounded recovery for legacy/manual states rather than inventing provenance or deleting work.

### 6. Shared intake semantics get a platform-owned canonical destination

Mutable cross-project process semantics should not depend on a full project-owned root `AGENTS.md` being overwritten on every rollout. The platform should provide a compact platform-owned task-intake contract/document that is updated through normal releases. Root `AGENTS.md` remains the always-on repository map and keeps project/domain rules, but contains only a stable reference/invariant directing agents to the shared intake contract when a task reaches authoring/execution concerns.

This follows the existing bounded-context design: always-on rules stay short; detailed mutable workflow lives in canonical thematic docs.

### 7. Existing managed repositories need a one-time ownership-safe migration

A normal Copier update cannot be assumed to rewrite project-owned root guidance. The change therefore includes an explicit migration/adoption mechanism for repositories already marked `managed`:

- detect whether the required stable intake reference/invariant is present;
- add or reconcile only the bounded shared reference needed for the new contract;
- preserve project/domain-specific instructions and module-level rules;
- validate that the platform-owned canonical intake document/scripts are on the same platform version;
- make subsequent intake semantic updates arrive through normal platform-owned rollout surfaces.

`Jara_Fin` is the representative mature-project acceptance case because it already has current managed-task capability/config while retaining old root guidance.

### 8. Candidate repository adoption stays separate

`Jara_kassy_detect` and other `candidate` repositories do not enter managed rollout merely because this contract changes. Their first-time adoption keeps the existing explicit **Adopt Project** security/administrative boundary. Once adopted, they receive the same shared intake contract through normal releases.

## Risks & mitigations

- **Backlog noise from over-classifying small fixes.** Preserve the quick path and existing material-change criteria; do not use file/diff count alone.
- **“Сделай” accidentally starts work where the user only wanted recording.** Author+start is tied to explicit execution intent; fixation phrases remain author-only.
- **Duplicate task created during retry.** Combined entrypoint reuses current duplicate/authoring identity checks and is idempotent across partial author/start states.
- **Mechanical provenance guard blocks legacy work with no recovery.** Provide a bounded explicit recovery classification/path; never fabricate provenance or reset work.
- **Migration overwrites project-specific AGENTS rules.** Treat migration as a targeted reference/invariant insertion with preservation checks, not a full template replacement.
- **Shared contract drifts between central/template/downstream.** Add render/update/migration tests and behavioral acceptance cases.

## Rollout

Implement and verify centrally, publish as a normal immutable Dev Platform release, then use reviewed managed rollout for existing managed repositories. The migration acceptance must prove that a mature project with project-owned guidance receives the shared intake reference without losing local rules. First-time adoption of candidates is a separate explicit operation.
