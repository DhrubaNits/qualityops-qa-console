# ISO 29119 Test Design Standard

Use this guidance to convert a signed-off requirement into traceable test design artifacts.

## Test Condition Identification

- Identify test conditions from each requirement statement, acceptance criterion, business rule, interface dependency, data rule, role, state transition, and error condition.
- Separate conditions for positive behavior, negative behavior, boundary values, integration responses, auditability, and regression impact.
- Make each condition observable. A tester must be able to see a UI message, persisted data value, API response, status change, audit entry, or blocked action.

## Test Case Specification

- Each test case must have one clear objective.
- Link every test case to the requirement ID and acceptance criteria it covers.
- Define preconditions that must be true before execution, including user role, test environment, baseline data, enabled feature flags, and dependent service availability.
- Define specific test data, including valid values, invalid values, duplicate records, boundary values, and downstream service responses.
- Steps must be numbered, concrete, and executable by a tester without guessing the feature area.

## Test Procedure Specification

- Procedure steps must describe exact user or system actions: login role, navigation path, data entry, save action, verification action, and audit/log review.
- Include setup and cleanup needs when data persistence affects later tests.
- Include integration preparation when a downstream API, eligibility service, scheduler service, or audit service must return a controlled response.

## Expected Result Clarity

- Expected results must be specific and measurable.
- State the exact system behavior: record created or not created, field highlighted, warning shown, status displayed, confirmation shown, audit entry written, API failure handled, or retry blocked.
- Avoid generic outcomes such as "works correctly", "feature behaves as expected", "requirement is satisfied", or "all acceptance criteria pass".

## Pass/Fail Criteria

- A test passes only when all expected observable outcomes occur and no forbidden side effects occur.
- A test fails if data is saved when validation should block it, warning or confirmation messages are missing, duplicate records are created unexpectedly, audit entries are missing, or downstream failures are hidden from the user.

## Coverage Balance

- Include positive and negative coverage for every critical requirement.
- Include boundary coverage when field length, date/time, response time, eligibility status, provider availability, or duplicate matching can vary.
- Include integration, regression, audit, and performance coverage where the requirement touches dependent systems or compliance-sensitive workflows.
