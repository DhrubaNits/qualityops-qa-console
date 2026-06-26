# QualityOps Test Result Triage Agent

The **QualityOps Test Result Triage Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to analyze UiPath Test Manager / Test Cloud execution results, classify failures, and create Azure DevOps bugs for valid defects.

This agent helps QA teams move from raw test execution results to meaningful failure triage and actionable defect management.

---

## Purpose

After test execution, QA teams often spend significant time manually reviewing failed tests, robot logs, assertion messages, screenshots, and execution evidence.

The purpose of this agent is to reduce that manual triage effort by classifying failures and recommending the next action.

It helps answer:

* Which test cases failed?
* What does the failure evidence say?
* Is the issue likely a product defect?
* Is it an automation issue?
* Is it an environment issue?
* Is it a data issue?
* Does the failure need manual review?
* Should a bug be created in Azure DevOps?

---

## Position in the QualityOps Workflow

```text
UiPath Test Manager / Test Cloud Execution
        ↓
Test Result Triage Agent
        ↓
Failure Classification
        ↓
Azure DevOps Bug Creation
        ↓
Final QA Report Agent
```

This agent runs after Test Manager / Test Cloud execution and before final QA reporting.

---

## Supported Modes

The agent supports three modes:

```text
listExecutions
analyzeExecution
createDefect
```

---

## Mode 1: listExecutions

This mode lists UiPath Test Manager executions for a project.

It is used when the QA lead wants to inspect available test execution runs before selecting one for analysis.

### Required input

| Field       | Required | Description                    |
| ----------- | -------- | ------------------------------ |
| `mode`      | Yes      | `listExecutions`               |
| `projectId` | Yes      | UiPath Test Manager project ID |

### Example input

```json
{
  "mode": "listExecutions",
  "projectId": "your-test-manager-project-id"
}
```

---

## Mode 2: analyzeExecution

This mode analyzes a selected UiPath Test Manager execution.

It fetches:

* Execution summary
* Test case logs
* Failed result rows
* Robot logs
* Assertion evidence
* Failure evidence
* Classification result
* Recommended action
* Test Manager evidence link

### Required input

| Field             | Required | Description                    |
| ----------------- | -------- | ------------------------------ |
| `mode`            | Yes      | `analyzeExecution`             |
| `projectId`       | Yes      | UiPath Test Manager project ID |
| `testExecutionId` | Yes      | Test execution ID to analyze   |

### Example input

```json
{
  "mode": "analyzeExecution",
  "projectId": "your-test-manager-project-id",
  "testExecutionId": "execution-id"
}
```

---

## Mode 3: createDefect

This mode creates an Azure DevOps bug from a triaged test failure.

It uses classification, evidence, test case details, and parent work item ID to create a structured Azure DevOps bug.

### Required input

| Field               | Required    | Description                      |
| ------------------- | ----------- | -------------------------------- |
| `mode`              | Yes         | `createDefect`                   |
| `projectId`         | Recommended | UiPath Test Manager project ID   |
| `testExecutionId`   | Recommended | Test execution ID                |
| `testCaseId`        | Recommended | Failed test case ID              |
| `testCaseName`      | Recommended | Failed test case name            |
| `classification`    | Recommended | Failure classification           |
| `evidence`          | Recommended | Failure evidence                 |
| `recommendedAction` | Recommended | Suggested next action            |
| `linkToTestCaseLog` | Recommended | Test Manager evidence link       |
| `adoParentId`       | Yes         | Azure DevOps parent work item ID |

### Example input

```json
{
  "mode": "createDefect",
  "projectId": "your-test-manager-project-id",
  "testExecutionId": "execution-id",
  "testCaseId": "test-case-id",
  "testCaseName": "TS-001 - Create patient and appointment successfully",
  "classification": "Product Defect",
  "evidence": "Assertion failed. Expected confirmation message was not displayed.",
  "recommendedAction": "Create a product defect and assign it to the application team.",
  "linkToTestCaseLog": "https://test-manager-evidence-link",
  "adoParentId": "514"
}
```

---

## What This Agent Does

The Test Result Triage Agent performs the following actions:

1. Accepts direct input fields or a JSON `question` payload.
2. Validates the selected mode.
3. Reads Test Manager bearer token and related credentials from UiPath Assets.
4. Lists Test Manager executions when requested.
5. Fetches execution summary for selected execution.
6. Fetches test case logs.
7. Identifies failed test case rows.
8. Fetches robot logs for failed test cases.
9. Fetches assertion evidence.
10. Builds failure evidence.
11. Classifies failure type.
12. Recommends next action.
13. Creates Azure DevOps bugs when requested.
14. Returns safe structured output.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent / coded function
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Test Manager / Test Cloud APIs
* UiPath Assets for secure configuration
* UiPath Coded App integration
* Structured failure analysis output
* Safe diagnostics and secret redaction

This agent is important for the Agentic Testing with Test Cloud track because it directly works with Test Manager execution data and failure triage.

---

## External Integration

This agent integrates with:

* UiPath Test Manager / Test Cloud
* Azure DevOps Work Item Tracking APIs

Test Manager is used for:

* Execution listing
* Execution summary
* Test case logs
* Robot logs
* Assertion evidence
* Evidence links

Azure DevOps is used for:

* Bug creation
* Parent work item linking
* Defect evidence storage

---

## Configuration

The agent reads Test Manager configuration from UiPath Assets.

Expected Test Manager assets:

```text
TEST_MANAGER_BEARER_TOKEN
TEST_MANAGER_REFRESH_TOKEN
TEST_MANAGER_CLIENT_ID
TEST_MANAGER_CLIENT_SECRET
```

The agent reads Azure DevOps configuration from UiPath Assets.

Expected Azure DevOps assets:

```text
AzureDevOps_Org
AzureDevOps_Project
AzureDevOps_PAT
```

The current implementation contains a Test Manager base URL constant. For production use, this value can be moved to an Orchestrator Asset or environment variable to support multiple tenants and environments.

---

## Failure Classification

The agent classifies failures using rule-based evidence matching.

Supported classifications:

```text
Product Defect
Automation Issue
Environment Issue
Data Issue
Needs Review
```

---

## Classification Rules

### Product Defect

Examples of matched evidence:

* Verification failed
* Assertion failed
* Expected / Actual mismatch
* Warning message not displayed
* Saved status after update operation did not match

Recommended action:

```text
Create a product defect and assign it to the application team.
```

### Automation Issue

Examples of matched evidence:

* UI element not found
* Selector issue
* Strict selector failure
* Multiple similar matches
* Browser communication issue
* Browser extension issue
* Active session issue

Recommended action:

```text
Review automation selector, browser, package, or workflow stability.
```

### Environment Issue

Examples of matched evidence:

* HTTP 503
* Service unavailable
* Database connection timeout
* Dependent API failure
* Environment not responding

Recommended action:

```text
Check environment availability, dependent services, database/API connectivity, and test data setup.
```

### Data Issue

Examples of matched evidence:

* Missing test data
* Invalid input data
* Data setup issue

Recommended action:

```text
Review test data setup and required input data.
```

### Needs Review

Used when evidence does not clearly match one of the known categories.

Recommended action:

```text
Manually inspect logs and failure evidence.
```

---

## Output Structure

The agent returns structured output.

| Output           | Description                             |
| ---------------- | --------------------------------------- |
| `status`         | success, error, or Failed               |
| `mode`           | Mode executed                           |
| `projectId`      | Test Manager project ID                 |
| `result`         | Mode-specific result object             |
| `blockedReasons` | Reasons the operation could not proceed |
| `nextAction`     | Recommended next action                 |

---

## Example analyzeExecution Output

```json
{
  "status": "success",
  "mode": "analyzeExecution",
  "projectId": "project-id",
  "result": {
    "status": "Completed",
    "executionSummary": {
      "testExecutionId": "execution-id",
      "totalTests": 10,
      "passed": 8,
      "failed": 2,
      "skipped": 0
    },
    "triageResults": [
      {
        "testCaseId": "123",
        "testCaseName": "TS-001 - Create patient and appointment successfully",
        "classification": "Product Defect",
        "matchedTerms": [
          "Assertion failed"
        ],
        "recommendedAction": "Create a product defect and assign it to the application team.",
        "linkToTestCaseLog": "https://test-manager-evidence-link"
      }
    ],
    "overallRecommendation": "2 failed test results found and classified."
  }
}
```

---

## Example createDefect Output

```json
{
  "status": "success",
  "mode": "createDefect",
  "projectId": "project-id",
  "result": {
    "status": "Completed",
    "defectCreationStatus": "Created",
    "defectSystem": "Azure DevOps",
    "adoBugId": "1005",
    "adoParentId": "514",
    "classification": "Product Defect",
    "evidenceAdded": true,
    "nextAction": "Review the created bug in Azure DevOps."
  }
}
```

---

## Azure DevOps Bug Content

When creating a bug, the agent includes:

* Bug title
* Failure classification
* Recommended action
* Test case name
* Test Manager evidence link
* Failure evidence
* Execution details
* Test execution ID
* Test case ID
* QualityOps generated tags
* Parent work item link

Bug tags include:

```text
QualityOps; Automated Triage; <Classification>; UiPath Test Manager
```

---

## Security and Redaction

The agent includes redaction logic to avoid exposing secrets.

It redacts:

* Tokens
* Secrets
* Authorization headers
* Bearer values
* Passwords
* Cookies

Safe diagnostics may include:

* Token present flag
* Token fingerprint
* Token length
* Token refresh attempted flag
* Response status code
* Endpoint path

The actual token value is not returned.

---

## Error Handling

The agent handles common failure scenarios, including:

* Invalid `question` JSON
* Missing mode
* Missing project ID
* Unsupported mode
* Missing Test Manager bearer token asset
* Test Manager API errors
* Token expiry and refresh
* Missing Azure DevOps configuration
* Missing Azure DevOps parent ID
* Azure DevOps PAT permission issue
* Invalid API response

When an operation cannot continue, the agent returns blocked reasons and next action.

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

* Input merging
* Mode routing
* Test Manager client
* Execution listing
* Execution analysis
* Robot log fetch
* Assertion fetch
* Failure classification
* Azure DevOps bug payload creation
* Azure DevOps bug creation
* Secret redaction
* Structured output generation

### `entry-points.json`

Defines the UiPath coded function entry point, direct input fields, output schema, and execution graph.

---

## Role in QualityOps QA Console

This agent helps QualityOps move from test execution to actionable failure triage.

It improves:

* Test failure analysis speed
* Failure classification consistency
* Product defect routing
* Automation issue identification
* Environment issue identification
* Data issue identification
* Bug creation traceability
* Release readiness reporting

---

## Responsibility Separation

This agent performs test result triage and can create defects when requested.

| Mode               | Responsibility                                      |
| ------------------ | --------------------------------------------------- |
| `listExecutions`   | Lists Test Manager executions                       |
| `analyzeExecution` | Analyzes and classifies failed execution results    |
| `createDefect`     | Creates Azure DevOps bugs from triaged failure data |

This mode-based design keeps the agent flexible while supporting the full QualityOps workflow.

---

## Production Extension Ideas

This agent can be extended further with:

* Configurable Test Manager base URL
* LLM-assisted evidence summarization
* Historical failure pattern matching
* Flaky test detection
* Duplicate bug detection
* Auto-routing by component owner
* Severity and priority prediction
* Screenshot or log attachment upload
* Jira defect creation support
* Slack or Teams triage notification
* Data Service triage audit history

---

## Summary

The QualityOps Test Result Triage Agent analyzes UiPath Test Manager / Test Cloud execution results, classifies failed tests, recommends next action, and creates Azure DevOps bugs for valid defects.

It helps convert raw execution failures into actionable QA decisions and supports the end-to-end Agentic Testing with Test Cloud workflow.
