# Proposal: align self-contained CI contract

## Why

`v1.0.1` removed the private reusable-workflow dependency, but template documentation and the `platform_ci_ref` question still described the old execution model. Leaving that text would create process drift immediately in downstream projects.

## Goal

Align generated agent/readme guidance and Copier help with the already-shipped self-contained CI design. No lifecycle or CI behavior changes.
