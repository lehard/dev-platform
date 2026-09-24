# Proposal: Keep shared integration provenance out of public snapshots

## Why

The exact shared #164 PR passes all grouped tests but Linux snapshot smoke rejects a committed integration manifest containing private Development Backlog references. The manifest is operator provenance used for protected reconciliation, not reusable product source.

## What Changes

Exclude only the canonical `dev-platform/requirement-integrations/` directory from the public snapshot and its audit candidate set. Preserve the existing canonical repository allowlist, secret scan, and all product-source coverage.
