## Decisions

- **Evidence.** Process liveness is observed with `lsof -d cwd`, filtered to the assigned worktree, excluding the caller's ancestry. This works for records written before this change, which hold no pid. A missing or failing `lsof` blocks; there is no weaker proof.
- **History.** The delegation stays in the record, closed with `outcome: abandoned`, `closed_at`, `task_content_post` and an `abandonment` object. No execution evidence is created, so nothing claims the child finished.
- **Rerouting.** A new route supersedes an abandoned one the same way a not-launched attempt does. Task content left by the dead child is reported at closure and remains ordinary uncommitted or committed task content for the next writer.
