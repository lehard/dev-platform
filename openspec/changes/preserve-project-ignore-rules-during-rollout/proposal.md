# Proposal: Preserve project-owned ignore rules during Copier rollout

## Why

A managed Copier rollout removed project-owned `.gitignore` entries in Cuby and exposed more than 10,000 existing runtime, database and credential-adjacent files to source control. The downstream project restored the rules, but the platform still lacks a preservation boundary and a fail-closed check for this class of regression.

## What Changes

- Establish an explicit ownership/preservation contract for `.gitignore` across new renders and Copier updates.
- Preserve project-owned ignore extensions while allowing a bounded platform baseline.
- Add rollout validation that detects loss of effective ignore coverage for representative secret/runtime artifact classes before publication.
- Add regression coverage based on the observed Cuby failure mode.

## Impact

This changes platform rollout safety and template/update behavior for every managed repository. It must be delivered through the normal release lifecycle and validated against representative downstream fixtures.
