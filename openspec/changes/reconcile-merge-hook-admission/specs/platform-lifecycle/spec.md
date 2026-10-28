## ADDED Requirements

### Requirement: Task reconcile passes the platform merge-commit hook

Where the platform `pre-merge-commit` hook is installed, the supported task reconcile SHALL complete its merge of authoritative `origin/<main_branch>` in its own task worktree without a manual override. Before that single merge, reconcile SHALL record a one-shot intent in the task worktree's own git directory naming the task branch and the commit of `origin/<main_branch>`, and SHALL remove it after the merge whatever the outcome. The hook SHALL admit a merge commit only in a linked task worktree whose git directory holds that intent for the current branch, when `GIT_REFLOG_ACTION` is exactly `merge origin/<main_branch>` and `origin/<main_branch>` still points to the recorded commit, and SHALL consume the intent. The hook SHALL keep blocking every other merge commit, including every merge commit in the integration copy, and SHALL NOT be removed or disabled. Reconcile SHALL NOT rebase or force-push.

#### Scenario: Reconcile of a diverged task with the hook installed

- **GIVEN** a task worktree with its own commits, the platform `pre-merge-commit` hook installed, and an advanced `origin/main`
- **WHEN** the supported reconcile runs
- **THEN** it creates the merge commit of `origin/main` without a manual override
- **AND** the task head descends from both the previous task head and `origin/main`
- **AND** no intent remains in the worktree's git directory

#### Scenario: Ad-hoc merge in a task worktree

- **WHEN** a merge commit is attempted in a task worktree without a reconcile intent
- **THEN** the hook rejects it and no merge commit is created

#### Scenario: Intent does not admit another target or worktree

- **GIVEN** a reconcile intent in one task worktree
- **WHEN** a merge of another ref is attempted there, or any merge is attempted in another worktree, or `origin/main` has moved since the intent was recorded
- **THEN** the hook rejects it and no merge commit is created

#### Scenario: Integration copy

- **WHEN** a merge commit is attempted in the integration copy
- **THEN** the hook rejects it whatever intent exists
