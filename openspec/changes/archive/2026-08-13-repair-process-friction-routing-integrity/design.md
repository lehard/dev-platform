# Design: One coherent process-friction source path

## 1. Label at creation

The routing operation owns the `process` label. Creation and update paths verify that the canonical open source issue remains eligible for review.

## 2. Bounded reconciliation

A migration/recovery operation may repair unlabeled issues that are unambiguously platform-generated process-friction records. It is idempotent and does not relabel arbitrary historical issues.

## 3. Durable duplicate discovery

Exact fingerprint matching remains cheap, but discovery scans the complete bounded/paginated open source set rather than one page. Before creating a fresh issue for a new free-form category, the recording path must expose a bounded likely-duplicate decision using existing categories/root-cause evidence. It must prefer an explicit candidate over an unsupported automatic semantic merge.

## 4. Review alignment

The weekly cloud workflow is the routine review mechanism. Local `pending/review` commands remain recovery/diagnostic tools. `agent_doctor` must describe them accordingly rather than producing an implicit per-task assignment.

## 5. No second state machine

GitHub issues, labels, fingerprints and the existing local retry state remain the only process-friction stores.
