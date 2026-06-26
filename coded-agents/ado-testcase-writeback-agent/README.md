# QualityOps ADO Test Case WriteBack Agent

The **QualityOps ADO Test Case WriteBack Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to create Azure DevOps test cases from QA-approved test scenarios.

This agent takes reviewed and approved scenarios from the QualityOps QA Console and writes them into Azure DevOps as formal Test Case work items. It also links the generated test cases back to the source requirement or user story for traceability.

---

## Purpose

After the Test Scenario Generation Agent creates test scenarios, the QA lead reviews and approves the scenarios. Approved scenarios should not remain only inside the QualityOps console. They need to become formal test cases in the team’s test management system.

The purpose of this agent is to convert approved QualityOps scenarios into Azure DevOps Test Case work items.

This helps QA teams maintain:

* Requirement-to-test traceability
* Reusable test case records
* Manual and automation-ready test steps
* Expected result mapping
* Azure DevOps test planning compatibility
* Auditability of generated QA assets

---

## Position in the QualityOps Workflow

```text
Test Scenario Generation Agent
        ↓
QA Lead Scenario Review
        ↓
Test Case Review Memory Agent
        ↓
ADO Test Case WriteBack Agent
        ↓
Risk-Based Test Planner Agent
        ↓
UiPath Test Manager / Test Cloud Sync
```

This agent runs after QA review memory is saved and before risk-based execution planning and Test Manager sync.

---

## What This Agent Does

The ADO Test Case WriteBack Agent performs the following actions:

1. Receives approved test scenarios as a JSON payload.
2. Validates the source requirement ID.
3. Validates that test scenarios are present.
4. Reads Azure DevOps configuration from UiPath Assets or environment variables.
5. Normalizes scenario title, type, priority, preconditions, steps, and expected result.
6. Converts scenario steps into Azure DevOps test step XML.
7. Creates Azure DevOps Test Case work items.
8. Adds QualityOps tags to created test cases.
9. Links each created test case back to the source requirement.
10. Returns created test case IDs and URLs.
11. Returns failed scenario details when a scenario cannot be created.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent / coded function
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Assets for configuration
* UiPath Coded App integration
* Structured input and output schemas
* Governed creation of downstream QA artifacts

The agent is called from the QualityOps QA Console and runs as part of the UiPath-governed QA orchestration workflow.

---

## External Integration

This agent integrates with **Azure DevOps Work Item Tracking APIs**.

It creates Azure DevOps work items of type:

```text
Test Case
```

It writes values into fields such as:

* `System.Title`
* `System.Description`
* `System.Tags`
* `Microsoft.VSTS.Common.Priority`
* `Microsoft.VSTS.TCM.Steps`

It also links the generated Test Case back to the source requirement using an Azure DevOps work item relation.

---

## Configuration

Azure DevOps configuration can be supplied using environment variables or UiPath Assets.

Expected configuration names:

```text
ADO_ORGANIZATION
ADO_PROJECT
ADO_PAT
```

The agent first attempts to read these values from UiPath Assets. If values are not available there, it checks environment variables.

For published cloud execution, UiPath Assets are preferred.

Do not commit real PAT tokens, client secrets, tenant-specific values, or authorization headers.

---

## Inputs

This agent accepts one input field named `question`.

The `question` value should be a JSON string.

### Required fields inside `question`

| Field           | Required | Description                                         |
| --------------- | -------- | --------------------------------------------------- |
| `requirementId` | Yes      | Azure DevOps requirement or user story ID           |
| `testScenarios` | Yes      | Approved test scenarios to create as ADO test cases |

### Optional fields inside `question`

| Field         | Required | Description                                      |
| ------------- | -------- | ------------------------------------------------ |
| `submittedBy` | No       | User or system submitting the write-back request |
| `environment` | No       | Target test environment                          |
| `riskPlan`    | No       | Optional risk-based execution plan metadata      |
| `source`      | No       | Source system or workflow name                   |

---

## Example Input

```json
{
  "requirementId": "514",
  "submittedBy": "QA Lead",
  "environment": "SQA",
  "testScenarios": [
    {
      "scenarioId": "TS-001",
      "scenarioTitle": "Create patient and appointment successfully",
      "testType": "Functional",
      "priority": "High",
      "preconditions": [
        "Clinic staff user exists.",
        "Patient registration module is available."
      ],
      "steps": [
        {
          "action": "Login as clinic staff user.",
          "expectedResult": "Clinic staff dashboard is displayed."
        },
        {
          "action": "Navigate to Patient Registration and enter valid demographic details.",
          "expectedResult": "Patient details are accepted without validation errors."
        },
        {
          "action": "Save the patient record.",
          "expectedResult": "Patient record is created and confirmation message is displayed."
        }
      ],
      "expectedResult": "Patient record and appointment are created successfully with audit history captured."
    }
  ]
}
```

---

## Outputs

The agent returns structured output.

| Output             | Description                                     |
| ------------------ | ----------------------------------------------- |
| `writeBackStatus`  | Completed or Failed                             |
| `requirementId`    | Source requirement ID                           |
| `createdTestCases` | Test cases successfully created in Azure DevOps |
| `failedScenarios`  | Scenarios that could not be created             |

---

## Created Test Case Output

Each created test case includes:

| Field        | Description                       |
| ------------ | --------------------------------- |
| `scenarioId` | Source scenario ID                |
| `testCaseId` | Created Azure DevOps Test Case ID |
| `title`      | Created test case title           |
| `url`        | Azure DevOps work item API URL    |

Example:

```json
{
  "writeBackStatus": "Completed",
  "requirementId": "514",
  "createdTestCases": [
    {
      "scenarioId": "TS-001",
      "testCaseId": 1001,
      "title": "TS-001 - Create patient and appointment successfully",
      "url": "https://dev.azure.com/example/project/_apis/wit/workItems/1001"
    }
  ],
  "failedScenarios": []
}
```

---

## Failed Scenario Output

If one or more scenarios fail, the response includes failure details.

Example:

```json
{
  "writeBackStatus": "Failed",
  "requirementId": "514",
  "createdTestCases": [],
  "failedScenarios": [
    {
      "scenarioId": "TS-002",
      "error": "Azure DevOps API returned HTTP 400: invalid field value."
    }
  ]
}
```

---

## Test Step Mapping

The agent supports both string-based steps and object-based steps.

### Object step format

```json
{
  "action": "Login as clinic staff user.",
  "expectedResult": "Clinic staff dashboard is displayed."
}
```

### String step format

```text
Login as clinic staff user. Expected Result: Clinic staff dashboard is displayed.
```

The agent converts these into Azure DevOps test step XML using:

```text
Microsoft.VSTS.TCM.Steps
```

This allows the generated Azure DevOps test cases to contain proper action and expected result columns.

---

## Test Case Description

The generated test case description includes:

* Source requirement ID
* Submitted by
* Environment
* Preconditions
* Test steps
* Expected result

This gives testers enough context to understand why the test case was created.

---

## Tags

Created Azure DevOps test cases are tagged with:

```text
QualityOps
AI Generated
<Test Type>
```

Example:

```text
QualityOps; AI Generated; Functional
```

These tags help teams search, filter, and report on generated QualityOps test cases.

---

## Requirement Traceability

Each created Azure DevOps test case is linked back to the source requirement using a work item relation.

This supports traceability:

```text
Requirement → Generated Test Case
```

This is important for QA governance, test planning, audit review, and release readiness reporting.

---

## Error Handling

The agent handles common failure scenarios, including:

* Invalid JSON input
* Missing requirement ID
* Missing or empty test scenario list
* Missing Azure DevOps configuration
* Invalid scenario format
* Scenario normalization failure
* Azure DevOps authentication failure
* Azure DevOps API errors
* Network errors
* Unexpected runtime errors

Failed scenarios are returned separately so the workflow can continue reporting which scenarios succeeded and which did not.

---

## Security Notes

This agent integrates with Azure DevOps, so secure configuration is important.

Rules followed:

* Do not commit `.env`.
* Do not commit PAT tokens.
* Do not commit client secrets.
* Do not expose authorization headers.
* Use UiPath Assets for cloud execution.
* Use environment variables only for local testing.
* Do not include confidential customer data in sample payloads.
* Do not log sensitive authorization details.

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
* Azure DevOps configuration resolution
* UiPath Asset reading
* Scenario normalization
* Test step normalization
* Azure DevOps test step XML generation
* Azure DevOps Test Case work item creation
* Requirement-to-test-case linking
* Structured output generation

### `entry-points.json`

Defines the UiPath coded function entry point, input schema, output schema, and execution graph.

---

## Role in QualityOps QA Console

This agent turns approved QualityOps scenarios into real Azure DevOps test cases.

It is a key bridge between AI-assisted test design and enterprise test management.

It improves:

* Traceability
* Test case creation speed
* Test step consistency
* Requirement coverage
* Azure DevOps visibility
* QA governance

---

## Responsibility Separation

This agent is intentionally separate from the scenario generation and review memory agents.

| Agent                          | Responsibility                           |
| ------------------------------ | ---------------------------------------- |
| Test Scenario Generation Agent | Generates candidate test scenarios       |
| Test Case Review Memory Agent  | Stores QA approval decisions             |
| ADO Test Case WriteBack Agent  | Creates approved Azure DevOps test cases |

This separation keeps the QualityOps workflow modular and easier to govern, debug, and extend.

---

## Production Extension Ideas

This agent can be extended further with:

* PartialSuccess status when some scenarios succeed and some fail
* Retry logic for transient Azure DevOps failures
* Test suite linking in Azure DevOps Test Plans
* Test plan and test suite creation
* Duplicate test case detection
* Update existing test cases instead of always creating new ones
* More advanced tag management
* Bidirectional traceability updates
* Data Service audit logging
* Attachment support for generated test evidence

---

## Summary

The QualityOps ADO Test Case WriteBack Agent creates Azure DevOps Test Case work items from QA-approved QualityOps scenarios.

It links generated test cases back to the original requirement, maps action and expected result steps correctly, and helps turn agent-generated test design into governed enterprise QA assets.
