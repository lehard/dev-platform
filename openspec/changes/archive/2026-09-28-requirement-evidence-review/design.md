# Design

Update the source workflow prompt for weekly Process Health Review and its durable engineering contract to read a bounded relevant set of Requirement Issues, their child links, and process issues originating from pre-authoring or the parent retrospective. The process issue remains the durable finding; the Requirement and child linkage provide context for grouping. The compiled lock file is generated from the source workflow using the repository's existing compiler, and representative tests assert the source/compiled prompt retains the required lens.

The review must not infer a clean Requirement from clean children, and it must not count each child as an independent root cause. It cites bounded evidence and checks current state before recommending work. Specialized reviews feed the same friction router; they do not create parallel improvement queues.

## Risks

- Private Backlog content must stay in the private caller and report. The prompt retains the current private execution and read-only constraints.
- Expanded evidence can enlarge the weekly review. Keep the same bounded issue counts and report limits.
