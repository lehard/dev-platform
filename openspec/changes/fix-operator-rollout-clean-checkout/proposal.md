# Proposal: Fix clean-checkout operator rollout

## Why

The v1.5.7 managed rollout correctly selects the generic operator integration but writes its Copier answer before running `copier update`. Copier rejects a dirty destination, so all three selected projects fail before any candidate PR is made.

## What changes

Provide the selected answer through Copier's supported render-data interface for both the normal update and the guarded-recopy fallback. The resulting answer file remains authored by Copier; rollout must not pre-mutate the downstream checkout.

## Non-goals

This does not alter operator identities, external configuration resolution, registry selection, default-off behavior, or rollout's review-only merge policy.
