# QualityOps Risk-Based Test Planner Agent

The **QualityOps Risk-Based Test Planner Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to prioritize generated test scenarios based on risk, priority, test type, testing scope, and suggested QA focus areas.

This agent helps QA teams decide which tests should be executed first before release validation.

---

## Purpose

After test scenarios are generated and approved, QA teams still need to decide the right execution order.

In real projects, not every test has the same urgency. High-risk, business-critical, integration-heavy, negative, and regression scenarios should usually be executed before lower-risk checks.

The purpose of this agent is to create a risk-based execution plan that helps the QA lead answer:

* Which test scenarios should run first?
* Which scenarios cover the highest risk?
* Are functional, negative, integration, and regression areas covered?
* What is the recommended execution order?
* What release recommendation should QA follow before sign-off?

---

## Position in the QualityOps Workflow

```text
Test Scenario Generation Agent
        ↓
QA Lead Scenario Review
        ↓
ADO Test Case WriteBack Agent
        ↓
Risk-Based Test Planner Agent
        ↓
UiPath Test Manager / Test Cloud Sync
        ↓
Automation Mapping
        ↓
Test Execution / Result Analysis
```

This agent runs after scenarios are generated and approved, and before execution planning or Test Manager sync.

---

## What This Agent Does

The Risk-Based Test Planner Agent performs the following actions:

1. Receives generated test scenarios as JSON.
2. Validates the requirement ID.
3. Validates that test scenarios are present.
4. Validates that each scenario has required fields.
5. Normalizes test types and testing scope.
6. Scores each scenario using deterministic rules.
7. Sorts scenarios into recommended execution order.
8. Creates a coverage summary.
9. Generates a release execution recommendation.
10. Returns structured planning output to the QualityOps QA Console.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent / coded function
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Coded App integration
* Structured input and output schema
* Deterministic decision logic for governed QA execution planning

The agent is called from the QualityOps QA Console and runs as part of the UiPath-governed agentic testing workflow.

---

## Why Rule-Based Logic Is Used

This agent intentionally uses deterministic rule-based scoring instead of relying only on LLM reasoning.

Risk-based execution order should be:

* Explainable
* Repeatable
* Auditable
* Easy to tune
* Stable across repeated runs

This makes the planner more practical for enterprise QA teams, because the QA lead can understand why one test is ranked above another.

---

## Inputs

This agent accepts one input field named `question`.

The `question` value should be a JSON string.

### Required fields inside `question`

| Field           | Required | Description                           |
| --------------- | -------- | ------------------------------------- |
| `requirementId` | Yes      | Source requirement or work item ID    |
| `testScenarios` | Yes      | Generated and approved test scenarios |

### Optional fields inside `question`

| Field                | Required | Description                                                   |
| -------------------- | -------- | ------------------------------------------------------------- |
| `riskLevel`          | No       | Requirement-level risk such as Critical, High, Medium, or Low |
| `testingScope`       | No       | Testing scope recommended by requirement analysis             |
| `suggestedTestFocus` | No       | Suggested focus areas from requirement analysis               |

---

## Example Input

```json
{
  "requirementId": "514",
  "riskLevel": "High",
  "testingScope": [
    "Functional",
    "Integration",
    "Regression",
    "Negative"
  ],
  "suggestedTestFocus": [
    "patient registration",
    "eligibility verification",
    "appointment scheduling",
    "audit"
  ],
  "testScenarios": [
    {
      "scenarioId": "TS-001",
      "scenarioTitle": "Create patient and appointment successfully",
      "priority": "High",
      "testType": "Functional",
      "steps": [
        "Login as clinic staff user.",
        "Create patient record.",
        "Schedule appointment."
      ]
    },
    {
      "scenarioId": "TS-002",
      "scenarioTitle": "Validate mandatory patient demographic fields",
      "priority": "High",
      "testType": "Negative",
      "steps": [
        "Leave mandatory fields blank.",
        "Try to save the patient record."
      ]
    }
  ]
}
```

---

## Outputs

The agent returns structured output.

| Output                      | Description                       |
| --------------------------- | --------------------------------- |
| `planningStatus`            | Completed or Failed               |
| `requirementId`             | Source requirement ID             |
| `recommendedExecutionOrder` | Ranked scenario execution order   |
| `coverageSummary`           | Count of scenario types covered   |
| `releaseRecommendation`     | Recommended QA execution guidance |
| `failedScenarios`           | Validation failures, if any       |

---

## Recommended Execution Order

Each recommended scenario includes:

| Field           | Description                    |
| --------------- | ------------------------------ |
| `rank`          | Execution rank                 |
| `scenarioId`    | Scenario ID                    |
| `scenarioTitle` | Scenario title                 |
| `priority`      | Scenario priority              |
| `testType`      | Scenario test type             |
| `executionType` | Recommended execution category |
| `riskReason`    | Explanation for ranking        |

Example:

```json
{
  "rank": 1,
  "scenarioId": "TS-002",
  "scenarioTitle": "Validate mandatory patient demographic fields",
  "priority": "High",
  "testType": "Negative",
  "executionType": "Manual + Negative",
  "riskReason": "Covers high-risk requirement; prioritizes negative validation."
}
```

---

## Coverage Summary

The agent counts generated scenarios by test type.

Coverage summary includes:

| Field         | Description                |
| ------------- | -------------------------- |
| `functional`  | Functional scenario count  |
| `negative`    | Negative scenario count    |
| `integration` | Integration scenario count |
| `regression`  | Regression scenario count  |
| `edgeCase`    | Edge-case scenario count   |
| `total`       | Total scenario count       |

Example:

```json
{
  "functional": 2,
  "negative": 3,
  "integration": 1,
  "regression": 1,
  "edgeCase": 0,
  "total": 7
}
```

---

## Scoring Logic

The agent calculates scenario score using multiple factors.

### Requirement Risk Score

| Risk Level | Score |
| ---------- | ----- |
| Critical   | 50    |
| High       | 40    |
| Medium     | 25    |
| Low        | 10    |

### Scenario Priority Score

| Priority | Score |
| -------- | ----- |
| Critical | 40    |
| High     | 30    |
| Medium   | 20    |
| Low      | 10    |

### Test Type Score

| Test Type   | Score |
| ----------- | ----- |
| Negative    | 35    |
| Functional  | 30    |
| Integration | 28    |
| Regression  | 24    |
| Edge Case   | 18    |

Additional score is added when:

* Test type is part of the recommended testing scope.
* Requirement risk is Critical or High.
* Scenario is functional, integration, regression, or negative.
* Scenario title mentions negative coverage.
* Scenario title or steps match suggested test focus terms.

This scoring approach makes the execution order explainable and easy to tune.

---

## Execution Type Mapping

The agent recommends execution type based on test type and testing scope.

Examples:

| Test Type   | Execution Type       |
| ----------- | -------------------- |
| Regression  | Manual + Regression  |
| Integration | Manual + Integration |
| Negative    | Manual + Negative    |
| Functional  | Manual               |

This can later be extended to include automation readiness and UiPath Test Manager execution labels.

---

## Release Recommendation

The agent generates a release recommendation based on risk and available scenario coverage.

Example recommendations:

```text
Run high-risk functional, integration, and negative tests first before regression execution.
```

```text
Run high-risk functional and integration tests first before regression execution.
```

```text
Run the recommended order and confirm coverage gaps before release sign-off.
```

This gives QA leads a clear execution strategy before moving toward release readiness.

---

## Error Handling

The agent handles common failure scenarios, including:

* Invalid JSON input
* Missing requirement ID
* Missing test scenarios
* Empty test scenario list
* Scenario that is not an object
* Missing scenario ID
* Missing scenario title
* Missing test type

When validation fails, the agent returns `planningStatus` as `Failed` and includes details in `failedScenarios`.

---

## Security Notes

This agent does not require external credentials or secrets.

Security rules:

* Do not commit `.env`.
* Do not include confidential customer data in sample payloads.
* Do not expose private tenant-specific values.
* Keep sample data generic and demo-safe.

---

## Files in This Agent

Typical files in this folder:

```text
main.py
entry-points.json
bindings.json
langgraph.json
project.uiproj
pyproject.toml
uipath.json
README.md
```

### `main.py`

Contains the coded implementation for:

* Input parsing
* Scenario validation
* Test type normalization
* Scope normalization
* Scenario scoring
* Scenario ranking
* Coverage summary generation
* Release recommendation generation
* Structured output generation

### `entry-points.json`

Defines the UiPath coded function entry point, input schema, output schema, and execution graph.

---

## Role in QualityOps QA Console

This agent helps QualityOps move from generated test cases to intelligent execution planning.

It ensures that QA execution is not random or only based on manual judgment. Instead, execution order is guided by risk, scenario priority, testing scope, and coverage needs.

This improves:

* Release confidence
* QA prioritization
* High-risk coverage
* Test planning consistency
* Execution transparency
* Decision explainability

---

## Responsibility Separation

This agent is intentionally separate from test scenario generation and execution readiness.

| Agent                          | Responsibility                     |
| ------------------------------ | ---------------------------------- |
| Test Scenario Generation Agent | Generates candidate test scenarios |
| Test Case Review Memory Agent  | Stores QA approval decisions       |
| ADO Test Case WriteBack Agent  | Creates approved test cases        |
| Risk-Based Test Planner Agent  | Ranks scenarios for execution      |

This separation keeps the QualityOps workflow modular, explainable, and easier to extend.

---

## Production Extension Ideas

This agent can be extended further with:

* Automation coverage weighting
* Historical defect weighting
* Flaky test risk weighting
* Test execution duration estimation
* Business-critical module weighting
* Release confidence scoring
* Dynamic regression selection
* Test Manager execution set creation
* CI/CD trigger integration
* Environment readiness dependency checks

---

## Summary

The Quality
