# Proposal: Establish durable decision registry

## Why

Consequential decisions and their rationale are scattered among OpenSpec archives, evaluations and issues. Provider changes can lose the reasons and revisit conditions even when current behavior remains discoverable. Requirement lehard/development-backlog#249 requests a durable shared decision history and the TeamAI decision as its first record.

## What changes

Add a repository-backed decision registry with a bounded record format, explicit historical supersession and selective discovery from the canonical agent map. Seed it with the TeamAI v0.25.0 rejection, watch candidates and re-evaluation conditions. Clarify that the registry captures rationale while OpenSpec continues to define accepted executable behavior.

## Success evidence

A repository-only reader can find the TeamAI decision, explain why wholesale adoption is deferred, identify promising capabilities, and name concrete revisit triggers. The registry format handles accepted, rejected-for-now and deferred alternatives without rewriting earlier records.

## Constraints and non-goals

Do not create backlog, task status, implementation contract or permanent ADD state. Do not backfill all historical decisions or initiate TeamAI adoption.
