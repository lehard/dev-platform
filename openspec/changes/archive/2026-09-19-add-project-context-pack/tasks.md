## 1. Context ownership and structure

- [x] 1.1 Define the canonical project-context ownership model and bounded `docs/context/` entrypoint without duplicating project rules, checks, OpenSpec, module rules, or detailed docs.
- [x] 1.2 Add the minimal fresh-project/template surface needed for discoverability while avoiding empty mandatory placeholder ceremony.
- [x] 1.3 Extend ownership/Copier preservation behavior so reviewed project context survives updates.

## 2. Discovery and OpenSpec routing

- [x] 2.1 Add a bounded root/context pointer that makes project context discoverable only when the task reaches a relevant project/domain concern.
- [x] 2.2 Extend rendered OpenSpec guidance so proposal/spec/design/tasks route to relevant project context proportionally instead of loading the whole pack.
- [x] 2.3 Keep provider-specific adapters thin; do not copy project-context policy into Claude/Codex-specific files.

## 3. Evidence-first bootstrap/interview

- [x] 3.1 Implement the smallest provider-neutral bootstrap surface that inventories/uses existing README, project rules, OpenSpec, code/checks, and existing docs before requesting human input.
- [x] 3.2 Define one-question-at-a-time interview behavior for unresolved product/domain/architecture gaps and explicit unknown/TODO handling.
- [x] 3.3 Ensure raw source material is temporary/machine-local by default and is not silently committed with distilled context.
- [x] 3.4 Preserve existing non-empty project context; bootstrap must never silently rewrite reviewed content.

## 4. Regression evidence and delivery

- [x] 4.1 Add focused tests/checks for bounded root guidance, reached-concern discovery, unrelated-task non-loading, targeted OpenSpec routing, and fresh rendering.
- [x] 4.2 Add an existing-project update fixture proving project-owned context survives Copier update.
- [x] 4.3 Exercise a representative bootstrap with existing evidence plus at least one unresolved gap and verify the agent/helper does not invent the answer.
- [x] 4.4 Run selected platform checks and semantic OpenSpec verification, record truthful verification evidence, archive, and publish through the normal Dev Platform lifecycle.
