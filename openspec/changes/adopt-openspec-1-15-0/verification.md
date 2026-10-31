OpenSpec-Verify: PASS
Verification-Method: supervisor semantic OpenSpec review (meaning preservation of every split, completeness, coherence) of the 4 spec deltas, proposal, design and tasks; a mechanical split check per spec; `openspec validate <change> --strict` on 1.13.2 and on an isolated 1.15.0; an archive simulation of this change on a copy of `openspec/` followed by `openspec validate --all --strict` on 1.15.0; the exact-CLI regression suite on 1.15.0 and 1.13.2; the project harness adoption smoke and template contract tests with 1.15.0 on PATH; repository-owned selected checks recorded by the lifecycle
Automated-Checks-Evidence: automated-checks.json
Independent-Review-Evidence: independent-review-request.json

## Decisions

- Split (DEC-0007 procedure): 47 long requirements of lifecycle-workers (21), publication-queue (18) and chat-coordinator (8) became 47 MODIFIED (header and every scenario byte-equal to main, description cut to one behavior) and 175 ADDED requirements with their own scenarios. Edits beyond splitting: pronouns replaced by their noun phrase, subjects and inherited conditions repeated where the original sentence sat under them, sentences over 500 cut at a clause boundary (hosted preflight list, sandboxed writer profile at its semicolons, the generated-files merge/push sentence). Ambiguous phrases kept verbatim.
- Version: 1.15.0 (owner choice). npm `latest` is 1.16.0 (2026-10-30), which needs Node 22.12+ for npm installs (CI pins Node 20.19.0) and adds a strict scenario-step check; not adopted here.
- Pins moved together: `template/.dev-platform.toml.jinja`, `.github/workflows/ci.yml` (validate and regression), `lifecycle-workers.yml`, `adopt-project.yml`, `template/.github/workflows/dev-platform.yml.jinja`, README, `tests/test_template_contract.py`, `tests/project_harness_adoption_smoke.py`. This task worktree's own untracked `.dev-platform.toml` copy was moved to 1.15.0 so the central-config pin test runs; the integration root's copy and the machine's global CLI are operator steps after merge.
- No exemption: platform CI keeps `openspec validate --all --strict`; openspec-authoring states the limit is enforced without a filter.
- Handed off with the change active (BR-940); finalize archives.

## Completeness

- `openspec validate --all --strict` on 1.15.0 after the simulated archive: 51 passed, 0 failed.
- Regression suite: new `check_requirement_length_and_dropped_text` (500 passes strict; 501 passes normal and fails strict; prose above the first section and an extra `## Notes` section are warned about by name and fail strict) passes on 1.15.0 and fails on 1.13.2 ("strict validation accepted an ADDED requirement over 500 characters"); the 1.13.x fixtures pass unchanged on 1.15.0.
- Adoption smoke with the new pin: "Project-owned mature multi-agent adoption acceptance passed". Rollback: reverting this change restores every 1.13.2 pin; the split specs stay valid on 1.13.2.

## Not verified / limits

- The 1.14.2 symlink and 1.14.3 glob-containment fixes and the 1.14.2/1.15.0 verify-workflow REMOVED fixes are not pinned by new fixtures: the platform uses no symlinked OpenSpec layout or glob artifacts, and the verify workflow is advisory (platform archive gates stay authoritative).
- Local runs on the machine's 1.13.2 still pass because 1.13.2 does not check length; CI runs the pinned 1.15.0.
- Downstream projects with long requirements fail `--strict` after their next update; not measured here (updating projects is out of scope).
