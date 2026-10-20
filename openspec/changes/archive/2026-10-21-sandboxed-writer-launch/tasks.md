## 1. Launch primitive
- [x] 1.1 Implement profile generation from protected/allowed paths with realpath resolution and pinned runtime version.
- [x] 1.2 Implement the wrapped argv (short srt TMPDIR, inner env, bash -c with shlex.join, CLAUDE_CODE_TMPDIR) and platform/prerequisite refusals.

## 2. Credential scope
- [x] 2.1 Read the token from the operator token_file with explicit refusals; inject only into the writer env; strip it from harness-git and push envs.

## 3. Verification
- [x] 3.1 Unit tests for profile, token scope, argv shape and refusals; document the primitive in model-routing.md.
- [x] 3.2 Run full validation and semantic OpenSpec verification.
