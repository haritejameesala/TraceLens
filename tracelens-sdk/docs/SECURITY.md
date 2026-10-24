# Security and privacy guidance

- Do not commit `.env`, credentials, tokens, certificates, or production trace exports.
- Use `strict=True` when trace delivery is a requirement; use `strict=False` only when application continuity is more important than guaranteed telemetry delivery.
- Redaction is best effort and cannot identify every secret or personal-data format. Use allowlisted metadata and avoid raw user content.
- Restrict backend network access to trusted applications. The current SDK/backend integration does not itself establish tenant authorization or API-key authentication; do not expose the backend publicly without adding and validating an authentication layer.
- Tracebacks contain file paths and function names. Review whether these are acceptable for your deployment before storing them.
- Configure retention and access controls for trace data in the deployment environment.
- Report security issues privately to the project maintainers.
