## Why

The Requirement asks whether TeamAI can replace parts of Dev Platform infrastructure and shrink our own maintenance surface. Desk research (2026-09-28) shows real overlap. It also shows possible structural mismatches with Dev Platform's pinned-release model:

- team resources are pulled from the latest default branch on every session;
- the CLI self-updates by default;
- the tool writes to HOME and shell profiles;
- team hooks and MCP servers are auto-applied.

Several capabilities (version-bound skills, model profiles) exist only in betas. The accepted `upstream-substitution` gate requires deciding from observed pilot evidence rather than from desk research or from the fact that we already have an implementation.

## What Changes

- Run a sandboxed pilot of the exact stable TeamAI release covering the seven overlap areas, on a representative Dev Platform workflow and a freshly rendered managed-project fixture with Claude Code and Codex.
- Commit a decision record `docs/engineering/upstream-evaluations/teamai.md`. It holds the per-area decision, evidence, ownership classification, maintenance-surface baseline, and the retirement set or retention evidence.
- Add a spec requirement that fixes the evaluated boundary. Until a separate adoption change lands, every area remains Dev Platform-owned, and TeamAI is not a managed-project dependency.

## Impact

This change produces a documentation and specification record only. No runtime, template, capability or rollout behavior changes. A follow-up adoption child is authored only for areas decided `adopt-next-step`.
