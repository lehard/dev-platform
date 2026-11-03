## 1. Implementation
- [x] 1.1 Implement the pre-write complete serialized size check and explicit error, with a proven Issue-number bound and no arbitrary reserve.
- [x] 1.2 Preserve the successful path and existing format; regenerate platform manifest if required.

## 2. Verification
- [x] 2.1 Stubbed regression tests for exact estimated limit, limit plus one, comfortably fitting packages and no writes on rejection, for ASCII and non-ASCII; prove the Issue-number bound and boundary-zone behavior.
- [x] 2.2 Run relevant checks, semantic OpenSpec verification and record coordinator decision plus live-test omission and GitHub-limit residual risk in verification.md.
