# Tasks

## 1. Fix
- [x] `template/.github/workflows/dev-platform.yml.jinja`: change the `harness_mode == 'platform'` branch's closing `{% else %}` to `{%- else %}`.

## 2. Verify
- [x] Real `copier copy --trust --defaults` render for both `harness_mode` values; `git diff --cached --check` exits 0 for both.
- [x] Full-tree diff against the unfixed parent commit's render shows exactly one line removed, in exactly this file.
- [x] Full platform test suite green.
