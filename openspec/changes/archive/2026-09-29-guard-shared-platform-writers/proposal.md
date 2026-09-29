# Proposal: Guard platform-owned shared file publication

## Why

Two machine-local Process Health Review reports were created with mode 0644 and blocked a different agent's managed finish. A local probe showed that a patch tool can create 0644 even when the shell reports umask 0002. Guidance alone cannot prove that future writers preserve the shared group-write contract.

## What changes

Establish a supported, checked create-only publication path for Process Health Review reports using the existing shared group contract. Define a reusable output verification contract for platform-owned files in registered shared paths: a writer must verify group write on its own published output before success, and a new direct writer must pass a CI review guard. Detect noncompliant output at the closest controlled boundary, without repairing another agent's state.

## Success evidence

A report published through the supported path remains group writable under a hostile umask; a writer that leaves 0644 fails an automated regression check or its publication boundary; no unrelated writer's files are altered. Arbitrary external editors remain outside platform control and are caught by the explicit post-review check.
