# Tasks

## 1. Ownership model

- [x] Add downstream project-owned files to Copier `_skip_if_exists`.
- [x] Document the ownership boundary for adoption and rollout.

## 2. Version coherence

- [x] Make `platform_bootstrap.py` synchronize `.dev-platform.toml` from Copier `_commit`.
- [x] Make managed rollout validate `_commit` against `platform_version`.

## 3. Project-specific doctor requirements

- [x] Add `project_required_files` configuration support.
- [x] Cover the behavior with tests.

## 4. Regression coverage

- [x] Extend Copier upgrade smoke to prove project-owned files survive.
- [x] Run Platform CI for all profiles and strict OpenSpec validation.

## 5. Completion

- [x] Perform semantic OpenSpec verification, resolve findings, record PASS, archive, and publish through the normal platform release flow.
