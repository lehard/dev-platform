# Design: OpenSpec stable version bump (1.13.0 -> 1.13.2)

## Approach

Pure pin bump plus focused regression growth. Every literal occurrence of the
tested OpenSpec version moves to `1.13.2` in one change. The existing exact-CLI
regression script (`tests/openspec_1_13_regression.py`, run by platform CI
against the pinned `npx` command) gains fixtures for each correctness fix that
motivated the bump, so a future downgrade or upstream regression is caught by
behavior, not by release notes.

## Evidence gathered before authoring

Probed with locally installed exact CLIs (`1.13.0` and `1.13.2`) in temporary
projects:

- Case-only duplicate `ADDED` requirement: `1.13.0` archives it (spec gains a
  second near-identical requirement); `1.13.2` aborts with "differs only in case
  or spacing" and changes no files.
- Unpaired `RENAMED` (`FROM`, `FROM`, `TO`): both refuse archive; `1.13.2`
  additionally fails `validate --strict`.
- Tasks `- [x]`, `- [~]`, `+ [ ]`, `1. [ ]`: `instructions apply --json`
  reports `all_done` 1/1 on `1.13.0` and `ready` 1/4 with
  `taskTrackingConfigured: true` on `1.13.2`.
- Generated verify workflow (platform custom profile incl. `verify`): `1.13.2`
  adds REMOVED-inverted and RENAMED-baseline checks, distinguishes
  "Not applicable" from "Not verified", and states "Verification is advisory
  ... Archive retains its own checks".
- The existing `1.13.0` fixtures (fenced literal header, wrapped `+` bullets
  capability retirement, missing-delta apply warning) pass on `1.13.2`.

## Platform guard decision

No platform guard is removed or reduced. The upstream verify workflow is an
agent prompt that explicitly declares itself advisory; the platform's
`verification.md` PASS receipt + method, automated-checks evidence, routing
gate and lifecycle archive remain the only enforced guarantees. Equivalence is
therefore not proven for any guard, which the existing requirement demands
before removal.

Noted but out of scope: the platform's own `openspec_lifecycle.task_state`
only recognises `- [ ]`/`- [x]` lines, the same marker gap upstream fixed in
`1.13.1`. Changing it is a separate platform behavior change, recorded as a
follow-up rather than silently folded into this bump.

## Risks and mitigations

- **Workflow drift**: CI (`ci.yml`), adoption (`adopt-project.yml`) and the
  rendered downstream workflow each install OpenSpec. All move together and
  `test_template_contract` asserts the exact pin in each.
- **Stricter validation breaking existing specs**: `1.13.2` rejects
  scenario-less requirements and unpaired renames. Mitigation: run
  `validate --all --strict` with `1.13.2` on this repository before archive.
- **Brittle prose assertions**: verify-workflow fixtures match only short,
  load-bearing phrases of the exact pinned version and are updated with the
  next deliberate bump.

## Alternatives considered

- Staying on `1.13.0`: rejected; it silently archives case-only duplicates and
  miscounts task progress.
- Removing platform verification in favour of `/opsx:verify`: rejected by the
  requirement exclusions and by upstream's own advisory framing.
