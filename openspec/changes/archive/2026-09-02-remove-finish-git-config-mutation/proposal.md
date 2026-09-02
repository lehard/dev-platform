# Proposal: Remove Git config mutation from ordinary finish

## Why

Ordinary publication rewrites stable shared-repository configuration and makes independent tasks contend on `.git/config.lock`. Ephemeral Git maintenance paths can also disappear during audit and cause a false failure.

## What Changes

- Separate stable shared-repository setup/repair from ordinary read-only verification.
- Reuse the existing serialized integration boundary for the rare repair.
- Treat disappearance of an ephemeral Git lock as a bounded rescan condition.
- Preserve fail-closed handling of durable permission and foreign-state problems.
