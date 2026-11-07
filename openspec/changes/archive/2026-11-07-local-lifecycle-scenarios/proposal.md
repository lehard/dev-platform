## Why

Two breakages of the simple delivery path were fixed without a test that would catch them again. The reconcile conflict hint once stopped at "resolve and commit" and left a declared generated file to be guessed; its fix was proven only by a manual local probe, and the unit test checks the hint text with the generated-file declaration mocked. A new test file without a group was visible only in CI after a full local finish; the fix is one configuration line in `dev-platform/checks.toml` that nothing pins.

## What Changes

- A test on local Git (a temporary repository and a bare remote) drives a real reconcile conflict that includes a declared generated file through the real `finish_task.py --reconcile` entrypoint, follows every step of the printed hint literally and checks the task ends reconciled with its history kept. While the merge is unfinished it checks `--status` answers without a traceback and names reconcile, and a repeated reconcile prints the same steps.
- A test reads the preflight commands this repository configures, runs the cheap project gates with them on a temporary tree and checks a test file without a group stops them naming the file, while a grouped one passes.
- Each test names its source breakage.

## Non-goals

Lifecycle behavior changes, fixes of other defects, sandbox, GitHub or network in tests, scenarios for the removed queue, duplicates of breakages already covered by tests.
