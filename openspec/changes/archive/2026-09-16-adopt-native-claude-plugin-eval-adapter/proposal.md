# Proposal: Use Claude Code native plugin eval as the Claude capability-eval adapter

## Why

Development Backlog #79 intentionally left live Claude evaluation unsupported because the available upstream pattern required nested `claude -p` execution and provider-specific event parsing. Claude Code 2.1.269 now exposes a supported `claude plugin eval` surface with scored machine-readable results, so Dev Platform can reassess that boundary without building its own Claude runner.

## What Changes

- Add a bounded preflight and provider adapter around `claude plugin eval` if its supported contract supplies the evidence needed by the existing provider-neutral eval core.
- Normalize only the minimum truthful result/provenance needed by Dev Platform.
- Preserve existing deterministic fixtures and lifecycle eval decisions.
- Keep Codex unsupported until a comparable supported surface exists; do not fake symmetry.
