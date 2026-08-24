# Proposal: Tighten execution baseline comparability

## Why

The first execution-efficiency baseline is live, but its decision-quality gate currently keys off launched executions rather than verified managed executions, and its generic request counter can represent different runtime event semantics. Those ambiguities must be removed before a meaningful historical sample accumulates.

## What Changes

- Gate decision-quality evidence on verified eligible executions, not launch count alone.
- Expose launched, verified/eligible and missing-verification coverage separately.
- Use a cross-runtime model-request counter only where the runtime contract proves that exact semantic; otherwise preserve unknown or explicitly runtime-local counters.
- Keep historical records readable without silently mixing incompatible counter semantics.
- Keep the existing single provenance path and runtime-neutral schema.
