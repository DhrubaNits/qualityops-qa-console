# QualityOps Test Manager WriteBack Agent

The **QualityOps Test Manager WriteBack Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to prepare and sync generated QA artifacts into **UiPath Test Manager / UiPath Test Cloud**.

This agent is one of the core agents for the **Agentic Testing with Test Cloud** track because it connects the agentic QA workflow with UiPath testing governance.

---

## Purpose

After requirements are analyzed, scenarios are generated, scenarios are reviewed, and test cases are created, the QA workflow needs to move into a governed testing platform.

The purpose of this agent is to prepare and optionally sync QualityOps-generated requirements, test cases, requirement links, test sets, and test set membership into UiPath Test Manager / Test Cloud.

It helps QA teams maintain:

* Requirement-to-test traceability
* Test case organization
* Test set preparation
* Execution planning
* Test Cloud readiness
* Governance across generated QA assets

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
Test Manager WriteBack Agent
        ↓
Automation Mapping
        ↓
Test Execution / Result Analysis
        ↓
Final QA Report
```

This agent runs after test generation and planning, and before automation mapping or execution analysis.

---

## What This Agent Does

The Test Manager WriteBack Agent performs the following actions:

1. Receives QualityOps requirement and test scenario data as JSON.
2. Validates required Test Manager sync inputs.
3. Builds a requirement payload.
4. Builds Test Manager test case payloads.
5. Builds requirement-to-test-case link metadata.
6. Selects an appropriate test set based on risk level.
7. Builds test set payload and test set membership.
8. Supports `DryRun` mode to preview sync payloads safely.
9. Supports `RealSync` mode to call UiPath Test Manager APIs.
10. Looks up Test Manager project by project prefix when required.
11. Creates requirement records in Test Manager.
12. Searches for reusable test cases before creating duplicates.
13. Creates new test cases when no matching test case exists.
14. Assigns test cases to requirements.
15. Creates a test set.
16. Assigns test cases to the created test set.
17. Returns sync summary, created IDs, reused IDs, diagnostics, and next action.

---

## UiPath Platform Usage

This agent demonstrates deep UiPath platform usage through:

* UiPath Coded Agent / coded function
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Test Manager / Test Cloud APIs
* UiPath Assets for Test Manager configuration
* UiPath Coded App integration
* Structured input and output schemas
* Safe diagnostic output for governed troubleshooting

This agent helps show that QualityOps is not only generating test content, but also integrating that content with UiPath Test Manager / Test Cloud.

---

## Sync Modes

The agent supports two sync modes.

## 1. DryRun

`DryRun` is the default and safest mode.

In DryRun mode, the agent:

* Validates the input
* Prepares requirement payload
* Prepares test case payloads
* Prepares requirement links
* Prepares test set payload
* Prepares test set membership
* Returns a summary
* Does not call Test Manager APIs

DryRun is useful for:

* Demo validation
* Payload review
* Debugging
* Safe preview before real sync

## 2. RealSync

`RealSync` performs actual calls to UiPath Test Manager APIs.

In RealSync mode, the agent can:

* Resolve the Test Manager project
* Create a requirement
* Search for existing test cases
* Reuse matching test cases
* Create new test cases
* Assign test cases to the requirement
* Create a test set
* Assign test cases to the test set

RealSync requires valid Test Manager configuration.

---

## Configuration

For RealSync, the agent uses the following configuration values:

```text
TEST_MANAGER_BEARER_TOKEN
TEST_MANAGER_BASE_URL
TEST_MANAGER_PROJECT_PREFIX
TEST_MANAGER_REFRESH_TOKEN
TEST_MANAGER_CLIENT_ID
TEST_MANAGER_CLIENT_SECRET
TEST_MANAGER_TOKEN_URL
```

The agent can read these values from:

* UiPath Assets
* Environment variables

For published cloud execution, UiPath Assets are preferred.

Do not commit real tokens, client secrets, refresh tokens, tenant-specific URLs, or authorization headers.

---

## Authentication and Token Handling

The agent includes authentication handling for Test Manager API calls.

It supports:

* Bearer token normalization
* Detection of whether the token already starts with `Bearer`
* Safe token fingerprinting
* Token length reporting
* Safe request header diagnostics
* Token refresh attempt when a 401 response is detected
* Retry after token refresh
* Secret redaction in error messages

The agent does not return the actual token value.

---

## Inputs

This agent accepts one input field named `question`.

The `question` value should be a JSON string.

### Required fields inside `question`

| Field                   | Required | Description                        |
| ----------------------- | -------- | ---------------------------------- |
| `requirementId`         | Yes      | Source requirement/work item ID    |
| `testManagerProjectKey` | Yes      | Test Manager project key or prefix |
| `testScenarios`         | Yes      | Test scenarios to prepare or sync  |

### Optional fields inside `question`

| Field                      | Required | Description                           |
| -------------------------- | -------- | ------------------------------------- |
| `testManagerProjectId`     | No       | Test Manager project ID               |
| `testManagerProjectPrefix` | No       | Project prefix for lookup             |
| `testManagerProjectName`   | No       | Project display name                  |
| `syncMode`                 | No       | DryRun or RealSync                    |
| `requirementTitle`         | No       | Requirement title                     |
| `requirementDescription`   | No       | Requirement description               |
| `riskLevel`                | No       | High, Medium, Low, or unknown         |
| `environment`              | No       | Target environment                    |
| `submittedBy`              | No       | User or system submitting the request |

---

## Example Input: DryRun

```json
{
  "syncMode": "DryRun",
  "requirementId": "514",
  "testManagerProjectKey": "QUALITYOPS",
  "testManagerProjectName": "QualityOps Test Project",
  "requirementTitle": "Validate end-to-end patient care workflow",
  "requirementDescription": "Clinic staff should register patient, verify eligibility, and schedule appointment.",
  "riskLevel": "High",
  "environment": "SQA",
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
      ],
      "expectedResult": "Patient record and appointment are created successfully with audit history captured."
    }
  ]
}
```

---

## Example Output: DryRun

```json
{
  "syncStatus": "ReadyToSync",
  "syncMode": "DryRun",
  "requirementId": "514",
  "testManagerProjectKey": "QUALITYOPS",
  "requirementPayload": {
    "externalId": "ADO-514",
    "name": "Validate end-to-end patient care workflow",
    "description": "Clinic staff should register patient, verify eligibility, and schedule appointment."
  },
  "summary": {
    "requirementsPrepared": 1,
    "testCasesPrepared": 1,
    "linksPrepared": 1,
    "testSetsPrepared": 1
  },
  "blockedReasons": [],
  "nextAction": "Review prepared payloads and rerun with syncMode RealSync to call UiPath Test Manager APIs."
}
```

---

## Example Input: RealSync

```json
{
  "syncMode": "RealSync",
  "requirementId": "514",
  "testManagerProjectKey": "QUALITYOPS",
  "testManagerProjectName": "QualityOps Test Project",
  "requirementTitle": "Validate end-to-end patient care workflow",
  "requirementDescription": "Clinic staff should register patient, verify eligibility, and schedule appointment.",
  "riskLevel": "High",
  "environment": "SQA",
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
      ],
      "expectedResult": "Patient record and appointment are created successfully with audit history captured."
    }
  ]
}
```

---

## Outputs

The agent returns structured output.

| Output                   | Description                                              |
| ------------------------ | -------------------------------------------------------- |
| `syncStatus`             | ReadyToSync, Completed, ConfigurationRequired, or Failed |
| `syncMode`               | DryRun or RealSync                                       |
| `requirementId`          | Source requirement ID                                    |
| `testManagerProjectId`   | Test Manager project ID                                  |
| `testManagerProjectKey`  | Test Manager project key                                 |
| `testManagerProjectName` | Test Manager project name                                |
| `requirementPayload`     | Prepared requirement payload                             |
| `testCasePayloads`       | Prepared Test Manager test case payloads                 |
| `requirementLinks`       | Prepared requirement-to-test-case links                  |
| `testSetPayload`         | Prepared test set payload                                |
| `testSetMembership`      | Prepared test set membership                             |
| `summary`                | Prepared object counts                                   |
| `blockedReasons`         | Reasons sync is blocked                                  |
| `nextAction`             | Recommended next step                                    |
| `realSyncAttempted`      | Whether RealSync was attempted                           |
| `createdRequirement`     | Created Test Manager requirement ID                      |
| `createdTestCaseIds`     | Test cases created in Test Manager                       |
| `reusedTestCaseIds`      | Existing test cases reused                               |
| `allTestCaseIds`         | All created and reused test case IDs                     |
| `createdTestSetId`       | Created Test Manager test set ID                         |
| `testCaseSyncDetails`    | Per-test-case sync details                               |

---

## Test Set Selection

The agent selects a test set based on risk level.

| Risk Level | Test Set                                 |
| ---------- | ---------------------------------------- |
| High       | High Risk Functional + Integration Suite |
| Medium     | Standard Regression Validation Suite     |
| Low        | Smoke Validation Suite                   |
| Unknown    | QualityOps Generated Test Suite          |

This connects risk-based planning with Test Manager execution organization.

---

## Test Case Reuse

The agent can search existing Test Manager test cases before creating new ones.

Reuse matching can use:

* Foreign reference
* Scenario ID
* Normalized title
* Scenario index
* Requirement external ID

This helps reduce duplicate test cases in Test Manager and supports cleaner enterprise adoption.

---

## Requirement and Test Case Payloads

The agent creates a requirement payload using:

* External ID
* Requirement name
* Requirement description

It creates test case payloads using:

* Scenario ID
* Foreign reference
* Scenario title
* Priority
* Test type
* Steps
* Expected result

It also creates requirement-link metadata so generated test cases can be traced back to the source requirement.

---

## Error Handling

The agent handles common failure and configuration scenarios, including:

* Invalid JSON input
* Missing requirement ID
* Missing Test Manager project key
* Missing test scenarios
* Missing RealSync token
* Missing Test Manager base URL
* Missing project ID or prefix
* Test Manager API failure
* Authentication/session rejection
* Token expiry
* Token refresh configuration missing
* Invalid API response
* Test case assignment payload variation

When errors occur, the agent returns structured blocked reasons and safe diagnostics.

---

## Safe Diagnostics

The agent returns diagnostic information useful for debugging without exposing secrets.

Safe diagnostics include:

* Whether token is present
* Whether auth header was prepared
* Token length
* Token fingerprint
* Whether token had Bearer prefix
* First endpoint path
* Request URL used
* Response status code
* Response content type
* Whether token refresh was attempted
* Whether retry was attempted

The agent does not return the actual bearer token or client secret.

---

## Security Notes

This agent integrates with Test Manager APIs, so secure configuration is important.

Rules followed:

* Do not commit `.env`.
* Do not commit bearer tokens.
* Do not commit refresh tokens.
* Do not commit client secrets.
* Do not expose authorization headers.
* Store Test Manager configuration in UiPath Assets for cloud execution.
* Use environment variables only for local testing.
* Redact sensitive values from error messages.
* Keep sample data generic and demo-safe.

---

## Files in This Agent

Typical files in this folder:

```text
main.py
entry-points.json
bindings.json
main.mermaid
project.uiproj
pyproject.toml
sample-input.json
sample-input-realsync.json
README.md
```

### `main.py`

Contains the coded implementation for:

* Input parsing
* DryRun payload generation
* RealSync Test Manager API integration
* Test Manager configuration resolution
* Token normalization and refresh
* Requirement creation
* Test case search and reuse
* Test case creation
* Requirement-to-test-case assignment
* Test set creation
* Test set membership assignment
* Safe diagnostic output
* Structured response generation

### `entry-points.json`

Defines the UiPath coded function entry point, input schema, output schema, and execution graph.

---

## Role in QualityOps QA Console

This agent bridges the QualityOps agentic QA workflow into UiPath Test Manager / Test Cloud.

It makes generated test scenarios usable inside UiPath’s testing platform and supports the official Agentic Testing with Test Cloud track.

It improves:

* Test Manager adoption
* Test case governance
* Requirement traceability
* Test set planning
* Test Cloud readiness
* Enterprise QA workflow integration

---

## Responsibility Separation

This agent is intentionally separate from other workflow agents.

| Agent                                | Responsibility                                |
| ------------------------------------ | --------------------------------------------- |
| Risk-Based Test Planner Agent        | Recommends execution order                    |
| Test Cloud Execution Readiness Agent | Checks if execution is ready                  |
| Test Manager WriteBack Agent         | Prepares or syncs test assets to Test Manager |

This separation keeps the QualityOps workflow modular and easy to debug.

---

## Production Extension Ideas

This agent can be extended further with:

* Direct Test Cloud execution trigger
* Test execution schedule creation
* Test suite update instead of create-only behavior
* More advanced duplicate detection
* Multi-project sync
* Environment-specific test set selection
* Test Manager result readback
* Stronger release gate integration
* Test case versioning
* Data Service audit logging

---

## Summary

The QualityOps Test Manager WriteBack Agent prepares and syncs generated QA assets into UiPath Test Manager / Test Cloud.

It supports DryRun preview, RealSync execution, test case reuse, test set creation, requirement linking, and safe diagnostics.

This agent helps demonstrate that QualityOps is a working agentic testing solution built on the UiPath Platform, not just a standalone AI test generation tool.
