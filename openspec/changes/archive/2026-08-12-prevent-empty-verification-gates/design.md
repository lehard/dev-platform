## Context

The platform already separates `harness_mode=platform` from `harness_mode=project`. The defect is narrower: in platform-owned mode an empty command list can be indistinguishable from a successfully completed check group, so a truthful receipt may still create false confidence.

## Decisions

### Make emptiness a first-class result

Check selection/execution should return enough structured state to distinguish: commands selected and passed; commands selected and failed; no applicable group; applicable group misconfigured as empty. Do not rely on human interpretation of an empty stdout stream.

### Fail closed only where Dev Platform owns the check contract

For `harness_mode=platform`, an applicable required group with zero commands is a platform/project configuration defect and blocks verification. For `harness_mode=project`, repository-owned CI remains authoritative and the platform does not impose its selector semantics.

### Do not build a semantic test-quality grader

The platform can prove that commands existed and ran, and can identify obvious category mismatches such as compilation-only evidence where reviewed configuration expects tests. It cannot prove test adequacy generically. Avoid AI scoring, coverage percentages or framework-specific policy in this change.

## Risks / Trade-offs

- Over-broad stack detection could create false blockers; use reviewed configuration and already reliable stack signals, with fail-closed behavior only when applicability is established.
- Existing repositories with accidentally empty groups may become blocked until their project-owned check configuration is corrected; that is intentional for platform-owned harnesses because the current state is false assurance.
