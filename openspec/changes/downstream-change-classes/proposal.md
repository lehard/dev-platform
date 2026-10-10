## Why

A downstream project that has installed Dev Platform cannot tell which platform-owned behavior it may repair locally when a mechanism is defective. `docs/ownership.md` only says a project must not silently weaken platform safety rules; it defines no sanctioned temporary repair and no list of rules that must never be touched. Observed defects (lehard/dev-platform#420, #425, #427) each stopped product work until a new immutable release. An agent facing such a stop has two bad options: bypass the guard on its own judgment, or wait. This change gives the downstream contract the missing vocabulary and a machine-readable boundary, so a later change can allow a controlled local hotfix without an agent ever declaring a sensitive gate "safe".

## What Changes

- A new downstream contract with three change classes: (a) ordinary project change, (b) temporary local hotfix of a platform-owned mechanism that keeps every guarantee, (c) protected rule that no local change or recovery may bypass or alter.
- A platform-shipped, versioned, machine-readable protected surface (`dev-platform/protected-surface.toml`) naming protected rule categories and the platform-owned paths that implement them: independent review, protected publication, isolation of other agents' worktrees, credential restrictions, routing/provenance/evidence authenticity, Git-history protection and immutable releases.
- A fail-closed classification: every platform-owned, plain-copied file is classified `protected` or `hotfixable`; an unclassified file is a platform test failure, never a default.
- Template guidance: `docs/engineering/change-classes.md` plus a pointer row in the generated `AGENTS.md` concern table, stating that an agent never reclassifies a file or rule and that class (c) changes only through a platform release (or a recovery path the gate itself already defines).

## Capabilities

### New Capabilities

- `downstream-change-classes`: the three-class contract, the protected surface and the fail-closed classification.

## Impact

`template/dev-platform/protected-surface.toml`, `template/docs/engineering/change-classes.md`, `template/AGENTS.md.jinja`, `docs/ownership.md`, `AGENTS.md` pointer and a platform test that classifies the template tree. Rendered into new projects and delivered to existing ones by Copier update. No behavior of any existing gate changes.

## Non-goals

Hotfix records, divergence detection or gate recovery semantics (separate changes of this Requirement); re-fixing BR-519, BR-522 or #427; a universal `--force`, global disabling of checks or any implicit right of an agent to change the protective contract; upstream back-porting of patches.
