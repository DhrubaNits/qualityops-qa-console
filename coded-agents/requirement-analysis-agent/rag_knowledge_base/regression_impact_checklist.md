# Regression Impact Checklist

Regression impact analysis identifies existing behavior that could break because of a requirement change.

## Impact Areas

- Existing user workflows using the same screens, APIs, data tables, queues, or integrations.
- Shared validation rules, reusable components, feature flags, or configuration.
- Reporting, audit, downstream notification, and data export behavior.
- Role-based access and permission behavior.
- Existing automated tests, manual smoke tests, and production monitoring checks.

## Required Regression Questions

- Which modules and workflows consume the changed data?
- Which existing happy paths must continue to pass?
- Which negative and edge cases were previously supported?
- Are database schema, API contract, event payload, or integration mappings changed?
- Are there backward compatibility, migration, or historical data concerns?
- Are performance, timeout, or retry characteristics affected?

## QA Expectations

- Define a focused regression suite tied to impacted modules.
- Include high-risk patient, provider, scheduling, eligibility, audit, and billing paths when touched.
- Validate unchanged workflows before and after deployment when the change affects shared services.
