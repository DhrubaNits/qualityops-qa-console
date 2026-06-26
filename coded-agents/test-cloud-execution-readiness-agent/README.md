# QualityOps Test Cloud Execution Readiness Agent

The **QualityOps Test Cloud Execution Readiness Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to determine whether a requirement is ready for UiPath Test Manager / Test Cloud execution.

This agent acts as a readiness gate before test execution. It checks whether the required QA workflow steps are completed, recommends the correct test set, selects an execution mode, identifies the first tests to run, and returns blocked reasons when execution should not proceed.

---

## Purpose

In real QA delivery, test execution should not start just because test scenarios exist. Before triggering execution, the QA lead needs to know whether the workflow is ready.

The purpose of this agent is to answer:

* Has the QA lead approved the requirement or scenarios?
* Have test scenarios been generated?
* Have Azure DevOps test cases been created?
* Has risk-based execution planning been completed?
* Which test set should be used?
* Should execution be manual, automated, or mixed?
* Which tests should run first?
* Is anything blocking Test Cloud execution?

This makes execution planning safer, more governed, and more aligned with release quality.

---

## Position in the QualityOps Workflow

```text
Requirement Analysis
        ↓
Human Review and Approval
        ↓
Test Scenario Generation
        ↓
ADO Test Case Creation
        ↓
Risk-Based Test Planning
        ↓
Test Cloud Execution Readiness Agent
        ↓
UiPath Test Manager / Test Cloud Execution
        ↓
Test Result Analysis and Triage
```

This agent runs after risk-based planning and before test execution or Test Manager/Test Cloud execution decisions.

---

## What This Agent Does

The Test Cloud Execution Readiness Agent performs the following actions:

1. Receives workflow readiness inputs as JSON.
2. Validates the input payload.
3. Validates the requirement ID.
4. Checks whether QA lead approval is completed.
5. Checks whether test scenarios were generated.
6. Checks whether Azure DevOps test cases were created.
7. Checks whether risk-based planning is completed.
8. Blocks execution when required workflow steps are missing.
9. Selects a recommended test set.
10. Selects an execution mode.
11. Selects the first tests to run.
12. Returns a recommended next action.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent / coded function
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Coded App integration
* UiPath Test Manager / Test Cloud readiness gating
* Structured input and output schema
* Deterministic decision logic for governed execution readiness

The agent is called from the QualityOps QA Console and runs as part of the UiPath-governed agentic testing workflow.

---

## Why Rule-Based Logic Is Used

Execution readiness should be consistent and explainable.

This agent uses deterministic rule-based logic so the QA lead can clearly understand why execution is ready or blocked.

This helps make the workflow:

* Predictable
* Auditable
* Stable
* Easy to explain
* Easy to extend
* Suitable for enterprise QA governance

---

## Inputs

This agent accepts one input field named `question`.

The `question` value should be a JSON string.

### Expected fields inside `question`

| Field                       | Required | Description                                      |
| --------------------------- | -------- | ------------------------------------------------ |
| `requirementId`             | Yes      | Source requirement or work item ID               |
| `qaReviewStatus`            | Yes      | QA review status, expected value is Approved     |
| `testScenarioCount`         | Yes      | Number of generated test scenarios               |
| `adoTestCaseCreatedCount`   | Yes      | Number of created Azure DevOps test cases        |
| `riskPlanningStatus`        | Yes      | Risk planner status, expected value is Completed |
| `riskLevel`                 | No       | Requirement risk level                           |
| `coverageSummary`           | No       | Scenario coverage summary from risk planner      |
| `recommendedExecutionOrder` | No       | Ordered scenario list from risk planner          |

---

## Example Input

```json
{
  "requirementId": "514",
  "qaReviewStatus": "Approved",
  "testScenarioCount": 8,
  "adoTestCaseCreatedCount": 8,
  "riskPlanningStatus": "Completed",
  "riskLevel": "High",
  "coverageSummary": {
    "functional": 2,
    "negative": 3,
    "integration": 1,
    "regression": 1,
    "edgeCase": 1,
    "total": 8
  },
  "recommendedExecutionOrder": [
    {
      "rank": 1,
      "scenarioId": "TS-002",
      "scenarioTitle": "Validate mandatory patient demographic fields",
      "priority": "High",
      "testType": "Negative"
    },
    {
      "rank": 2,
      "scenarioId": "TS-001",
      "scenarioTitle": "Create patient and appointment successfully",
      "priority": "High",
      "testType": "Functional"
    }
  ]
}
```

---

## Outputs

The agent returns structured output.

| Output                     | Description                   |
| -------------------------- | ----------------------------- |
| `readinessStatus`          | Completed or Failed           |
| `requirementId`            | Source requirement ID         |
| `executionReadinessStatus` | Ready or Not Ready            |
| `recommendedTestSet`       | Recommended test set or suite |
| `executionMode`            | Recommended execution mode    |
| `testsToRunFirst`          | First tests to execute        |
| `blockedReasons`           | Reasons execution is blocked  |
| `nextAction`               | Recommended next step         |

---

## Example Ready Output

```json
{
  "readinessStatus": "Completed",
  "requirementId": "514",
  "executionReadinessStatus": "Ready",
  "recommendedTestSet": "High Risk Functional + Integration Suite",
  "executionMode": "Manual + Automated",
  "testsToRunFirst": [
    {
      "rank": 1,
      "scenarioId": "TS-002",
      "scenarioTitle": "Validate mandatory patient demographic fields",
      "priority": "High",
      "testType": "Negative"
    }
  ],
  "blockedReasons": [],
  "nextAction": "Trigger high-risk functional and integration tests in UiPath Test Cloud."
}
```

---

## Example Blocked Output

```json
{
  "readinessStatus": "Completed",
  "requirementId": "514",
  "executionReadinessStatus": "Not Ready",
  "recommendedTestSet": "",
  "executionMode": "",
  "testsToRunFirst": [],
  "blockedReasons": [
    "QA Lead approval is required before execution.",
    "ADO test cases have not been created."
  ],
  "nextAction": "Complete the blocked items before triggering Test Cloud execution."
}
```

---

## Readiness Checks

Execution is blocked when any of the following conditions are true:

| Check                                       | Blocked Reason                                                   |
| ------------------------------------------- | ---------------------------------------------------------------- |
| QA review is not Approved                   | QA Lead approval is required before execution                    |
| Test scenario count is 0 or missing         | Test scenarios have not been generated                           |
| ADO test case created count is 0 or missing | ADO test cases have not been created                             |
| Risk planning status is not Completed       | Risk-based execution planning must be completed before execution |

This ensures that Test Cloud execution is triggered only after required QA workflow steps are completed.

---

## Test Set Selection Logic

The agent recommends a test set based on risk level and coverage summary.

| Condition                                                | Recommended Test Set                     |
| -------------------------------------------------------- | ---------------------------------------- |
| High risk + functional + integration + negative coverage | High Risk Functional + Integration Suite |
| Regression coverage is majority of total coverage        | Regression Suite                         |
| Edge-case coverage is majority of total coverage         | Exploratory / Edge Case Suite            |
| Default condition                                        | Standard QA Validation Suite             |

---

## Execution Mode Selection

The agent recommends execution mode based on risk level.

| Risk Level       | Execution Mode        |
| ---------------- | --------------------- |
| High             | Manual + Automated    |
| Medium           | Automated + QA Review |
| Low              | Automated             |
| Unknown or other | Automated + QA Review |

This supports a practical combination of human judgment and automation execution.

---

## Tests to Run First

The agent selects the first tests to run from the risk planner output.

Selection rules:

* Prefer high-priority scenarios.
* Select up to 5 scenarios.
* If fewer than 3 high-priority scenarios exist, fill from the remaining ordered scenarios.
* Preserve key metadata such as rank, scenario ID, title, priority, and test type.

This gives the QA lead a focused execution starting point.

---

## Error Handling

The agent handles common failure scenarios, including:

* Invalid JSON input
* Input not being a JSON object
* Missing requirement ID
* Missing workflow readiness data
* Blocked workflow state

When invalid input is received, the agent returns:

*
