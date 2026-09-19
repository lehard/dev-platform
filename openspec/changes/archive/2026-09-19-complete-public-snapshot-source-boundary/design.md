# Design: Canonical source snapshot without operator compatibility leakage

## Context

The current snapshot implementation correctly shares one candidate set between audit and packaging, but its boundary is too aggressive for a canonical source repository: it excludes all tests and OpenSpec state even though packaged README and CI depend on them. At the same time, a source file that is included in the snapshot still contains private-project migration logic.

The fix should not turn the snapshot into a bespoke distribution artifact unrelated to the development repository. The new public repository is intended to become the canonical Dev Platform source, so it must remain developable, testable, spec-driven, and releasable from the first fresh-history commit.

## Decisions

1. **Treat the snapshot as canonical source, not runtime packaging.**
   Include product source, docs, tests, release/CI machinery, template, and accepted specs required to develop and verify Dev Platform.

2. **Exclude history rather than verification.**
   Prefer narrowly excluding old maintenance history such as `openspec/changes/archive/` over excluding `tests/` or accepted `openspec/specs/`. Keep OpenSpec configuration required by current lifecycle.

3. **Prove the extracted artifact, not only the source checkout.**
   Add a snapshot smoke that extracts the tarball and validates path/link/CI completeness plus a bounded public verification command set from inside the extracted directory.

4. **Make exclusions contract-driven.**
   Every excluded path must have a product reason. A file cannot be excluded only because sanitizing it is inconvenient if README/CI/spec/release behavior still depends on it.

5. **Extract or eliminate private compatibility shims.**
   The public rollout engine may keep generic migration primitives. Jara/Planner/Cuby-specific constants, hash checks, override source strings, messages, and named functions must leave the public candidate.

6. **Prefer migration over permanent plugin complexity.**
   If a legacy shim is needed only to bring one current private project up to the generic platform contract, prefer a controlled one-time downstream migration. Use an external operator compatibility mechanism only when ongoing compatibility is genuinely needed.

7. **Do not break operator fleet silently.**
   Before deleting each live compatibility path, inspect current operator/downstream evidence sufficiently to decide whether it is obsolete, requires one-time migration, or requires an external operator-owned override. This is bounded compatibility analysis, not a full downstream migration.

8. **Synthetic public tests replace private examples.**
   Generic rollout invariants remain tested using `example-org/example-service`-style fixtures and generic names. Production-specific hashes or override payloads are not copied into fixtures.

9. **Sanitizer has semantic markers in addition to owner/repo matching.**
   Add focused policy/tests for known private compatibility markers in packaged source. Do not attempt a vague natural-language scanner; keep the blocklist/policy explicit and bounded.

10. **Cutover remains later.**
    This task prepares a self-contained sanitized snapshot and evidence. It does not create, rename, or change visibility of GitHub repositories.

## Verification strategy

- Unit tests prove candidate policy keeps tests and accepted specs while excluding only documented history/maintenance paths.
- A snapshot fixture containing CI/README references to missing paths must fail.
- A real snapshot is extracted and runs the bounded public-source smoke from inside the extracted tree.
- Sanitizer tests place project-specific compatibility markers in packaged source and prove they block the snapshot.
- Rollout tests preserve generic behavior with synthetic fixtures after private shims are removed/externalized.
- Existing #119 operator isolation and GitLab exact-head tests remain green.
- Full required repository checks pass on the exact final revision.
