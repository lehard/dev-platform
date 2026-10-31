## Context

Decision: DEC-0007 (`docs/decisions/0007-openspec-requirement-length.md`). The tested-version requirement (openspec-authoring "Every recorded copy of the tested OpenSpec version moves together") and the regression-suite requirement already define what moves and what stays in CI.

## Decisions

- **Version.** 1.15.0, as the owner chose. 1.16.0 (2026-10-30) is the npm `latest` but requires Node 22.12+ for npm installs while CI pins Node 20.19.0, and adds a strict scenario-step check; it is a separate decision.
- **Split.** The same procedure and mechanical guard as portions 1–3A: MODIFIED scenarios byte-equal to main, every description ≤ 500, every ADDED with SHALL/MUST and a scenario, every original word carried over except replaced pronouns and connectives.
- **Regression fixtures.** `check_requirement_length_and_dropped_text` in the exact-CLI suite: an ADDED requirement of exactly 500 characters passes strict, 501 passes normal validation and fails strict; a delta with prose above the first section and an extra `## Notes` section is warned about by name and fails strict. The existing 1.13.x fixtures pass unchanged on 1.15.0. The file name stays (CI and checks reference it); its docstring names the 1.14/1.15 coverage.
- **No exemption.** Platform CI keeps `openspec validate --all --strict` on the pinned release; no filter is added.
- **Operator steps after merge.** The machine's global OpenSpec and the untracked root `.dev-platform.toml` `[tools.openspec]` pin are updated by the coordinator; this change does not touch machine configuration.

## Risks

- Downstream projects with long requirements fail `--strict` after updating; the warning names the fix and DEC-0007 the procedure.
- Local runs on the machine's 1.13.2 still pass (1.13.2 does not check length); CI runs the pinned 1.15.0.
