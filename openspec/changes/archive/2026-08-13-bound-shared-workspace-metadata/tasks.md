## 1. Ownership model

- [x] 1.1 Inventory current shared-workspace audit and rendered wrapper traversal paths.
- [x] 1.2 Define the allowlist for platform-owned metadata and the narrowly excluded transient cache pattern.

## 2. Implementation

- [x] 2.1 Bound shared-workspace audit/repair to the allowlist without weakening owned Git/lifecycle checks.
- [x] 2.2 Update rendered group-write verification to ignore only foreign transient cache paths.

## 3. Verification

- [x] 3.1 Add external-symlink and concurrent foreign-cache regression fixtures.
- [x] 3.2 Prove owned permission drift is still reported/repaired.
- [x] 3.3 Run relevant platform tests, strict OpenSpec validation and template/Copier smoke.
