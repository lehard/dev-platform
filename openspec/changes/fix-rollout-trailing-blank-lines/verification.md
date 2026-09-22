# Verification: Fix trailing-blank-line whitespace failures in two rendered templates

## Method

`/opsx:verify` was not available in this execution environment. Performed the documented equivalent manual OpenSpec semantic review: re-read `proposal.md`'s Why/What Changes/Success Evidence, `design.md`'s root-cause analysis (including why a global `_envops` fix was tried and rejected) and the `project-factory` spec delta's two ADDED scenarios, then checked the implementation (two `.jinja` files) against each claim individually, with real `copier` renders rather than reasoning about Jinja semantics abstractly.

## Root cause confirmation

Before writing this change: reproduced the failure live via the actual `Roll Out Platform` run for `lehard/planner-agent-lab` (`v1.4.38 -> v1.5.2`), which got past `copier update` (thanks to the already-merged `add-legacy-baseline-bridge` fix) and then failed `git diff --cached --check` with `.gitlab-ci.yml:14: new blank line at EOF` and `docs/engineering/task-intake.md:37: new blank line at EOF`. Confirmed Copier's actual Jinja defaults by reading the installed `copier` 9.17.1 source directly (`copier/_template.py`'s `envops` property, `copier/_main.py`'s `jinja_env` construction): `keep_trailing_newline=True` is hardcoded, `trim_blocks`/`lstrip_blocks` are not set unless a template's `copier.yml` opts in. Reproduced the exact byte-level defect with isolated `jinja2.Environment(keep_trailing_newline=True)` renders of the real template source before writing any fix.

## Alternative rejected, with evidence

Tried `_envops: {trim_blocks: true, lstrip_blocks: true}` globally in `copier.yml` first. Verified via a real `copier copy --trust --defaults` render across light/standard/multi-agent profiles that it fixed both target files, but a full-tree `diff -rq` against an unfixed baseline also showed `template/.github/workflows/process-health-labels.yml.jinja` corrupted: `trim_blocks` ate the newline after an inline `{% endraw %}` at end-of-line, gluing `GH_TOKEN: ${{ github.token }}` and `REPOSITORY: ${{ github.repository }}` onto one invalid line. Reverted the `copier.yml` change entirely before writing the per-file fix that shipped.

## Success evidence review

- "A managed project's `git diff --cached --check` no longer fails on these two files" — verified directly: `copier copy --trust --defaults --vcs-ref HEAD` renders (workflow_profile in {light, standard, multi-agent} x harness_mode in {platform, project}, and operator_config_path both set and unset for `task-intake.md.jinja`'s two branches), followed by `git init` + `git add -A` + `git diff --cached --check -- .gitlab-ci.yml docs/engineering/task-intake.md` on each rendered tree: exit 0 in every combination.
- "No other rendered file changes" — full-tree `diff -rq` between a HEAD render and a parent-commit render (same `--data` flags) shows exactly the two target files differ, each losing only the intended stray blank line(s); `.github/workflows/process-health-labels.yml` is byte-identical between the two renders.
- "Full platform test suite passes unchanged" — `python3 scripts/run_test_groups.py --all`: 1140/1140, unchanged from before this fix.

## Spec-delta scenario review (`specs/project-factory/spec.md` in this change)

- "A control tag closes a template file" — covered directly by both fixed files: `{% endif -%}` is the literal last line of each, confirmed by reading the full file content (not just the diff hunk), with nothing meaningful after it except the file's own trailing newline.
- "Whitespace-control trimming never corrupts inline expressions" — this change itself is the positive example: the global-envops path was tried, found to corrupt `process-health-labels.yml.jinja`'s inline `{% raw %}` usage, and was reverted in favor of the per-file fix that shipped, exactly as the scenario requires.

## Independent review

A native Claude executor (general-purpose subagent) independently read the proposal/design/spec and the full diff, then did NOT trust the design doc's claims and instead ran its own real verification: 4 fresh `copier copy` renders at HEAD and 4 at the parent commit (via a temporary `git worktree add --detach`) crossing harness_mode/operator_config_path, byte-inspected file tails, ran its own `git diff --cached --check` (exit 0 all 4), full-tree-diffed parent-vs-fixed renders (only the two target files differ in all 4 combinations, `process-health-labels.yml` byte-identical), and ran `tests/test_template_contract.py` (41 passed). It reported no blockers and three nits, all addressed or acknowledged here:

- `design.md` described the `task-intake.md.jinja` fix in a way that reads as if only the else-branch needed the second `{% endif -%}` trim, when in fact the unconditional post-`{% endif %}` newline is emitted for whichever branch renders. Reworded `design.md` to state this applies to both branches.
- The review's own Copier install (9.17.1) is a patch version newer than the exact version this platform pins (9.17.0, per `docs/release-policy.md`). Noted as acceptable: `keep_trailing_newline`/`trim_blocks`/`lstrip_blocks` semantics are stable core Jinja/Copier behavior unlikely to differ across a patch version, and this is the same version already installed and exercised by this repository's own test suite and prior managed-task work in this environment.
- The spec's second scenario ("never rely on environment-wide trimming without auditing raw/inline-tag usage") is a process constraint rather than a runtime-observable behavior with no automated check enforcing it. Confirmed this matches an established, pre-existing pattern in this repo's own specs (`platform-lifecycle`, `worktree-coordination`, `platform-ci`, `ci-safety`, `agent-runtime` all use similar "SHALL NOT rely on X unless Y" phrasing); no change made, since it is consistent with house style rather than a deviation from it.

## Tests run

```
python3 -m compileall -q template/scripts scripts
python3 scripts/run_test_groups.py --all            # 13/13 groups passed, 1140 tests
openspec validate fix-rollout-trailing-blank-lines --strict   # valid
python3 -m pytest tests/test_template_contract.py -q          # independent review's own run: 41 passed
```

Plus the real-Copier-render verification described above (not expressible as a single command; see design.md's "Verification performed" section for the exact render/diff/check sequence run before this change was written, independently repeated by the reviewing agent).

No unresolved finding remains.

OpenSpec-Verify: PASS
Verification-Method: manual-semantic-review (opsx:verify unavailable in this environment)
Automated-Checks-Evidence: automated-checks.json
