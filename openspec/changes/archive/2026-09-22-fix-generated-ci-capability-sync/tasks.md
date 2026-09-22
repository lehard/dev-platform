# Tasks

## 1. Fix
- [x] `template/.github/workflows/dev-platform.yml.jinja`: add "Materialize selected capability surfaces" step before "Validate platform contract".

## 2. Verify
- [x] Real `copier copy` render with capabilities enabled: `platform_doctor.py` fails before the fix, passes after.
- [x] `git check-ignore` confirms materialized surfaces stay untracked.
- [x] Full-tree diff against the unfixed parent shows exactly the one new step, in exactly one file.
- [x] New regression tests in `tests/test_capability_manager.py` and `tests/test_template_contract.py`.
- [x] Full platform test suite green.
