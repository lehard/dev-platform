# Design

A repository-owned setup entrypoint checks workflow enablement and Actions secret metadata with GitHub CLI. Because secret values are unreadable by design, an explicit Actions workflow performs the authenticated provider probe using the secret and reports only success or a bounded setup error. Keep the check separate from ordinary CI/release gates. Avoid printing response bodies or credentials.

Risk: an API probe costs a request and may reveal error details. Bound the request, strip response content, and report only status categories.
