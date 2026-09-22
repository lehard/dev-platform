# Proposal: Make Requirement pre-authoring proportional

## Why

The current Requirement-first flow assumes full snapshot, ADD, and intent decomposition even when the Requirement has a deterministic or bounded answer. That makes routine work ceremonious and leaves no durable explanation of why a stage was skipped or which existing routing tier governs it.

## What changes

- Classify a complete Requirement and scoped evidence into deterministic, bounded-evidence, or material-design paths.
- Reuse fresh scoped projections and record an explicit skip receipt when ADD/intents are unnecessary.
- Bind every non-deterministic stage to the existing provider-neutral routing policy: routine/read-only extraction for bounded evidence and R2 design work only when a material delta remains.

## Success evidence

- Regression coverage proves deterministic and bounded paths avoid unnecessary semantic work.
- A fresh matching projection is reused and an explicit skip is resumable.
- Routing records no new provider-specific contract and escalates only for existing hard triggers.

## Constraints and non-goals

The Requirement remains the business source of truth. This change composes with the complete-context binding and must not recreate #158's contract alignment or #154/#156's downstream rollout.
