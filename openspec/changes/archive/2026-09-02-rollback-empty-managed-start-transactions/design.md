# Design: Prove emptiness before rollback

## Decisions

1. Transaction creation remains early enough to protect real partial starts.
2. Exception cleanup deletes the exact transaction only when worktree, branch and board identity are all absent.
3. Retry performs the same exact-identity emptiness proof before replacing a stale package revision.
4. Any observed side effect delegates to the existing conservative recovery path.
5. No global scan, guessed ownership or sibling cleanup is allowed.
