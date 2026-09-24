## Why

The public Platform Health Review cannot read the private Development Backlog, so its process report omits managed work and the combined public report can be mistaken for a complete audit. Granting private access to a public Actions run would expose private data to public run surfaces.

## What Changes

- Move the combined scheduled and manual run to the private Development Backlog. Private evidence, logs, artifacts, and the full report stay there.
- Use a short-lived GitHub App read credential restricted to the required repositories and permission scopes. Use the private run's own narrowly permitted GitHub token to write the private report.
- Remove the public combined report publisher and public schedule. Preserve bounded advisory review behavior and optional notifications only where they are private-safe.
- Explicitly label the result degraded if private evidence is inaccessible. Do not claim a complete audit or publish private details in public fallback output.

## Impact

The private Development Backlog gains the workflow and its GitHub Actions configuration. The platform owns reusable review logic and the contract. Operators must provide the App credentials and OpenAI API key to the private runner; public repository secrets do not transfer across repositories.
