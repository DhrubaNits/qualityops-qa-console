# Acceptance Criteria Checklist

Acceptance criteria should be testable, complete, and specific enough to support automation and manual validation.

## Criteria Quality

- Each criterion describes one expected behavior.
- Criteria use concrete inputs, actions, and expected outcomes.
- Criteria avoid vague terms such as fast, correct, proper, seamless, or user-friendly unless measurable.
- Criteria identify who performs the action and where the result is visible.
- Criteria define pass/fail conditions for success, failure, warning, and partial completion.

## Validation Criteria

- Mandatory and optional fields are identified.
- Allowed formats, ranges, and code sets are defined.
- Duplicate detection behavior is explicit, including matching fields, warning text, blocking rules, and available user actions.
- Error messages and recovery steps are specified.
- Permissions and role-specific behavior are covered.

## Scenario Coverage

- Happy path.
- Negative scenarios.
- Boundary and edge cases.
- Data conflict or duplicate scenarios.
- System unavailable, API failure, timeout, and retry scenarios.
- Regression-sensitive scenarios that must continue to work.
