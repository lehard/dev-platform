# Managed Project status acceptance evidence

Date: 2026-08-11

## Project preflight

- Authenticated GitHub CLI access exposed the configured user Project
  `lehard/1` with Projects mutation scope.
- The Project contained exactly one single-select `Status` field with the
  reviewed options `Backlog`, `Ready`, `In progress`, `In review`, `Blocked`,
  and `Done`.
- `lehard/development-backlog#8` resolved to exactly one Project item. A real
  idempotent reconciliation observed it already at `In review` and performed no
  mutation.

## Historical recovery

- `lehard/development-backlog#2` was observed stale at `Ready`.
- Repository evidence was unambiguous: archived managed provenance exists at
  `openspec/changes/archive/2026-08-11-add-central-dogfood-lifecycle/`, and
  exact delivery PR `lehard/dev-platform#118` is GitHub-confirmed `MERGED` at
  2026-08-11T12:08:07Z.
- The new reconciliation primitive updated only that exact Project item to
  `Done`. The first live mutation attempt exposed that a numeric-looking GitHub
  single-select option ID must be sent as a GraphQL String rather than through
  GitHub CLI's magic typed-field conversion; the transport was corrected and
  covered by a regression test before the successful retry.

No `Blocked` transition was fabricated: there was no genuine external blocker
after Projects authorization was restored.
