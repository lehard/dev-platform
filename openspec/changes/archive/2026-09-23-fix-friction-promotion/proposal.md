# Proposal: Restore friction promotion

## Why

`agent_friction.py promote` refers to `config` without defining it, so promotion crashes after reading operator configuration.

## What changes

Resolve the project identity from the current platform configuration in the command path and verify promotion through the CLI.

## Non-goals

No change to event routing, sanitization, or the destination policy.
