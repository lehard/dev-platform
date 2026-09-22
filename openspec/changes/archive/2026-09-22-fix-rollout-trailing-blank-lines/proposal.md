# Proposal: Fix trailing-blank-line whitespace failures in two rendered project-factory templates

## Why

The first real post-cutover `Roll Out Platform` run to get past the legacy-baseline-bridge fix (for `lehard/planner-agent-lab`, `v1.4.38 -> v1.5.2`) failed one step later: `git diff --cached --check` rejected the Copier-updated diff because `.gitlab-ci.yml` and `docs/engineering/task-intake.md` each render with a trailing blank line at end-of-file. Both templates place `{% if %}/{% else %}/{% endif %}` control tags on their own source line without Jinja whitespace-control markers, so Copier's Jinja environment (which sets `keep_trailing_newline=True` but not `trim_blocks`/`lstrip_blocks`) leaves the tags' own adjacent newlines in the rendered output.

## What Changes

- `template/.gitlab-ci.yml.jinja`: change the final `{% endif %}` to `{% endif -%}` (nothing follows it in the file, so trimming everything after it is safe).
- `template/docs/engineering/task-intake.md.jinja`: remove two stray literal blank lines that sit immediately before `{% else %}` and `{% endif %}` in the source, and change the final `{% endif %}` to `{% endif -%}`.

No change to `copier.yml`'s Jinja environment options: a global `_envops: {trim_blocks: true, lstrip_blocks: true}` was tried and rejected because it corrupts `template/.github/workflows/process-health-labels.yml.jinja`'s inline `{% raw %}...{% endraw %}` usage (`trim_blocks` eats the newline after `{% endraw %}` at end-of-line, gluing two YAML lines together into an invalid document). This fix is deliberately per-file and per-tag.

## Success Evidence

- A real `copier copy --trust --defaults --vcs-ref HEAD` render (light/standard/multi-agent profiles, harness_mode platform and project) produces `.gitlab-ci.yml` and `docs/engineering/task-intake.md` with no trailing blank line, verified by running `git diff --cached --check` against a freshly `git init`'d copy of the rendered tree (exit 0).
- A full-tree `diff -rq` between a render built from this change and one built from its immediate parent commit shows exactly two files differ, each losing exactly the intended stray blank line(s); no other rendered file changes.
- The full platform test suite (`python3 scripts/run_test_groups.py --all`) passes unchanged (1140/1140).

## Dependencies

None. This is a narrower continuation of the already-merged `add-legacy-baseline-bridge` change (lehard/development-backlog#146): that fix let Copier's 3-way diff succeed against a pre-cutover baseline; this fix lets the resulting diff pass the whitespace-hygiene gate that runs immediately afterward in `scripts/rollout_project.py`.
