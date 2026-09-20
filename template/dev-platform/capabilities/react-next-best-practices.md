# React / Next best practices

Stack-specific engineering guidance for React and Next.js (App Router) work:
implementation structure and runtime performance. It applies **only** when the
project is a compatible React/Next codebase and has enabled this capability. It
does not apply to non-React frontends, backend-only work, or unsupported major
versions, and it never changes the application's dependencies.

## Precedence

This guidance is subordinate. When any of the following exists it wins and this
capability only helps you apply it well:

1. Project product requirements and accepted OpenSpec behaviour.
2. A project-owned design system, architecture decision, or lint/config contract.
3. Accessibility, regulatory, and functional-testing requirements.

It never changes product intent, never creates backlog or spec work, and adds no
application runtime dependency.

## How to use this index

This file is a slim always-loaded index. The actual rules live in bounded topic
groups. **Read only the group that matches the task** from
`dev-platform/capabilities/react-next-best-practices/`:

| Task involves | Read this group |
| --- | --- |
| Choosing Server vs Client Components, `"use client"`, boundaries, `use()` | `server-client-components.md` |
| Data fetching, request waterfalls, caching, streaming, `Suspense` | `data-fetching-and-waterfalls.md` |
| Bundle size, `import()` code-splitting, `next/dynamic`, heavy dependencies | `bundle-and-code-splitting.md` |
| Wasted renders, memoisation, derived state, `key`, effect misuse | `rendering-and-re-renders.md` |

If a task spans two groups, read both; do not load the others. If none match,
this capability has no specific rule — follow the project's own conventions.

## Provenance

The topic groups are an independent, bounded adaptation of widely published,
version-pinned guidance (Next.js App Router documentation and react.dev). Dev
Platform vendors none of those files and fetches none at runtime. The reviewed
revisions, licences, and treatment are recorded in
`docs/engineering/engineering-capabilities.md`. Adopting newer upstream guidance
is an explicit reviewed
`python3 scripts/capability_manager.py update react-next-best-practices`.
