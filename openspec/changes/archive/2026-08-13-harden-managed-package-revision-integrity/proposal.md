# Proposal: Harden managed package revision integrity

## Why

Managed authoring currently records a fresh target `prepared_against` revision, but validation can still run against a stale local checkout. Separate incidents also showed that a published package can become structurally unusable with no supported repair path, and that the source Development Backlog Issue can materially change after package authoring without the executor seeing the drift.

These are one lifecycle problem: package identity is strong enough for idempotent import, but not strong enough to prove what repository/Issue revision was accepted or to replace a bad pre-execution revision safely.

## What Changes

- Bind authoring validation to the exact repository revision recorded as `prepared_against`.
- Record bounded source-Issue revision evidence at package authoring.
- Detect source-Issue drift before start and after materialization without silently rewriting canonical OpenSpec.
- Add one supported, idempotent package supersede/repair path that validates the replacement before activation and leaves one active revision.
- Preserve backward compatibility for existing packages where practical and reuse the existing managed-task revision/provenance machinery.

## Impact

- Modified specification: `managed-task-intake`.
- Expected surfaces: `template/scripts/managed_task.py`, central adapter/tests, managed start/status/finish drift diagnostics, authoring/import regression fixtures and docs as needed.
