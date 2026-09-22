# Design: Fix dev-platform.yml.jinja's harness_mode=platform trailing blank line

## Root cause, confirmed empirically

Reproduced live: dispatched `Roll Out Platform` for `lehard/cuby` against `v1.5.4` (after `add-legacy-baseline-bridge`, `fix-rollout-trailing-blank-lines`, and `fix-reconcile-missing-registry-flag` were all already shipped). Confirmed `lehard/cuby`'s own `.dev-platform.toml` records `harness_mode = "platform"`. `copier update` and the rest of `apply_rollout()` proceeded, then `git diff --cached --check` failed with `.github/workflows/dev-platform.yml:51: new blank line at EOF`.

Read `template/.github/workflows/dev-platform.yml.jinja` in full: it has an inner `{% if harness_mode == 'platform' %} ... {% else %} ... {%- endif -%}` construct, itself nested inside an outer `{% if scm_provider == 'github' %} ... {% else %} ... {%- endif -%}{{ '\n' -}}`.

Traced the exact whitespace-control asymmetry by hand and confirmed with a local `jinja2.Environment(keep_trailing_newline=True)` render before touching the template: the `else` branch (`harness_mode == 'project'`) is followed by `{%- endif -%}`, whose leading `{%-` strips the whitespace immediately before it in the source -- specifically, the `else` branch's own trailing newline. The `if` branch (`harness_mode == 'platform'`) is followed by a plain `{% else %}` with no leading `-`, so its own trailing newline (from the last `--execute` line) is never stripped. The outer construct's unconditional trailing `{{ '\n' -}}` then always appends one more newline regardless of which inner branch rendered -- for the `project` branch this exactly replaces the newline the inner `-` already stripped (net: one clean newline), but for the `platform` branch it stacks on top of a newline that was never removed (net: a blank line at EOF).

Verified this precisely with a real `copier copy --trust --defaults` render for both `harness_mode` values before and after the fix: pre-fix, `harness_mode=platform` renders 51 lines ending in a blank line; `harness_mode=project` already rendered cleanly (45 lines, no blank). Post-fix, `harness_mode=platform` renders 50 lines with no blank line, and `harness_mode=project` is unchanged.

## Fix

`{% else %}` (the tag closing the `harness_mode == 'platform'` branch) -> `{%- else %}`, symmetric to the existing `{%- endif -%}` on the other branch. No other tag in the file needed a change.

## Explicitly out of scope

- `template/AGENTS.md.jinja`, `template/docs/engineering/agent-workflow.md.jinja`: same defect class was found present during the prior `fix-rollout-trailing-blank-lines` investigation but not yet confirmed to block any of the three currently-managed projects (`lehard/planner-agent-lab`, `lehard/Jara_Fin`, `lehard/cuby`). Left alone until they are actually observed blocking a real rollout, per the same scope discipline used for this file until it turned out to be reached.
- `lehard/Jara_Fin`'s own `.github/workflows/dev-platform.yml.rej` conflict during its `v1.5.4` rollout attempt: confirmed via `gh api` that Jara_Fin's committed file still pins `openspec@1.8.0` (a much older platform lineage than the fresh-history canonical repo), and Copier's own three-way merge -- not this fix -- is what raises `.rej` when a downstream file has diverged from its recorded baseline in a way the new template's changes also touch. This is exactly the behavior the accepted `platform-rollout` spec's "Unresolved template-update conflicts block completion" requirement intends: a genuine per-project conflict that stops for human review, not a platform defect to silently resolve.

## Tests

No new automated test: this is the same class of fix as `fix-rollout-trailing-blank-lines`, which established that a unit test meaningfully covering real Copier whitespace-control behavior would need to invoke real rendering (matching `tests/upgrade_smoke.py`'s existing approach) rather than a cheap string assertion. The verification evidence (real Copier renders, `git diff --cached --check`, and a full-tree diff proving no other file changes) is recorded in `verification.md`.
