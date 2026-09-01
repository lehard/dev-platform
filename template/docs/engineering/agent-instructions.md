# Agent-facing instruction architecture

This document owns the reusable quality contract for instructions read by
agents in a Dev Platform-managed repository. It complements, but does not
replace, repository `AGENTS.md`, OpenSpec, or the task-intake contract.

## Bounded maps and context pointers

Always-on instruction surfaces are maps: they state durable triggers,
invariants, and destinations. Put workflow mechanics, examples, and rules that
only apply after a task reaches a concern in the concern-specific canonical
document.

A context pointer names both the concern and its authoritative destination. An
agent must be able to discover the document for a reached concern without
loading every detailed document on every task. A concern that is not reached
does not make its detailed guidance universal context.

Keep the root map bounded. Adding a new durable concern means adding one
discoverable pointer and targeted evidence, not copying its workflow into every
runtime adapter.

## Surface ownership

| Surface | Owns | Must not own |
| --- | --- | --- |
| `AGENTS.md` and rendered `template/AGENTS.md.jinja` | navigation, task-intent triggers, safety invariants, and canonical destinations | detailed workflow manuals or runtime-specific copies of shared policy |
| `CLAUDE.md` and rendered `template/CLAUDE.md.jinja` | a thin pointer to the applicable root map and bounded runtime-specific mechanics | an independent lifecycle or authoring policy |
| `docs/engineering/task-intake.md` and its rendered equivalent | shared managed-task intent boundaries, representation, source-of-truth model, and authoring STOP behavior | ChatGPT-only or repo-local transport details as separate semantics |
| `docs/engineering/chatgpt-project-protocol.md` | connected-GitHub authoring mechanics for a ChatGPT Project with no target checkout | a competing task format or implementation lifecycle |
| repository-local `managed_task.py` | deterministic authoring and intake mechanics from a checkout | a different semantic contract from task intake |

When a shared rule changes, update its sole owner and the pointers or rendered
reference that expose it. Runtime-specific text may describe a genuine
mechanical difference, but it must link back to the shared owner instead of
restating an equivalent policy.

## Cross-surface managed authoring

`task-intake.md` is the semantic owner. A fixation is one Development Backlog
Issue with one active `managed-openspec:v1` package, and it stops in `Backlog`.
The target-repository checkout changes only after normal managed start
materializes that package; the local OpenSpec is then canonical.

Repository-local Codex and Claude use `managed_task.py create --bundle ...`
when it is available. ChatGPT Project may use its supported connected GitHub
mutations when it has no checkout, but must create the same package shape and
must not start implementation. The ordinary `start_managed_task.py` importer
accepts either result without translation.

## Evidence

For an instruction-surface change, add proportionate evidence for:

- pointer destinations and rendered root coherence;
- a positive reached-concern discovery case and a negative unrelated-concern
  case;
- thin tool-specific adapters with no duplicate shared policy; and
- representative ChatGPT Project and repository-local fixation representations
  that parse through the normal managed package contract.

## Upstream reference

The current `writing-for-agents` material was reviewed as an upstream reference
only on 2026-09-01. The adopted principles are bounded always-on context,
explicit trigger-bearing pointers, and one coherent instruction system across
entry files and linked documents. Dev Platform remains the authoritative,
provider-neutral owner: this reference is neither a runtime dependency nor a
required external service.
