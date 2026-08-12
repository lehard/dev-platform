## Why

Source backlog issue: `lehard/development-backlog#14`
Prepared against: `lehard/dev-platform@3c970b815b92f0711d85957a263330b8ecd9d439`

Process evidence in `lehard/dev-platform#39` showed a truthful `OpenSpec-Verify: PASS` while important frontend routes were non-functional because the platform-owned check mapping resolved relevant frontend work to no commands and Python work to byte-compilation only. The lifecycle did not fabricate evidence; it lacked a distinction between "checks executed successfully" and "there were effectively no product checks to execute".

## What Changes

- Make platform-owned check selection/reporting expose whether applicable commands were actually selected and executed.
- Treat an applicable platform-managed check group that resolves to zero commands as a configuration blocker, not a silent success.
- Keep project-owned harnesses project-owned: the platform does not invent or duplicate product CI for `harness_mode=project`.
- Make verification evidence state what actually ran and prevent an automated-check claim when no such checks executed.
- Add a regression fixture for the false-PASS class from `dev-platform#39`.

## Capabilities

### Modified Capabilities

- `project-factory`: generated platform-owned check contracts must be diagnosably non-empty for applicable scopes.
- `completion-lifecycle`: semantic verification/archive evidence must distinguish successful executed checks from absent automated coverage.
