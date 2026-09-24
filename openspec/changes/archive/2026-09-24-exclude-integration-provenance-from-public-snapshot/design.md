# Design: Narrow operator-provenance exclusion

Add the exact directory to `public_distribution.EXCLUDED_PATHS`, alongside existing machine-local config and archived change provenance. The same `public_files` candidate set feeds audit, digest and tar creation, so the exclusion is consistent. A test places a private Backlog reference in a tracked-like integration manifest and verifies it is omitted, while a separate product file with the same reference still triggers the operator-state finding. No scanner predicate or product repository allowlist changes.
