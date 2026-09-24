# Verification: private-platform-health-review

OpenSpec-Verify: PASS

Verification-Method: manual semantic review of the authored outcome, success evidence, completeness, correctness, and coherence; local automated gates and live private GitHub Actions runs

Automated-Checks-Evidence: automated-checks.json

Requirement-Integration-Exception: Requirement #194 has exactly one technical child (#195), so a shared multi-child integration candidate cannot be assembled; publish this verified child through its exact managed PR.

## Outcome and cloud evidence

- The private caller's missing-access run published a private `degraded` report, with `private_evidence: degraded`, an unavailable-evidence category, and both AI reviews skipped: [private report #204](https://github.com/lehard/development-backlog/issues/204). The private report replaced its predecessor on later runs.
- After GitHub App installation permission approval, [private run 35993638802](https://github.com/lehard/development-backlog/actions/runs/35993638802) completed successfully. Preflight, both review agents, safe outputs, and the publisher succeeded. [Private combined report #210](https://github.com/lehard/development-backlog/issues/210) records `audit_status: complete` and `private_evidence: available`, and links the private process and architecture reports #209 and #208. The process report cites private managed evidence.
- The public repository received no new combined or individual report from that run. Historical public reports #99, #100 and #101 were closed; #100's old body, which mentioned private issue identifiers, was replaced with a brief migration notice.

## Automated checks

- `python3 -m compileall -q template/scripts scripts`: passed.
- `python3 scripts/managed_projects.py validate`: passed, 3 managed projects.
- `python3 scripts/run_test_groups.py --all`: all 13 groups and all 1282 discovered tests passed.
- `python3 template/scripts/openspec_lifecycle.py check`: passed.
- `openspec validate private-platform-health-review --strict --no-interactive`: passed.
- `python3 scripts/validate_agentic_workflows.py`: all three gh-aw sources compiled and matched their lock files at the pinned gh-aw version 0.88.8. The existing process triage concurrency warning did not fail validation.
- [Public PR #111 validation run](https://github.com/lehard/dev-platform/actions/runs/35993560306): passed, including the public distribution audit and snapshot smoke.

## Semantic OpenSpec review

- **Outcome and success evidence:** The combined schedule/dispatch and report publisher live in the private caller. Live degraded and full runs exercise both branches of the specified behavior. The full run produced one open combined private report; the prior same-prefix report was closed.
- **Completeness:** The public source contains reusable workflow logic and deterministic helpers, but no private repository identity or private task findings. The private caller pins those workflows to an immutable commit. Operator setup, degraded behavior, test coverage, and report placement are covered.
- **Correctness:** The process token is a short-lived GitHub App installation token restricted to the public platform and private caller with Contents, Issues and Pull requests read; the architecture token has public platform Contents read. The private caller's `GITHUB_TOKEN` writes reports. The publisher rejects a destination other than the private caller and checks the repository is private. gh-aw prompt imports are inlined in reusable locks so activation works in the private caller checkout; the first full run exposed and the later successful run verified this correction.
- **Coherence:** The proposal, design, specification delta, implementation, tests, and live behavior agree on private-only complete output, explicit degraded mode, and independent review sections. No separate public full report or storage path remains active.

The automated-checks marker above names the evidence that the archive helper will generate from its own selected checks; it does not assert that the evidence file existed before archive.
