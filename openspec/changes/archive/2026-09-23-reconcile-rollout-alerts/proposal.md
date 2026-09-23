# Proposal: Reconcile stale rollout alerts

## Why

The failure tracker closes only when the next automated rollout preparation succeeds. A manually recovered project can leave an alert open indefinitely.

## What changes

Add a bounded reconciliation command that compares an open failure issue with the target project's actual platform version/recovery evidence and closes it only when recovery is proven. Run it on a periodic operator maintenance schedule, independent of a later rollout or stale-PR apply action.

## Non-goals

No independent alert database and no automatic modification of downstream projects.
