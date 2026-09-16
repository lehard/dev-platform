# Design: Bounded OpenSpec stable-version compatibility bump

## Decisions

1. Treat OpenSpec as an external dependency; do not vendor or fork it.
2. Upgrade only to the current stable release confirmed at execution time; prerelease versions are out of scope.
3. Exercise representative create/materialize/validate/verify/archive behavior before changing the supported version contract.
4. Add controlled cases for duplicate delta sections, retirement/remove behavior, fenced examples, and apply with missing spec deltas because these are the upstream correctness areas motivating the bump.
5. Keep Dev Platform semantic verification and archive evidence authoritative for platform completion; a safer upstream parser does not replace semantic acceptance.
6. If 1.13.0 exposes a compatibility regression, stop with explicit evidence rather than weakening lifecycle invariants to force the bump.
