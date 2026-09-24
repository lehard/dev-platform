# Design: Explicit shared publication identity

The publisher receives `--shared-manifest` only from a shared-candidate entrypoint. It requires a clean candidate, a repository-relative manifest under the canonical integration directory committed at exact HEAD, a content-valid Requirement identity, at least two distinct children, and reciprocal parent/child links. A missing or malformed manifest fails before push or PR mutation. The ordinary managed path remains unchanged.

With valid shared evidence, the publisher skips only its single-Issue `In review` Project update. The parent remains In progress while the protected PR is open; the existing exact merged-PR reconciler changes children and parent to Done after local main synchronization. It does not bypass required checks or merge guard.
