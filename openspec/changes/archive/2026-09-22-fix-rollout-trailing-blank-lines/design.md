# Design: Fix trailing-blank-line whitespace failures in rendered templates

## Root cause, confirmed empirically

Reproduced live: `Roll Out Platform` for `lehard/planner-agent-lab` (`v1.4.38 -> v1.5.2`, after the legacy-baseline-bridge fix already shipped) got past `copier update` cleanly, then failed `git diff --cached --check` (in `scripts/rollout_project.py`'s `apply_rollout()`) with:

```
.gitlab-ci.yml:14: new blank line at EOF.
docs/engineering/task-intake.md:37: new blank line at EOF.
```

Confirmed Copier's actual Jinja defaults by reading the installed `copier` 9.17.1 source (`copier/_template.py`): `envops` defaults to `{}` unless a template's `copier.yml` sets `_envops`; `copier/_main.py`'s `jinja_env` property passes those `envops` straight to `jinja2.sandbox.SandboxedEnvironment(...)`. `copier/_template.py` additionally hardcodes `result.setdefault("keep_trailing_newline", True)`, but never sets `trim_blocks`/`lstrip_blocks`. Plain Jinja2 defaults for those two are `False`. This means a block tag (`{% if %}`, `{% else %}`, `{% endif %}`) placed alone on its own source line leaves its own line's newline as literal output text, since nothing trims it.

Verified the exact mechanism with isolated `jinja2.Environment(keep_trailing_newline=True)` renders of the real template source (not guesswork): both files render with a trailing `\n\n` (blank line at EOF) exactly matching the CI failure, for whichever `harness_mode`/`operator_config_path` branch is exercised.

## Why a global envops fix was rejected

Tried `_envops: {trim_blocks: true, lstrip_blocks: true}` in `copier.yml` first, since that is the standard Jinja-recommended way to make own-line control tags fully invisible in output. Verified with a real `copier copy --trust --defaults` render across all 3 workflow profiles that it fixes both target files. But a full-tree `diff -rq` against an unfixed baseline render also showed `template/.github/workflows/process-health-labels.yml.jinja` corrupted:

```
-          GH_TOKEN: {% raw %}${{ github.token }}{% endraw %}
-          REPOSITORY: {% raw %}${{ github.repository }}{% endraw %}
-        run: |
+          GH_TOKEN: ${{ github.token }}          REPOSITORY: ${{ github.repository }}        run: |
```

`trim_blocks` removes the newline immediately following ANY block tag, including `{% endraw %}` used inline at the end of a content line -- gluing that line to the next. This is a real, verified regression, not a hypothetical one. A global env-level fix is unsafe without an exhaustive per-file audit of every Jinja tag usage across `template/`, which is out of scope here. Reverted the `copier.yml` change entirely.

## Fix

Per-file, per-tag, minimal `-` trim markers, applied only where a tag borders another tag or absolute end-of-file -- never where it borders real indented content (confirmed empirically that `-` strips ALL contiguous whitespace including indentation, not just one newline, via `jinja2.Environment().from_string('A{% if True -%}\n    B\n{%- endif %}').render()` -> `'AB'`, i.e. it also ate the indentation).

Also established, by checking `git diff --check`'s actual whitespace-error categories (`blank-at-eol`, `blank-at-eof`, `trailing-space`, `space-before-tab`, `tab-in-indent`), that a blank line in the *middle* of a file is never flagged -- only a blank line at the true end of the file is. This meant the interior blank line each of these two conditionals also produces (e.g. before the `- echo ...` line in `.gitlab-ci.yml`) does not need fixing at all; only the tag closing the file needed a trim marker.

- `.gitlab-ci.yml.jinja`: `{% endif %}` -> `{% endif -%}`. It is the file's last tag with nothing meaningful after it (just its own trailing newline), so trimming everything after it is safe regardless of which branch (`harness_mode == 'platform'` or the `else`) was taken.
- `task-intake.md.jinja`: the file has a bug of a different flavor at two spots -- an explicit, literal blank line was authored in the source directly before `{% else %}` (line ~172) and before `{% endif %}` (line ~209). These are not tag-adjacent-newline artifacts; they are literal blank lines that were written into the file. Removed both directly (no trim marker needed for these, since deleting the literal blank line source content is the correct, non-magical fix). Also changed the final `{% endif %}` to `{% endif -%}`: the text after `{% endif %}` (a lone trailing `\n`) sits *outside* the if/else content span entirely, so it is emitted unconditionally regardless of which branch rendered -- both branches needed this second trim, not only the branch adjacent to the literal blank line just removed.

## Verification performed

- `jinja2.Environment(keep_trailing_newline=True)` renders of each fixed file (both branches of each conditional) confirmed byte-for-byte: single trailing `\n`, no blank line.
- Real `copier copy --trust --defaults --vcs-ref HEAD` renders for `workflow_profile` in `{light, standard, multi-agent}` and `harness_mode` in `{platform, project}` (`operator_config_path` set and unset for `task-intake.md.jinja`'s two branches), each followed by `python3 -m compileall` and `python3 scripts/platform_doctor.py` inside the rendered tree (matching `ci.yml`'s own "Render factory profiles" step), all green.
- `git init` + `git add -A` + `git diff --cached --check` on a fixed render: exit 0 for both target files.
- Full-tree `diff -rq` of a fixed render against an unfixed-baseline render of the same profile: exactly the two target files differ, each losing only the intended stray blank line(s).
- `python3 scripts/run_test_groups.py --all`: 1140/1140 unchanged.

## Explicitly out of scope

- `template/.github/workflows/dev-platform.yml.jinja`, `template/AGENTS.md.jinja`, `template/docs/engineering/agent-workflow.md.jinja`: same defect class, confirmed present (via the same real-render method), but not currently blocking any in-flight rollout, and `dev-platform.yml.jinja` already has its own hand-rolled `-` trim markers whose full interaction needs separate, careful analysis. Flagged as a follow-up task rather than folded into this fix.
- Any change to `copier.yml`'s `_envops` or other global Jinja settings.
- Any change to `scripts/rollout_project.py`'s whitespace-hygiene gate itself (`git diff --cached --check`); it is doing exactly its job by catching this.

## Tests

No new automated test is added: this is a pure template-content fix with no new branchable logic in Python source, and the existing `tests/test_template_contract.py` suite already asserts these files' structural presence and key content strings, which remain unaffected (verified: full suite green). The verification evidence above (real Copier renders plus `git diff --check`) is the actual regression protection for this specific defect class; it is recorded in `verification.md` as manual/empirical verification rather than a new unit test, since a unit test would need to invoke real Copier rendering to be meaningful (matching how `tests/upgrade_smoke.py` already does for the broader factory-render surface) and duplicating that harness for two lines is not proportionate.
