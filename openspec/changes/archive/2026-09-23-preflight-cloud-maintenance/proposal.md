# Proposal: Preflight cloud maintenance setup

## Why

The cloud workflows can be present and enabled while their `OPENAI_API_KEY` is absent or invalid, leaving Process Issue Triage broken only when triggered.

## What changes

Provide a bounded operator setup check that checks enabled workflows, secret presence and provider authentication through GitHub Actions without exposing secret values. Document how to invoke and interpret it.

## Non-goals

No secrets in source; no new monitoring service or runtime state store.
