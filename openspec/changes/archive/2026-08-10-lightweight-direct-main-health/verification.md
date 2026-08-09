# Verification: keep direct-mode main health lightweight

OpenSpec-Verify: PASS
Verification-Method: semantic completeness/correctness/coherence review plus GitHub Platform CI #235

## Result

- PR events keep selected-check validation for platform-owned harnesses.
- Manual dispatch is the only generated path for full platform-managed checks.
- Direct `main` pushes keep platform doctor, OpenSpec lifecycle hygiene and strict OpenSpec validation without repeating the full project check set.
- This matches the local-heavy/cloud-final cost policy and avoids requiring generic CI to install arbitrary project dependencies.
- Platform CI #235 passed on `dbd2a8ba1653a02d36d8219af34c1e36ee35016a`.

No critical or warning findings remain. Ready for archive and patch release.
