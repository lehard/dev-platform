# Design

Generated `.github/workflows/ci.yml` will run `scripts/select_checks.py` locally with SHA-pinned `actions/checkout` and `actions/setup-python` instead of calling a private cross-repository reusable workflow.

The scripts and workflow remain platform-owned Copier files. Therefore CI changes still arrive only in reviewed template updates and remain versioned with the project. Existing `platform_ci_ref` stays in schema v2 for backward compatibility but is not required by the v1.0.1 generated CI caller.

This removes the private Actions Access prerequisite while preserving project-owned heavy QA pipelines as separate gates.
