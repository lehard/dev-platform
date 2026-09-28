# Design: Readiness before bounded timeout

Use the existing `wait_for_readiness` polling helper in the affected test. The child writes a readiness marker only after flushing `partial` to stdout; the parent waits for that marker under the normal bounded startup deadline, then invokes `communicate_within_deadline` under the existing 0.3 second override. The marker is disposable test state.

The marker must be published after the output flush so its existence establishes that the retained output is already available. Keep the post-timeout assertions and cleanup intact. This confines the change to test synchronization and leaves the helper's timeout behavior unchanged.

Delay the controlled child for longer than the short timeout before it flushes output. This makes the original scheduler race reproducible even on an otherwise idle host: starting the 0.3 second deadline at spawn would fail, while starting it after readiness still tests the hang.
