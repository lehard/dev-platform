# Design: Hermetic claim fixture

The two focused tests patch `execute_requirement.locked_json` with a test-local context manager that loads the board JSON and writes it after the body exits. This exercises `_release_ready_claim`'s identity and dirty-worktree logic without invoking unrelated shared-group initialization on a temporary directory. Other tests continue covering the actual shared JSON lock and ownership rules.
