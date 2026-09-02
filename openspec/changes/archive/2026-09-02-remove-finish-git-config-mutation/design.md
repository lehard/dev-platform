# Design: Verify on finish, repair deliberately

## Decisions

1. Bootstrap/adoption remains responsible for initial shared-repository configuration.
2. Ordinary lifecycle preflight reads `core.sharedRepository` and does not rewrite a correct value.
3. A required repair uses the existing integration serialization and is rechecked after mutation.
4. Audit retries only the disappearing ephemeral-path observation; it does not suppress durable findings.
5. No new lock service or repository-wide finish serialization is introduced.
