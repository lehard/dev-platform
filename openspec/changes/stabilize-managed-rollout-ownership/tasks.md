# Tasks

## 1. Ownership model

- [ ] Add downstream project-owned files to Copier `_skip_if_exists`.
- [ ] Document the ownership boundary for adoption and rollout.

## 2. Version coherence

- [ ] Make `platform_bootstrap.py` synchronize `.dev-platform.toml` from Copier `_commit`.
- [ ] Make managed rollout validate `_commit` against `platform_version`.

## 3. Project-specific doctor requirements

- [ ] Add `project_required_files` configuration support.
- [ ] Cover the behavior with tests.

## 4. Regression coverage

- [ ] Extend Copier upgrade smoke to prove project-owned files survive.
- [ ] Run Platform CI for all profiles and strict OpenSpec validation.

## 5. Completion

- [ ] Perform semantic OpenSpec verification, resolve findings, record PASS, archive, and publish through the normal platform release flow.
