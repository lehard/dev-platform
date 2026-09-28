## Why

Concrete model bindings are the replaceable layer of model routing, and the current Codex bindings (`gpt-5.6-terra` for routine/standard, `gpt-5.6-sol` for complex) are one generation behind. The stable GPT-6 tiers (`gpt-6-sol`, `gpt-6-luna`) are in Codex, cheaper than their GPT-5.6 predecessors, and there is no GPT-6 Terra. Claude Code already resolves its `haiku`/`sonnet`/`opus` aliases to Haiku 4.5, Sonnet 5.5 and Opus 5.5.

## What Changes

- Codex bindings become `routine=gpt-6-luna`, `standard=gpt-6-sol`, `complex=gpt-6-sol`; superseded `gpt-5.6-terra` is removed from policy.
- Claude bindings keep the provider aliases, which follow the current generation (Sonnet 5.5 for `standard`); no pinned snapshot ids because the native Agent handoff accepts only the aliases.
- Both the central `.dev-platform.toml`, the rendered template and the built-in `DEFAULT_MODELS` fallback carry the same values.
- The model-routing spec states that a binding change is a policy-only change: tiers and assurance stay independent, only stable models are eligible, delivery is via immutable release/Copier update, and rollback is reverting the binding through the same path.

## Impact

Policy values and one spec requirement. Historical routing records naming `gpt-5.6-*` stay readable and calibration continues to group them by recorded model. Managed projects pick up the new values through the normal template update; no per-project edits. Evidence for the new bindings is intentionally the dogfood record accumulated after adoption via `model_routing.py routing-calibration`, since no usable observations exist yet for the new models.
