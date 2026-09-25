# Proposal: Add optional Telegram/webhook notification for the Platform Health Review report

## Why

the private Backlog task requires that a human be notified when a new Platform Health Review result is available, through a configured channel, without the notification duplicating the full report. GitHub is already the base channel (the report Issue itself, from `add-platform-health-review-report`), but nothing currently pushes a short summary to a human proactively, and no notification mechanism (Telegram, generic webhook) exists anywhere in the platform today: this is genuinely new integration surface.

## Current to target

Today: a human must know to check GitHub for a new Platform Health Review report; there is no proactive notification.

Target: after the combined report Issue is published, an optional notification step sends one short message (a summary plus a link to the report Issue) to a configured Telegram chat and/or a generic outbound webhook. Delivery is optional per channel: a channel with no configured secret is simply skipped, and GitHub remains fully functional as the base channel/source of truth with or without any external delivery enabled.

## What changes

- Add a `platform-health-review` requirement defining optional external notification: GitHub as the always-present base channel, Telegram and a generic webhook as optional additional adapters.
- Add a deterministic, non-agentic GitHub Actions step (a repository-owned script) that runs after the report Issue is published, formats the short summary + link, and sends it to whichever channel(s) are configured.
- Read any external channel secret (Telegram bot token/chat id, webhook URL) only from GitHub Actions repository secrets, mirroring the existing `OPENAI_API_KEY` pattern; never write such a secret into `dev-platform/capabilities.toml`, `.dev-platform.toml`, or any other portable/public project configuration file.
- Make which channels are enabled (not their secret values) ordinary project-owned capability configuration.

## Success evidence

- A Platform Health Review run with a Telegram secret configured results in exactly one Telegram message containing a short summary and the report Issue link.
- A run with no external-channel secrets configured completes normally with GitHub as the only channel; no error is raised for an intentionally unconfigured optional channel.
- A repository-wide secret-scan/public-distribution audit finds no channel secret in tracked source or portable project configuration.
- `openspec validate --strict` passes for the updated `platform-health-review` delta.

## Constraints and non-goals

This change does not add multi-recipient or per-repository notification routing (single configured destination per channel for this central v1 pilot). It does not add a new gh-aw safe-output type; notification logic runs outside the agent sandbox. It does not build a new operator-config layer for these secrets — GitHub Actions repository secrets are reused. It does not change what either review evaluates or how the report is composed.

## Delivery scope

An OpenSpec delta to `specs/platform-health-review/spec.md`, a repository-owned notification script, and the GitHub Actions workflow wiring that invokes it after the report step. No application/product code changes.

Identity-Redaction: Direct private Backlog identifiers were removed from this current-tree archive after the original review.
