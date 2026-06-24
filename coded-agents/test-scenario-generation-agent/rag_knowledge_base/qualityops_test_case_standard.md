# QualityOps Test Case Standard

QualityOps test cases must be clear, specific, traceable, and executable.

## Required Scenario Fields

- testCaseId: stable identifier such as TS-001.
- title: concise and scenario-specific.
- objective: one clear objective.
- testType: functional, negative, boundary, integration, regression, audit, performance, or error handling.
- priority and risk: derived from requirement risk, clinical/business impact, and QA Lead feedback.
- traceability: requirement ID and covered acceptance criteria.
- preconditions: exact state required before execution.
- testData: concrete patient, eligibility, appointment, API, role, and boundary data.
- steps: numbered, concrete, and executable.
- expectedResult: specific, measurable system behavior.
- coverageReason: why the case is included.
- automationCandidate: true when stable and repeatable.
- negativeScenario: true when validating blocked, failed, invalid, or warning behavior.

## Writing Rules

- Use one clear objective per test case.
- Include specific preconditions, not generic environment statements.
- Include specific test data values or data categories.
- Use clear numbered steps with named pages such as Patient Registration, Eligibility Verification, Scheduler, and Audit History.
- Expected results must describe observable behavior and data persistence.
- Never use generic expected results such as "feature behaves as expected", "works correctly", "requirement is satisfied", or "all acceptance criteria pass".
- Every test case must trace to a requirement ID and acceptance criteria.

## Coverage Rules

- Include positive happy path coverage.
- Include at least two mandatory field validation cases when patient registration or appointment creation is in scope.
- Include negative, boundary, integration, regression, audit, performance, and error handling cases where relevant.
- Include duplicate patient validation when demographic matching is part of the workflow.
- Include downstream API unavailable, timeout, and failure behavior when eligibility or scheduling depends on external services.

## Title Rules

- Do not repeat the requirement title prefix.
- Do not generate duplicate words such as "Validate Validate".
- Prefer concise scenario-specific titles such as:
  - Create patient and appointment successfully with active eligibility
  - Validate mandatory patient demographic fields during registration
  - Display duplicate patient warning for matching name and DOB
  - Prevent appointment save when provider or location is missing
  - Show eligibility timeout warning and prevent unsafe continuation
  - Verify audit trail after patient and appointment creation
