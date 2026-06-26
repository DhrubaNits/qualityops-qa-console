# QualityOps Test Case Review Memory Agent

The **QualityOps Test Case Review Memory Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to store, load, and update QA review decisions for generated test scenarios.

This agent uses **UiPath Data Service** as review memory so that QA lead decisions are traceable, reusable, and auditable across the end-to-end testing workflow.

---

## Purpose

After the Test Scenario Generation Agent creates scenarios, the QA lead reviews them before test cases are created in Azure DevOps or synced into UiPath Test Manager.

The purpose of this agent is to persist those review decisions so the workflow can remember:

* Which scenarios were approved
* Which scenarios were rejected
* Who reviewed them
* When they were reviewed
* What comments were provided
* Which Azure DevOps test cases were later created from approved scenarios

This helps QualityOps maintain human-in-the-loop governance across the QA workflow.

---

## Position in the QualityOps Workflow

```text
Test Scenario Generation Agent
        ↓
QA Lead Scenario Review
        ↓
Test Case Review Memory Agent
        ↓
Azure DevOps Test Case WriteBack Agent
        ↓
Risk-Based Test Planner Agent
        ↓
UiPath Test Manager / Test Cloud Sync
```

This agent sits between scenario generation and downstream test case creation.

It ensures that only reviewed and approved scenarios continue into the rest of the workflow.

---

## What This Agent Does

The Test Case Review Memory Agent supports three main operations:

1. `SAVE_REVIEW_MEMORY`
2. `LOAD_REVIEW_MEMORY`
3. `UPDATE_ADO_CREATION_RESULT`

These operations allow the QualityOps QA Console to save scenario review decisions, reload previously reviewed scenarios, and update memory records after Azure DevOps test cases are created.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Data Service
* UiPath Coded App integration
* Structured input and output schemas
* Governed review-memory persistence

The agent is called from the QualityOps QA Console and runs as a managed UiPath Orchestrator job.

---

## UiPath Data Service Usage

This agent stores review memory in a UiPath Data Service entity.

Default entity name:

```text
QATestReviewMemory
```

The entity name can be overridden using the environment variable:

```text
QUALITYOPS_REVIEW_MEMORY_ENTITY_NAME
```

This makes the agent configurable for different tenants, folders, or demo environments.

---

## Data Service Fields

The agent expects review-memory records to use fields such as:

| Field                  | Description                                |
| ---------------------- | ------------------------------------------ |
| `RequirementId`        | Source requirement/work item ID            |
| `ScenarioKey`          | Unique scenario key or scenario ID         |
| `ScenarioTitle`        | Scenario title                             |
| `ReviewStatus`         | Approved, Rejected, or other review status |
| `ReviewComment`        | QA lead comment                            |
| `ReviewedBy`           | Reviewer name or email                     |
| `ReviewedAt`           | Review timestamp                           |
| `ScenarioJson`         | Full scenario JSON                         |
| `StepsJson`            | Serialized scenario steps                  |
| `CreatedAdoTestCaseId` | Azure DevOps test case ID created later    |
| `CreatedAdoUrl`        | Azure DevOps test case URL created later   |
| `Source`               | Source system, usually QualityOps          |
| `UpdatedAt`            | Last updated timestamp                     |

---

## Supported Operations

## 1. SAVE_REVIEW_MEMORY

This operation saves or updates QA review memory for generated test scenarios.

If a record already exists for the same `RequirementId` and `ScenarioKey`, the agent updates it. Otherwise, it creates a new record.

### Example Input

```json
{
  "operation": "SAVE_REVIEW_MEMORY",
  "requirementId": "514",
  "scenarios": [
    {
      "scenarioKey": "TS-001",
      "scenarioTitle": "Create patient and appointment successfully",
      "reviewStatus": "Approved",
      "reviewComment": "Approved for test case creation.",
      "reviewedBy": "QA Lead",
      "steps": [
        "Login as clinic staff user.",
        "Create patient record.",
        "Schedule appointment."
      ],
      "source": "QualityOps"
    }
  ]
}
```

### Example Output

```json
{
  "status": "Success",
  "operation": "SAVE_REVIEW_MEMORY",
  "message": "Processed 1 scenario(s): 1 created, 0 updated, 0 failed.",
  "createdCount": 1,
  "updatedCount": 0,
  "failedCount": 0,
  "entityName": "QATestReviewMemory",
  "requirementId": "514",
  "records": [],
  "failures": []
}
```

---

## 2. LOAD_REVIEW_MEMORY

This operation loads all saved review-memory records for a requirement.

It is used when the QualityOps QA Console needs to restore previous review decisions.

### Example Input

```json
{
  "operation": "LOAD_REVIEW_MEMORY",
  "requirementId": "514"
}
```

### Example Output

```json
{
  "status": "Success",
  "operation": "LOAD_REVIEW_MEMORY",
  "message": "Loaded 3 review memory record(s).",
  "createdCount": 0,
  "updatedCount": 0,
  "failedCount": 0,
  "entityName": "QATestReviewMemory",
  "requirementId": "514",
  "records": [],
  "failures": []
}
```

---

## 3. UPDATE_ADO_CREATION_RESULT

This operation updates saved review-memory records after approved scenarios are converted into Azure DevOps test cases.

It stores the created Azure DevOps test case ID and URL against the matching scenario memory record.

### Example Input

```json
{
  "operation": "UPDATE_ADO_CREATION_RESULT",
  "requirementId": "514",
  "createdTestCases": [
    {
      "scenarioKey": "TS-001",
      "adoTestCaseId": "1001",
      "adoUrl": "https://dev.azure.com/example/project/_workitems/edit/1001"
    }
  ]
}
```

### Example Output

```json
{
  "status": "Success",
  "operation": "UPDATE_ADO_CREATION_RESULT",
  "message": "Processed 1 created test case result(s): 1 updated, 0 failed.",
  "updatedCount": 1,
  "failedCount": 0,
  "entityName": "QATestReviewMemory",
  "requirementId": "514",
  "records": [],
  "failures": []
}
```

---

## Inputs

This agent accepts one input field named `question`.

The `question` value should be a JSON string.

| Field              | Required            | Description                                    |
| ------------------ | ------------------- | ---------------------------------------------- |
| `operation`        | Yes                 | Operation to perform                           |
| `requirementId`    | Yes                 | Requirement/work item ID                       |
| `scenarios`        | Required for save   | Scenario review records to save                |
| `createdTestCases` | Required for update | Azure DevOps test case creation result records |

Supported operations:

```text
SAVE_REVIEW_MEMORY
LOAD_REVIEW_MEMORY
UPDATE_ADO_CREATION_RESULT
```

---

## Outputs

The agent returns structured output.

| Output                | Description                         |
| --------------------- | ----------------------------------- |
| `status`              | Success, Failed, or PartialSuccess  |
| `operation`           | Operation performed                 |
| `message`             | Human-readable result message       |
| `createdCount`        | Number of records created           |
| `updatedCount`        | Number of records updated           |
| `failedCount`         | Number of failed records            |
| `entityName`          | Data Service entity name used       |
| `dataServicePathUsed` | Data Service API path used          |
| `requirementId`       | Requirement/work item ID            |
| `records`             | Created, updated, or loaded records |
| `failures`            | Failure details, if any             |

---

## Error Handling

The agent handles common failure scenarios, including:

* Invalid JSON input
* Missing operation
* Unsupported operation
* Missing requirement ID
* Missing or invalid scenarios list
* Missing or invalid created test cases list
* Missing scenario key
* No memory record found for update
* Data Service entity name mismatch
* Data Service permission or folder access issues
* Unexpected runtime errors

When errors occur, the agent returns structured failure details instead of failing silently.

---

## Data Service Entity Name Troubleshooting

If the configured entity name is incorrect, the agent returns a readable error message explaining that the entity name was not accepted by UiPath Data Service.

Common checks:

* Use the Data Service entity **Name**, not only the Display Name.
* Confirm the process runs in the same folder or has permission.
* Confirm the entity exists in the expected tenant.
* Confirm the configured entity name matches the field structure expected by the agent.

---

## Security Notes

This agent does not require Azure DevOps PAT access directly. It works with UiPath Data Service.

Security rules:

* Do not commit `.env`.
* Do not commit tenant secrets.
* Do not commit Data Service credentials.
* Do not store confidential customer data in sample payloads.
* Store only the review memory required for QA traceability.
* Avoid logging sensitive scenario data unnecessarily.

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

* Operation routing
* Data Service path construction
* Data Service query
* Record insert
* Record update
* Save review memory
* Load review memory
* Update Azure DevOps creation results
* Structured response generation

### `entry-points.json`

Defines the UiPath agent entry point, input schema, output schema, and execution graph.

---

## Role in QualityOps QA Console

This agent supports the review governance layer of QualityOps.

It ensures that generated test scenarios are not treated as final automatically. Instead, QA lead review decisions are stored and used by downstream agents.

This improves:

* Human-in-the-loop control
* Review traceability
* Auditability
* Test case creation governance
* Repeatable QA workflow execution

---

## Responsibility Separation

This agent is intentionally separate from the Test Scenario Generation Agent and Azure DevOps Test Case WriteBack Agent.

| Agent                          | Responsibility                              |
| ------------------------------ | ------------------------------------------- |
| Test Scenario Generation Agent | Generates candidate test scenarios          |
| Test Case Review Memory Agent  | Stores QA review decisions                  |
| ADO Test Case WriteBack Agent  | Creates approved test cases in Azure DevOps |

This separation keeps the workflow easier to govern, debug, and extend.

---

## Production Extension Ideas

This agent can be extended further with:

* Reviewer role validation
* Review timestamp normalization by user timezone
* Scenario versioning
* Scenario diff tracking
* Approval history timeline
* Integration with UiPath Action Center
* Support for bulk approval and bulk rejection
* Data Service audit dashboard
* Advanced reporting of approval rate and rejection reasons

---

## Summary

The QualityOps Test Case Review Memory Agent stores QA review memory in UiPath Data Service.

It helps QualityOps QA Console keep human review decisions traceable, auditable, and reusable before approved scenarios move into Azure DevOps test case creation and UiPath Test Manager / Test Cloud workflows.
