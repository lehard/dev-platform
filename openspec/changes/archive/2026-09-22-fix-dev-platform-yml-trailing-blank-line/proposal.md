# Proposal: Fix the trailing-blank-line whitespace failure in dev-platform.yml.jinja for harness_mode=platform

## Why

The prior `fix-rollout-trailing-blank-lines` change fixed the same class of Jinja whitespace-control defect in `.gitlab-ci.yml.jinja` and `task-intake.md.jinja`, but explicitly deferred `template/.github/workflows/dev-platform.yml.jinja` as not yet confirmed blocking. It is now confirmed blocking: a real `Roll Out Platform` dispatch for `lehard/cuby` (`harness_mode=platform`) failed at `git diff --cached --check` with `.github/workflows/dev-platform.yml:51: new blank line at EOF`.

## What Changes

- `template/.github/workflows/dev-platform.yml.jinja`: change the `{% else %}` that closes the `harness_mode == 'platform'` branch to `{%- else %}`, matching the `{%- endif -%}` that already exists for the symmetric `harness_mode == 'project'` branch. The asymmetry meant only the `platform` branch's own trailing newline was never trimmed, so the file's unconditional final `{{ '\n' -}}` always produced a double newline (blank line at EOF) specifically for `harness_mode=platform` projects.

## Success Evidence

Real `copier copy --trust --defaults` renders for both `harness_mode` values, followed by `git init` + `git diff --cached --check`, both exit 0. A full-tree diff between a render built from this change and one built from its parent commit shows exactly one line removed (the trailing blank at line 51) in exactly one file.

## Dependencies

Continues `fix-rollout-trailing-blank-lines` (lehard/development-backlog#147) and, transitively, `add-legacy-baseline-bridge` (lehard/development-backlog#146): both earlier fixes are prerequisites for a rollout run reaching this far.
