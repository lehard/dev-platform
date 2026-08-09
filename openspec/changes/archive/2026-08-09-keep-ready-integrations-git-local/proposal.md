# Keep ready-generated integrations Git-local

## Why

`v1.4.1` correctly preserves mature project `.gitignore` files. That means `scripts/dev.py ready` must not rely on adding new platform ignore patterns to those tracked files: regenerating Codex/Claude integrations in an older mature repository could otherwise leave machine-local generated paths untracked and make the checkout dirty immediately after readiness.

## What changes

- `scripts/dev.py ready` idempotently records machine-local generated integration patterns in `.git/info/exclude` before OpenSpec refresh.
- Document `.gitignore` as project-owned for mature adoption and explain clone-local excludes.
- Add regression coverage and clarify the rollout specification.
