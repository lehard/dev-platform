## Why

BR-799 adopts a current verified OpenSpec stable release with its path-containment, removed-requirement verification and archive content-loss fixes. From 1.14.1 `openspec validate --strict` fails on a requirement description over 500 characters (Fission-AI/OpenSpec#1976, #2020). DEC-0007 records the owner's choice: split our long requirements by the upstream procedure and bump only when `validate --all --strict` is green on the new release. Portions 1–3A split 182 of 229 long requirements; 47 remain in lifecycle-workers, publication-queue and chat-coordinator.

## What Changes

- Split the last 47 long requirements: MODIFIED under the same header with every scenario kept and the description cut to one behavior; each removed behavior ADDED with its own scenario. Meaning does not change.
- Move every recorded copy of the tested OpenSpec version from 1.13.2 to 1.15.0: `template/.dev-platform.toml.jinja` `[tools.openspec]`, `.github/workflows/ci.yml`, `.github/workflows/lifecycle-workers.yml`, `.github/workflows/adopt-project.yml`, `template/.github/workflows/dev-platform.yml.jinja`, README and the test pins.
- Extend `tests/openspec_1_13_regression.py` with fixtures for the 1.14.1 strict length limit (500 passes, 501 fails strict, normal validation passes) and the 1.14.2 warning for delta text that archive drops.
- openspec-authoring: an ADDED requirement that the length limit is enforced without a repository exemption.

## Capabilities

### Modified Capabilities

- `lifecycle-workers`, `publication-queue`, `chat-coordinator`: form only.
- `openspec-authoring`: the length limit is enforced without exemption.

## Impact

CI, the adoption workflow and rendered projects install OpenSpec 1.15.0. Downstream projects get it on their next platform update; a project whose own specs exceed the limit fails `--strict` there and splits them by the same procedure (DEC-0007). Rollback is a revert of this change, which restores the 1.13.2 pins.
