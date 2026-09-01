# Proposal: Add optional engineering capability lifecycle

## Why

Dev Platform is beginning to add reusable engineering behaviors such as debugging protocols, architecture review, browser verification, design guidance, and selective domain interrogation. These are orthogonal to the existing `workflow_profile`, yet there is no shared lifecycle for declaring, discovering, invoking, evaluating, pinning, opting into, materializing, updating, listing, and removing them. Letting every capability invent those mechanics would recreate provider and project drift and would force users to remember internal skill names.

## What Changes

- Define a provider-neutral contract for optional engineering capabilities, separate from core workflow capabilities.
- Add deterministic project opt-in, invocation policy, materialization, provenance, update, removal, catalog generation, and health validation.
- Follow native Agent Skills progressive disclosure: `name + description` drive discovery, full instructions load on invocation, and explicit invocation remains available where supported.
- Add one discoverable capability-management/authoring path for create/update/remove/list/audit operations and integrate bounded automatic eval decisions with #79.
- Support instruction-only and tool-backed capabilities without coupling application production runtimes to development tooling.
- Preserve one canonical source when provider-local Codex/Claude surfaces must be generated.
