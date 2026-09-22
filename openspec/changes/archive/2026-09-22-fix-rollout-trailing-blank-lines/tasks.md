# Tasks

## 1. Fix
- [x] `template/.gitlab-ci.yml.jinja`: trim the final `{% endif %}` to `{% endif -%}`.
- [x] `template/docs/engineering/task-intake.md.jinja`: remove the two stray literal blank lines before `{% else %}`/`{% endif %}`; trim the final `{% endif %}` to `{% endif -%}`.

## 2. Verify
- [x] Render both files (all relevant branches) with real Copier and confirm `git diff --cached --check` passes.
- [x] Full-tree diff a fixed render against an unfixed baseline; confirm only the two target files change, by exactly the intended blank line(s).
- [x] Full platform test suite green.
