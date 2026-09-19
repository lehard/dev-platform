# Verification

OpenSpec-Verify: PASS
Verification-Method: Equivalent semantic review because installed OpenSpec CLI 1.8.0 has no `verify` command; reviewed the proposal, design, delta specs, implementation, and checks for outcome fidelity, completeness, correctness, and coherence.
Automated-Checks-Evidence: automated-checks.json

## Semantic review

- **Outcome fidelity:** audit and snapshot share one deterministic candidate set; the public-current-tree and bounded reachable-history gates produce scoped, secret-safe receipts.
- **Completeness:** the implementation covers public distribution, portable versus operator guidance, explicit operator configuration/registry validation, and GitLab exact-head terminal-CI behavior.
- **Correctness:** focused tests cover prohibited candidates, nested machine caches, history credential findings and batching, opt-in isolation, external registry discovery, GitLab success/pending/failure/missing evidence, and no merge operation. The full grouped suite passed.
- **Coherence:** portable Copier renders omit mandatory operator commands while opted-in renders retain managed guidance; current central operator configuration is explicitly enabled but excluded from the public product candidate set.

## Executed evidence

- `python3 -m compileall -q template/scripts scripts`
- `python3 scripts/run_test_groups.py --all` — 889 tests, 13 groups, all successful.
- `python3 scripts/managed_projects.py --registry tests/fixtures/managed-projects.json validate`
- `python3 scripts/public_distribution.py audit`
- `python3 scripts/public_distribution.py history-audit`
- `python3 scripts/public_distribution.py snapshot --output /tmp/dev-platform-119-snapshot.tar`
- `python3 template/scripts/openspec_lifecycle.py check`
- `openspec validate harden-public-distribution-operator-and-gitlab-boundaries --strict`

## Post-archive CI fix

The `validate` GitHub Actions run for this PR failed the `multi-agent` Copier
upgrade smoke check: `template/docs/engineering/agent-workflow.md.jinja` had
gated its entire body behind `operator_config_path`, so a portable (non-operator)
`multi-agent` render silently lost the fail-closed worktree-board guidance
(`unreadable or un-lockable board`) even though that guidance is a profile
capability, not an operator/Development-Backlog concern. Fixed by keeping the
profile-based sections (start of task, shared workspace permissions, worktree
hygiene, provider-local routing, publishing, verification, CI updates,
friction/retrospective, completion) unconditional, and narrowing the
operator-only conditional to just the Development-Backlog-specific task-intake
commands and the `source_issue_drift` publishing clause.

Re-executed evidence after the fix:

- `python3 -m compileall -q template/scripts scripts`
- `python3 -m unittest tests.test_template_contract tests.test_agent_instruction_architecture tests.test_root_guidance_contract` — 55 tests, all successful.
- `python3 tests/upgrade_smoke.py --profile light --publish-mode direct`
- `python3 tests/upgrade_smoke.py --profile standard --publish-mode pr`
- `python3 tests/upgrade_smoke.py --profile multi-agent --publish-mode pr`
- `python3 scripts/run_test_groups.py --all` — 889 tests, 13 groups, all successful.
- `python3 scripts/managed_projects.py --registry tests/fixtures/managed-projects.json validate`
- `python3 template/scripts/openspec_lifecycle.py check`
