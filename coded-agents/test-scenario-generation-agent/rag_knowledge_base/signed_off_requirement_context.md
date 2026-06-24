# Signed-off Requirement Context

This local context describes the minimum signed-off information expected before final test scenario generation.

## Readiness Rule

Final executable test cases should be generated only when the requirement is Ready and the QA Lead decision is Approve. If the requirement is Not Ready, Needs Changes, Reject, or Rejected, return blocked status with missing information required before generation.

## Required Requirement Inputs

- requirementId
- requirementTitle
- requirementDescription
- acceptanceCriteria
- requirementAnalysis
- qaLeadReview
- testingScope
- suggestedTestFocus
- identifiedGaps

## Signed-off Context Usage

- Use requirementId for traceability.
- Use requirementTitle and requirementDescription to determine the workflow under test.
- Use acceptanceCriteria to identify expected behavior, validation rules, warnings, confirmations, persistence, audit, performance, and integration expectations.
- Use requirementAnalysis to include known risks, dependencies, assumptions, gaps, and readiness.
- Use qaLeadReview to include approval decision, coverage focus, risk comments, and required changes.
- Use testingScope and suggestedTestFocus to choose scenario categories and prioritize high-risk coverage.

## Blocked Output Rule

When blocked, do not generate final executable test cases. Return:

- generationStatus: Blocked
- testScenarios: empty list
- missingInformation: specific missing or unresolved items
- blockedReason: concise explanation
- ragSourcesUsed: local knowledge sources used during analysis
