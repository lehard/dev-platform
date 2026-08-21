# Tasks

## 1. Specify the shared profile contract

- [x] 1.1 Identify the template-owned start API consumed by managed intake and make its standard-profile behavior explicit.
- [x] 1.2 Define parent-only standard routing separately from delegated child-writer containment.

## 2. Implement compatible lifecycle behavior

- [x] 2.1 Move or preserve the callable standard task-start contract at the shared/template boundary.
- [x] 2.2 Ensure routing preflight records a standalone standard task clone without weakening child-writer validation.

## 3. Add release-grade verification

- [x] 3.1 Add deterministic light/standard/multi-agent profile contract tests, including managed-start composition.
- [x] 3.2 Add rendered/adopted downstream standard-profile canary coverage to the platform release or rollout validation path.
- [x] 3.3 Verify a downstream update can remove only the superseded compatibility code without changing project-owned behavior.

## 4. Verify and deliver

- [x] 4.1 Run template-render, shared-script, profile-matrix and CI validation; document downstream compatibility evidence.
- [x] 4.2 Perform semantic completeness/correctness/coherence review, record actual verification, archive via lifecycle helper, and publish a protected PR.
