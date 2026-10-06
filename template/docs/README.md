# Documentation map

This map explains where to look. The root `AGENTS.md` remains the process map and always-on invariants; this file points from it to the right concern document. It is platform-owned and updated by Copier.

## Which source answers which question

| Question | Source |
| --- | --- |
| How may work be performed here (process, safety, always-on rules)? | `AGENTS.md` and any module-level `AGENTS.md` |
| What is the accepted current behavior? | `openspec/specs/` |
| What behavior is being changed right now? | `openspec/changes/<active>/` (proposal, delta specs, design, tasks) |
| What does the system actually do today? | Code, plus current specs and any active delta |
| What are the durable process, workflow and operating details? | `docs/` (this map and the documents below) |

Target behavior during an active change is `current specs + active delta`, subject to the process rules in `AGENTS.md`.

## Which document for which task

| Task or concern | Document |
| --- | --- |
| Maintaining agent-facing instructions and pointers | [engineering/agent-instructions.md](engineering/agent-instructions.md) |
| Task intake and intent transitions | [engineering/task-intake.md](engineering/task-intake.md) |
| ChatGPT Project authoring through connected GitHub | [engineering/chatgpt-project-protocol.md](engineering/chatgpt-project-protocol.md) |
| Start/publish lifecycle, worktrees, validation, friction, completion | [engineering/agent-workflow.md](engineering/agent-workflow.md) |
| OpenSpec model, semantic verification, receipts, archive | [engineering/openspec-workflow.md](engineering/openspec-workflow.md) |
| Executor selection, escalation, delegated write containment | [engineering/model-routing.md](engineering/model-routing.md) |
| Optional engineering capabilities | [engineering/engineering-capabilities.md](engineering/engineering-capabilities.md) |
| Browser verification adapter | [engineering/browser-verification.md](engineering/browser-verification.md) |
| Project-specific engineering, stack and domain rules | `engineering/project-rules.md` (project-owned) |
| Product/domain semantics, architecture invariants, examples | `context/README.md` (project-owned, loaded only when that concern is reached) |

## Ownership

Documents under `docs/engineering/` (except `project-rules.md`) and this map are platform-owned and change through reviewed Copier updates. `engineering/project-rules.md` and `context/` are project-owned; keep domain and stack rules there, not in platform documents.

## Upstream OpenSpec documentation

Upstream OpenSpec documentation is supplementary reference only. The standard lifecycle is fully described in [engineering/openspec-workflow.md](engineering/openspec-workflow.md) and uses Dev Platform entrypoints.
