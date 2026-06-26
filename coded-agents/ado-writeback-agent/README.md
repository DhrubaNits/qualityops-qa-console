# QualityOps ADO WriteBack Agent

The **QualityOps ADO WriteBack Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to write QA lead decisions and review comments back to Azure DevOps.

This agent helps maintain traceability between the QualityOps QA Console and the original Azure DevOps requirement or work item.

---

## Purpose

After the Requirement Analysis Agent analyzes a requirement, the QA lead may approve, reject, or request clarification from the QualityOps QA Console.

The purpose of this agent is to write that QA lead decision back to the related Azure DevOps work item as a structured comment.

This creates an audit trail showing:

* Which requirement was reviewed
* What decision was taken
* Who submitted the decision
* Which environment was selected
* What comment or clarification was provided
* That the update came from QualityOps QA Console

---

## Position in the QualityOps Workflow

```text
Requirement Analysis Agent
        ↓
Human Review and Approval
        ↓
ADO WriteBack Agent
        ↓
Test Scenario Generation Agent
```

This agent is responsible for updating Azure DevOps after the QA lead review step.

It supports the human-in-the-loop governance model of QualityOps by making sure the QA lead decision is captured not only inside the console, but also in the source requirement system.

---

## What This Agent Does

The ADO WriteBack Agent performs the following actions:

1. Receives a JSON payload from the QualityOps QA Console.
2. Parses the payload from the `question` input.
3. Extracts requirement ID, decision type, decision comment, submitted by, and environment.
4. Reads Azure DevOps configuration from input, environment variables, or UiPath Assets.
5. Builds a formatted QualityOps QA lead decision comment.
6. Posts the comment to the Azure DevOps work item.
7. Returns structured output with write-back status and comment details.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Assets for secure configuration
* UiPath Coded App integration
* Structured input and output for governed orchestration

The agent is called from the QualityOps QA Console and runs as a managed UiPath Orchestrator job.

---

## External Integration

This agent integrates with **Azure DevOps Work Item Comments API**.

It posts a comment to the Azure DevOps requirement/work item using the work item ID received from the QualityOps QA Console.

The Azure DevOps comment keeps the requirement review process traceable and visible to delivery teams who work primarily in Azure DevOps.

---

## Configuration

Azure DevOps configuration can be provided in three ways.

### 1. Input payload

The caller may pass:

```text
adoOrg
adoProject
adoPat
```

### 2. Environment variables

For local development:

```text
AZURE_DEVOPS_ORG
AZURE_DEVOPS_PROJECT
AZURE_DEVOPS_PAT
```

### 3. UiPath Orchestrator Assets

For published cloud execution:

```text
AzureDevOps_Org
AzureDevOps_Project
AzureDevOps_PAT
```

The agent checks configuration in this order:

```text
Input payload
→ Environment variables
→ UiPath Assets
```

For production or cloud execution, UiPath Assets are preferred because they keep configuration outside source code.

Do not commit real PAT tokens, client secrets, tenant values, or authorization headers.

---

## Inputs

This agent accepts one input field named `question`.

The `question` value should be a JSON string.

### Required fields inside `question`

| Field             | Required | Description                                                          |
| ----------------- | -------- | -------------------------------------------------------------------- |
| `requirementId`   | Yes      | Azure DevOps requirement/work item ID                                |
| `decisionType`    | No       | QA lead decision, such as Approved, Rejected, or Needs Clarification |
| `decisionComment` | No       | QA lead comment to write back to Azure DevOps                        |
| `submittedBy`     | No       | Name or email of the user submitting the decision                    |
| `environment`     | No       | Target environment selected in the QualityOps QA Console             |

### Optional Azure DevOps configuration fields

| Field        | Required | Description                        |
| ------------ | -------- | ---------------------------------- |
| `adoOrg`     | No       | Azure DevOps organization          |
| `adoProject` | No       | Azure DevOps project               |
| `adoPat`     | No       | Azure DevOps personal access token |

For security, `adoPat` should normally be stored in UiPath Assets instead of being passed directly from the UI.

---

## Example Input

```json
{
  "requirementId": "514",
  "decisionType": "Approved",
  "decisionComment": "Requirement analysis reviewed and approved for test scenario generation.",
  "submittedBy": "QA Lead",
  "environment": "SQA"
}
```

Example input with optional Azure DevOps configuration:

```json
{
  "requirementId": "514",
  "decisionType": "Approved",
  "decisionComment": "Approved for test generation.",
  "submittedBy": "QA Lead",
  "environment": "SQA",
  "adoOrg": "your-org",
  "adoProject": "your-project",
  "adoPat": "your-pat"
}
```

---

## Outputs

The agent returns structured output.

| Output            | Description                                   |
| ----------------- | --------------------------------------------- |
| `writeBackStatus` | Status of the Azure DevOps comment write-back |
| `requirementId`   | Requirement/work item ID that was updated     |
| `decisionType`    | QA lead decision type                         |
| `commentText`     | Formatted comment posted to Azure DevOps      |

---

## Example Output

```json
{
  "writeBackStatus": "Success: Azure DevOps comment added successfully.",
  "requirementId": "514",
  "decisionType": "Approved",
  "commentText": "## QualityOps QA Lead Decision..."
}
```

---

## Comment Format

The agent posts a structured comment to Azure DevOps.

Example comment:

```markdown
## QualityOps QA Lead Decision

**Decision:** Approved

**Requirement ID:** 514

**Submitted By:** QA Lead

**Environment:** SQA

**Comment:** Requirement analysis reviewed and approved for test scenario generation.

---
Updated by QualityOps QA Console.
```

This format makes the decision easy to read directly inside Azure DevOps.

---

## Error Handling

The agent handles common failures, including:

* Invalid JSON input
* Missing requirement ID
* Missing Azure DevOps configuration
* Azure DevOps authentication failure
* Azure DevOps API errors
* Network errors
* Unexpected runtime errors

When an error occurs, the agent returns a structured failure message in `writeBackStatus`.

Example error output:

```json
{
  "writeBackStatus": "Failed: requirementId is mandatory.",
  "requirementId": "",
  "decisionType": "Approved",
  "commentText": ""
}
```

Another example:

```json
{
  "writeBackStatus": "Failed: Azure DevOps configuration is missing. Pass adoOrg, adoProject, adoPat in question JSON or create Orchestrator assets.",
  "requirementId": "514",
  "decisionType": "Approved",
  "commentText": "## QualityOps QA Lead Decision..."
}
```

---

## Security Notes

Security is important because this agent can access Azure DevOps.

Rules followed:

* Do not commit `.env`.
* Do not commit PAT tokens.
* Do not commit client secrets.
* Do not commit tenant-specific values.
* Prefer UiPath Assets for published cloud execution.
* Do not expose authorization headers in logs or outputs.
* Do not include confidential customer data in sample payloads.
* Use placeholder values in documentation and examples.

---

## Files in This Agent

Typical files in this folder:

```text
main.py
entry-points.json
bindings.json
langgraph.json
pyproject.toml
uipath.json
README.md
```

### `main.py`

Contains the coded implementation for:

* JSON payload parsing
* Azure DevOps configuration lookup
* UiPath Asset retrieval
* QualityOps comment formatting
* Azure DevOps comment API call
* Structured output generation

### `entry-points.json`

Defines the UiPath agent entry point, input schema, output schema, and execution metadata.

### `bindings.json`

Contains UiPath binding metadata used by the coded agent runtime.

### `langgraph.json`

Contains LangGraph runtime configuration.

### `pyproject.toml`

Contains Python project and dependency configuration.

---

## Role in QualityOps QA Console

This agent supports the human review and approval phase of QualityOps.

It ensures that QA lead decisions are persisted back to the original requirement system.

This improves:

* Traceability
* Auditability
* Requirement review history
* QA governance
* Collaboration between QA and delivery teams

---

## Responsibility Separation

This agent is intentionally separated from the Requirement Analysis Agent.

| Agent                      | Responsibility                                        |
| -------------------------- | ----------------------------------------------------- |
| Requirement Analysis Agent | Fetches and analyzes the requirement                  |
| ADO WriteBack Agent        | Writes QA lead decision comments back to Azure DevOps |

This separation makes the workflow easier to govern, test, debug, and extend.

---

## Production Extension Ideas

This agent can be extended further with:

* Richer comment templates
* Work item tagging after approval or rejection
* Work item state transition support
* Link creation between requirement and generated test cases
* Support for multiple Azure DevOps projects
* Retry logic for transient API failures
* Data Service audit logging
* Role-based approval metadata
* Approval timestamp normalization
* Attachment support for generated QA reports

---

## Summary

The QualityOps ADO WriteBack Agent writes QA lead review decisions back to Azure DevOps.

It connects the human approval step in the QualityOps QA Console with the original requirement record, making the QA workflow more traceable, governed, and enterprise-ready.
