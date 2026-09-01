# Proposal: Harden agent-facing instruction architecture

## Why

Dev Platform already keeps `AGENTS.md` bounded and delegates detail to concern-specific engineering documents, but that architecture is not yet expressed as a verifiable quality contract. A recent task-authoring review exposed a concrete consequence: ChatGPT Project and repo-local agents share the same managed-task semantics but have different runtime mechanics, and the current documentation can be read as if the repo-local CLI were mandatory everywhere.

## What Changes

- Define reusable quality requirements for bounded always-on instructions and explicit context pointers.
- Audit central, rendered, and ChatGPT-specific instruction surfaces against those requirements.
- Make cross-surface managed authoring explicit: one canonical representation and intent semantics, surface-appropriate supported publication mechanics.
- Add focused structural and bounded behavioral evidence for instruction routing and authoring equivalence.
- Use `writing-for-agents` as upstream reference only; keep Dev Platform authoritative and provider-neutral.

## Outcome and success evidence

The central and rendered root maps expose a discoverable instruction-architecture
pointer while remaining within their existing bounded-context budget. Thin
Claude adapters point to the root map without copying task authoring policy.

Both conversation surfaces state one Backlog-only managed representation:
focused tests prove that a controlled ChatGPT Project fixture without local
shell access and a repository-local `managed_task.py create --bundle ...`
fixture produce compatible package semantics consumable by normal managed
package discovery. Documentation links, template rendering, and the focused
behavioral cases must pass.

## Scope and constraints

This change affects the central repository and newly rendered downstream
projects. It adds platform-owned template guidance without overwriting
project-owned existing `AGENTS.md` files during Copier update. It does not add a
ChatGPT service dependency, new package version, importer, task lifecycle, or
external skill runtime dependency.

## Current to target

Today the shared managed-task semantics can be read as requiring the
repository-local CLI everywhere, and no single quality contract names the
ownership of root maps, thin adapters, task intake, and the ChatGPT adapter.
After this change, task intake owns shared semantics; each surface points to
that owner and states only the mechanics specific to its available capability.
