# Non-Functional Testing Checklist

Non-functional requirements define how well the system must behave under expected and adverse conditions.

## Performance and Reliability

- Response time target for UI, API, batch, and integration workflows.
- Throughput, volume, and peak-load expectations.
- Timeout thresholds and retry behavior.
- Degraded-mode or manual fallback behavior when dependent systems fail.
- Idempotency and duplicate submission handling for retryable operations.

## Security and Compliance

- Authentication and authorization expectations.
- Role-based access rules.
- Sensitive data masking for patient, provider, payer, and account data.
- Audit logging for create, update, delete, approval, override, and exception decisions.
- Data retention, privacy, and compliance expectations.

## Usability and Operations

- Clear user-facing error, warning, and confirmation messages.
- Accessibility or localization needs when applicable.
- Monitoring, alerting, and support diagnostics.
- Deployment, rollback, feature flag, and configuration requirements.
