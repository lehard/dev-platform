# Proposal: Classify Platform Health Review findings in Russian

## Why

The current architecture report labels its structural lens and confidence in English and has no lifecycle status. The process report groups issues by work state, but its findings do not share the requested category/confidence/status vocabulary. The combined report links those two outputs. Readers cannot reliably distinguish a defect, risk, simplification, hygiene item, and observation at a glance.

## What Changes

- Define a shared, concise Russian finding vocabulary for the existing review outputs and show a bounded excerpt of those findings in the existing combined report Issue.
- Require a current Backlog and recent merged-change check before either review describes a recommendation as new.
- Keep the architecture evidence lens separate from the primary finding category.
- Preserve the current private combined report, bounded reviews, and advisory/read-only boundary; introduce no score.

## Impact

Only existing Platform Health Review instructions, capability guidance, and the current combined-report publisher are changed. No task creation, new report storage, or review architecture changes.
