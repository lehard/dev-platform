## Why

A formally valid Business Requirement can still lose the accepted intent: exact decisions from a long conversation become "make it convenient", an accessible reference is dropped, agent freedom is granted on already settled questions, a later-cancelled proposal stays active beside a new criterion, or a local request grows into a global policy. Existing gates (`requirement_intake create` routing/labels/read-back, `goal-definition`, `selective-domain-interrogation`, ADD → Intents) check structure or run later and cannot recover content that was never written down. Requirement BR-582 asks for one shared, adaptive authoring standard applied before the Requirement is written or materially refined, on every surface, with no new lifecycle.

## What Changes

- Add the instruction-only capability `requirement-authoring` (`dev-platform/capabilities/requirement-authoring.{md,toml}`, evals, template mirror). Its Markdown is the single canonical source of the authoring standard and of its small representative examples.
- The standard defines: use of the whole available context; classification of accepted-current, superseding, example/reference, rejected/hypothetical and genuinely open material; affirmative current-decision wording without negotiation chronicle (a still-active boundary is kept as the boundary itself); lossless transfer of material detail; three binding levels (fixed, meaning-fixed with variable execution, delegated) in prose; preservation of accessible references with honest handling of unavailable ones and privacy; placement in the existing Outcome/Context/Acceptance evidence/Exclusions sections; selective questions (1–3 grouped, only for unresolved material product choices); and a light coverage/consistency/scope/autonomy/portability/truthfulness self-check before writing and after material edits.
- Wire the standard in without a second source: `task-intake.md`, `chatgpt-project-protocol.md`, `agent-instructions.md` and the `AGENTS.md` concern map point to the canonical file, so a ChatGPT Project (connected GitHub), Claude, Codex and managed downstream projects read the same content; enabling the capability additionally materializes it as a provider skill.
- Add tests that pin the standard's required rules, the example cases, the cross-surface identity, the unchanged Requirement format/children marker, and the absence of any new gate, status, ledger or interview.

## Capabilities

### Modified Capabilities

- `managed-task-intake`: a new requirement for how Business Requirement content is prepared before fixation and refinement.
- `engineering-capabilities`: a new requirement for the `requirement-authoring` capability as the single canonical authoring source reachable without per-project enablement.

## Impact

`dev-platform/capabilities/requirement-authoring.*`, `template/dev-platform/capabilities/requirement-authoring.*`, `dev-platform/evals/requirement-authoring-pilot.json` (and template mirror), `docs/engineering/{task-intake,chatgpt-project-protocol,agent-instructions,engineering-capabilities}.md` and their `template/` counterparts, `AGENTS.md` and `template/AGENTS.md.jinja`, and tests. No change to `requirement_intake.py` behavior, the Issue format, labels, children markers, BR revision binding, pre-authoring or ADD/OpenSpec rules.

## Non-goals

Rewriting existing Requirements; ADD standardized approval (BR-581); final agent report (BR-338); OpenSpec authoring rules; any LLM validator or scorecard, approval gate, mandatory interview, PRD backlog, unresolved-question ledger, new lifecycle status or storage; per-project configuration.
