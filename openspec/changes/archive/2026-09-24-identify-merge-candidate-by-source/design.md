# Design: Exact-source namespace

Derive the new `generation` in `requirement_merge_recovery.assemble` from bounded prefixes of `base` and `source_head`, retaining the manifest digest over full SHA values. `_slug` uses that generation unchanged, so branch, worktree and committed manifest names differ when source changes. Existing committed manifests keep their own generation and remain valid for publication/reconciliation; prepare and finalization still reject occupied exact names and changed child evidence. Add tests for different source heads and identical-source collision.
