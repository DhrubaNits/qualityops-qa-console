# QualityOps Test Scenario Generation Agent

The **QualityOps Test Scenario Generation Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to generate structured QA test scenarios from approved requirement analysis output.

This agent converts QA-approved requirement analysis into meaningful functional, negative, regression, integration, audit, and performance-focused test scenarios. It uses LLM reasoning, QA/RAG knowledge context, test design standards, healthcare workflow checklists, and deterministic fallback logic to produce high-quality test scenarios for downstream review and test case creation.

---

## Purpose

QA teams spend significant time manually converting requirements into test scenarios. This process can be inconsistent, especially when requirements involve complex workflows, integrations, negative scenarios, regression impact, audit expectations, or healthcare-specific validation rules.

The purpose of this agent is to accelerate test design while keeping QA control in the workflow.

It helps generate scenarios that include:

* Clear test objective
* Test type
* Priority
* Risk
* Preconditions
* Test data
* Step-by-step actions
* Specific expected results
* Traceability to the requirement
* Coverage reason
* Automation candidate flag
* Negative scenario flag where applicable

---

## Position in the QualityOps Workflow

```text
Requirement Analysis Agent
        ↓
Human Review and Approval
        ↓
Test Scenario Generation Agent
        ↓
Test Case Review Memory Agent
        ↓
Azure DevOps Test Case WriteBack Agent
        ↓
Risk-Based Test Planner Agent
        ↓
UiPath Test Manager / Test Cloud Sync
```

This agent runs after requirement analysis and QA lead approval.

If the requirement is not ready or the QA lead rejects it, scenario generation can be blocked and missing information is returned.

---

## What This Agent Does

The Test Scenario Generation Agent performs the following actions:

1. Receives approved requirement analysis output as JSON.
2. Parses requirement title, description, acceptance criteria, risk level, testing scope, suggested test focus, identified gaps, and QA lead review details.
3. Checks whether scenario generation should continue or be blocked.
4. Retrieves QA/RAG context from test design knowledge sources.
5. Uses LLM reasoning to generate structured test scenarios.
6. Applies deterministic fallback generation if LLM or vector retrieval is unavailable.
7. Normalizes scenario titles, priorities, steps, expected results, and metadata.
8. Prevents generic expected results.
9. Returns structured JSON output to the QualityOps QA Console.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Coded App integration
* UiPath Context Grounding / Index search support
* Structured input and output schemas
* Governed cloud execution as part of the QualityOps workflow

The agent is called by the QualityOps QA Console and runs as an Orchestrator-managed coded agent job.

---

## RAG and Test Design Knowledge

The agent uses QA/RAG knowledge context to guide test scenario generation.

Knowledge sources include:

* ISO 29119 Test Design Standard
* ISTQB Testing Principles
* QualityOps Test Case Standard
* Healthcare Workflow Test Checklist
* Signed-off Requirement Context

The agent supports UiPath Context Grounding / Index search and also includes a local markdown-based fallback knowledge base for reliable demo execution.

---

## Fast Demo Mode

The implementation includes a fast demo mode for stable hackathon demo execution.

In fast demo mode:

* UiPath Index search can be skipped.
* Local RAG fallback is used.
* Scenario generation remains deterministic and demo-safe.
* The agent still returns RAG source details and structured scenario output.

This allows the demo to remain stable even if vector search or external retrieval is unavailable during judging.

---

## Inputs

This agent accepts one input field named `question`.

The `question` value should be a JSON string containing requirement analysis output.

### Main input fields inside `question`

| Field                    | Required    | Description                                       |
| ------------------------ | ----------- | ------------------------------------------------- |
| `requirementId`          | Recommended | Source requirement/work item ID                   |
| `submittedBy`            | Optional    | User or system submitting the request             |
| `environment`            | Optional    | Target environment                                |
| `requirementTitle`       | Recommended | Requirement title                                 |
| `requirementDescription` | Recommended | Requirement description                           |
| `acceptanceCriteria`     | Recommended | Acceptance criteria                               |
| `riskLevel`              | Optional    | Requirement risk level                            |
| `testingScope`           | Optional    | Recommended testing scope                         |
| `suggestedTestFocus`     | Optional    | Suggested QA focus areas                          |
| `identifiedGaps`         | Optional    | Requirement gaps from analysis                    |
| `requirementAnalysis`    | Optional    | Structured output from Requirement Analysis Agent |
| `qaLeadReview`           | Optional    | Human review and approval details                 |
| `readinessStatus`        | Optional    | Ready, Needs Review, or Not Ready                 |
| `status`                 | Optional    | Workflow status                                   |

---

## Example Input

```json
{
  "requirementId": "514",
  "submittedBy": "QA Lead",
  "environment": "SQA",
  "requirementTitle": "Validate end-to-end patient care workflow",
  "requirementDescription": "Clinic staff should be able to register a patient, verify eligibility, and schedule an appointment.",
  "acceptanceCriteria": [
    "Patient demographic details are mandatory.",
    "Eligibility verification should show active, inactive, or unavailable status.",
    "Appointment should require provider, location, date, time, and appointment type.",
    "Audit history should capture patient and appointment actions."
  ],
  "riskLevel": "High",
  "testingScope": [
    "Functional Testing",
    "Negative Testing",
    "Regression Testing",
    "Integration Testing"
  ],
  "suggestedTestFocus": [
    "Patient registration validation",
    "Eligibility timeout handling",
    "Appointment scheduling validation",
    "Audit history verification"
  ],
  "requirementAnalysis": {
    "readinessStatus": "Ready",
    "riskLevel": "High"
  },
  "qaLeadReview": {
    "decision": "Approved",
    "feedbackText": "Generate scenarios covering happy path, negative validations, integration failures, and audit trail."
  }
}
```

---

## Outputs

The agent returns structured output.

| Output                 | Description                                       |
| ---------------------- | ------------------------------------------------- |
| `generationStatus`     | Completed, Blocked, or Failed                     |
| `testScenarios`        | Generated test scenarios                          |
| `generationMode`       | LLM/RAG or deterministic fallback generation mode |
| `llmGenerationUsed`    | Whether LLM output was used                       |
| `ragSourcesUsed`       | RAG source names used during generation           |
| `retrievedRagContext`  | RAG context and source metadata                   |
| `vectorRagStatus`      | UiPath Index / vector RAG status                  |
| `vectorChunksReturned` | Number of vector chunks returned                  |
| `vectorQueriesTried`   | Vector queries attempted                          |
| `fallbackRagUsed`      | Whether local fallback RAG was used               |
| `missingInformation`   | Missing information when generation is blocked    |
| `blockedReason`        | Reason generation was blocked                     |

---

## Test Scenario Output Structure

Each generated scenario includes:

| Field                 | Description                                                          |
| --------------------- | -------------------------------------------------------------------- |
| `scenarioId`          | Scenario identifier such as TS-001                                   |
| `scenarioTitle`       | Human-readable scenario title                                        |
| `id`                  | UI-compatible scenario identifier                                    |
| `testCaseId`          | Test case identifier                                                 |
| `title`               | Scenario title                                                       |
| `objective`           | Test objective                                                       |
| `priority`            | High, Medium, or Low                                                 |
| `type`                | UI-compatible test type                                              |
| `testType`            | Functional, Negative, Integration, Regression, Audit, or Performance |
| `risk`                | Risk addressed by the scenario                                       |
| `traceability`        | Requirement and acceptance criteria traceability                     |
| `preconditions`       | Required preconditions                                               |
| `testData`            | Specific data required for execution                                 |
| `steps`               | Test execution steps                                                 |
| `expectedResult`      | Specific measurable expected result                                  |
| `coverageReason`      | Why the scenario is included                                         |
| `automationCandidate` | Whether the scenario is suitable for automation                      |
| `negativeScenario`    | Whether it is a negative scenario                                    |

---

## Expected Result Quality Rules

The agent is designed to avoid weak or generic expected results.

It should not produce expected results such as:

```text
Feature behaves as expected
Works correctly
Requirement is satisfied
All acceptance criteria pass
Feature behaves as described
Existing behavior remains stable
```

Expected results should be specific and measurable.

Good expected results should mention details such as:

* Validation message
* Warning message
* Confirmation message
* Saved data
* Eligibility status
* Appointment result
* Audit event
* API timeout behavior
* Blocked or allowed user action
* Data persistence or rollback behavior

---

## Scenario Types Generated

The agent can generate scenarios such as:

* Happy path functional scenarios
* Mandatory field validation scenarios
* Duplicate record validation scenarios
* Eligibility unavailable or timeout scenarios
* Provider/location/date validation scenarios
* Downstream API failure scenarios
* Audit trail verification scenarios
* Regression scenarios
* Performance scenarios when applicable

---

## Generation Blocking Logic

The agent can block scenario generation when the requirement is not ready.

Generation may be blocked when:

* Requirement readiness is marked Not Ready
* QA lead decision is Reject
* QA lead decision is Needs Changes
* Required information is missing
* Requirement is not approved for executable test design

When blocked, the agent returns:

* `generationStatus`
* `missingInformation`
* `blockedReason`

This supports QualityOps human-in-the-loop governance.

---

## Fallback Generation

The agent includes deterministic fallback scenario generation.

Fallback generation is useful when:

* LLM generation times out
* LLM response is invalid
* Vector RAG does not return usable chunks
* Demo mode is enabled
* Stable deterministic output is required for presentation

Fallback scenarios still include:

* Scenario ID
* Title
* Objective
* Test type
* Priority
* Risk
* Preconditions
* Test data
* Steps
* Expected result
* Traceability
* Coverage reason
* Automation candidate flag
* Negative scenario flag

---

## Error Handling

The agent handles common failure conditions, including:

* Invalid JSON input
* Missing requirement context
* Blocked QA review decision
* LLM timeout
* Invalid LLM JSON response
* Generic expected result detection
* UiPath Index search failure
* Local RAG fallback usage
* Unexpected runtime errors

The agent is designed to return structured output instead of failing silently.

---

## Security Notes

The agent should not expose secrets or confidential values.

Rules followed:

* Do not commit `.env`.
* Do not commit PAT tokens.
* Do not commit client secrets.
* Do not expose authorization headers.
* Do not include confidential customer data in sample inputs.
* Keep tenant-specific configuration outside source code.
* Use safe logging and redact sensitive text where needed.

---

## Files in This Agent

Typical files in this folder:

```text
agent.json
entry-points.json
main.py
bindings.json
langgraph.json
pyproject.toml
sample-input.json
test_main.py
rag_knowledge_base/
README.md
```

### `main.py`

Contains the coded implementation for:

* Input parsing
* Requirement payload normalization
* Generation blocking logic
* UiPath Index / Context Grounding retrieval support
* Local RAG fallback retrieval
* LLM prompt construction
* LLM-based scenario generation
* Deterministic fallback generation
* Scenario normalization
* Structured output generation

### `entry-points.json`

Defines the UiPath agent entry point, input schema, output schema, and execution graph.

### `rag_knowledge_base/`

Contains local markdown knowledge sources used for fallback RAG.

### `sample-input.json`

Contains a sample input payload for local testing.

### `test_main.py`

Contains tests or validation helpers for the coded agent.

---

## Role in QualityOps QA Console

This agent is one of the most important agents in the QualityOps workflow.

It converts requirement analysis into actionable test design output.

The generated scenarios are later used by:

* Test Case Review Memory Agent
* Azure DevOps Test Case WriteBack Agent
* Risk-Based Test Planner Agent
* UiPath Test Manager WriteBack Agent
* Automation Link Agent
* Final QA Report Agent

---

## Production Extension Ideas

This agent can be extended further with:

* Fully enabled UiPath Context Grounding retrieval
* More domain-specific test design standards
* Stronger acceptance criteria traceability
* More test type customization
* Configurable number of scenarios
* Project-specific scenario templates
* Automatic automation feasibility scoring
* Deeper historical defect-based scenario generation
* Flaky test risk prediction
* Multi-domain support beyond healthcare
* More advanced negative and boundary value generation

---

## Summary

The QualityOps Test Scenario Generation Agent turns approved requirement analysis into structured, meaningful, and reviewable QA test scenarios.

It combines UiPath Coded Agents, UiPath Automation Cloud, LLM reasoning, RAG knowledge, test design standards, deterministic fallback logic, and human-in-the-loop governance to improve the quality and speed of test scenario creation.
