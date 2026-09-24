# Proposal: Portable ready-claim tests

## Why

The exact shared Requirement PR #106 failed Linux CI in two tests that put a board JSON file under a private temporary directory. Their purpose is to check claim identity, but the production JSON lock also applies shared-group ownership to that directory; CI cannot chgrp it to root.

## What Changes

Keep production ownership enforcement unchanged. Isolate only the unit fixtures' persistence boundary with a local JSON context manager, preserving claim matching, mutation and refusal assertions. Verify on required Linux CI before merging the shared candidate.
