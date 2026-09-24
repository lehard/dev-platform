# Proposal: Publish shared Requirement PRs

## Why

The combined #164 PR passed full local checks and was created, but the ordinary publisher stopped because its Project update assumes one changed managed Issue while the candidate has three.

## What Changes

An explicit committed shared-manifest option makes the publisher verify Requirement and child identity and skip single-child Project attribution. It retains protected GitHub checks and merge behavior. The shared integration reconciler alone marks children and parent Done after exact merged-PR proof.
