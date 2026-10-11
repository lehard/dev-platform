## Context

Blocking checks today fail in script-specific ways with free-form messages. Some already have a recovery (routing `approve-supervisor-diff`, publication `resume`, `dogfood_task.py reconcile`), others do not. Protected gates (see the change-class contract) must not gain a recovery that lets an agent bypass them.

## Decisions

1. **Three classes.** `platform-defect`: the check is wrong or misapplied; the message says so, points at the hotfix flow when the implementing file is hotfixable and at a platform release/friction report when it is protected. `recoverable`: a legitimate state is blocked and a supported, recorded path exists (command or owner decision). `hard-stop`: no safe exit exists; the catalog carries the justification and the message states that the stop is intentional.
2. **A recovery for a protected gate must itself be a recorded, owner-visible step**, following the `approve-supervisor-diff` pattern, never a flag that skips the check. A gate whose safe recovery cannot be defined is `hard-stop` with the reason (for example worktree isolation of other agents' state).
3. **Catalog is the single source.** One TOML file, no runtime registry or service. A catalog entry names the acceptance tests; a platform test resolves and runs them, so "has recovery" is evidence-backed, not claimed.
4. **Helper does not decide.** The helper only formats and exits; it adds no retry, default or alternate strategy. A missing catalog id is itself a hard error. A missing or malformed catalog raises `BlockingGateCatalogError` instead of the gate's own exception type: the gate still fails loudly and closed, and no default message is substituted.
5. **Mechanical migration, bounded scope.** The inventoried Python gates move onto the helper with identical exit conditions and message text, only the class and recovery lines are added. The shell `pre-merge-commit` hook stays in its own words (`migrated = false`): it cannot call the helper, and editing a git hook is a protected-surface change reserved for an explicit owner decision. Gates whose classification reveals a missing recovery are recorded as follow-up friction items rather than redesigned here.

## Risks and mitigations

- *Migration changes gate behavior.* Mitigation: existing tests for each gate remain; new tests assert unchanged exit conditions plus the added class line.
- *A "recoverable" label tempts a bypass.* Mitigation: negative tests over the protected surface; recoverable entries require a recorded step, reviewed in the catalog PR.
- *Inventory incomplete.* Mitigation: the platform test fails on any helper use with an unknown id and lists uncataloged gates found by a static search for the known failure pattern; completeness is reported, not assumed.
