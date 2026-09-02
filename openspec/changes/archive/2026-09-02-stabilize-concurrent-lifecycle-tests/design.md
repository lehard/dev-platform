# Design: Synchronize facts, not wall-clock guesses

## Decisions

1. A fixture signals readiness only after the descendant identity required by the assertion exists.
2. Timeout measurement begins after readiness, with a separate bounded readiness deadline.
3. Publication recovery tests share one configurable timeout and emit retained process diagnostics on expiry.
4. Automatic group concurrency is capped at a small host-independent maximum; explicit operator configuration still wins.
5. Failed tests are not automatically retried.
