# QA Test Design Standard

QA test design should translate requirements into clear, risk-based scenarios that cover functional, integration, data, security, and regression behavior.

## Test Design Inputs

- Requirement title, description, and acceptance criteria.
- Business workflow and impacted modules.
- User roles, permissions, and data ownership.
- API contracts, data mappings, queues, events, files, or integration dependencies.
- Non-functional targets such as performance, timeout, reliability, and auditability.

## Scenario Design Rules

- Include at least one end-to-end happy path for the primary workflow.
- Include negative tests for invalid, missing, duplicate, unauthorized, expired, or inconsistent data.
- Include edge tests for boundary values, special characters, nulls, date ranges, and concurrent updates.
- Include integration tests for request, response, timeout, retry, and downstream failure handling.
- Include regression tests for existing workflows affected by the change.
- Trace every high-priority acceptance criterion to at least one test scenario.

## Output Quality

- Test scenarios must state preconditions, test data, actions, and expected results.
- Expected results must include UI messages, database or API state changes, audit entries, and downstream effects when relevant.
