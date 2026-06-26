# QualityOps Automation Link Agent

The **QualityOps Automation Link Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to link generated UiPath Test Manager test cases with UiPath automation package entry points.

This agent helps connect generated QA test cases with executable UiPath automation assets so the test cases can move closer to automated execution in UiPath Test Manager / Test Cloud.

---

## Purpose

After test cases are created or synced into UiPath Test Manager, QA teams need to connect those test cases with automation assets.

The purpose of this agent is to map Test Manager test cases to UiPath automation package entry points.

It helps QA teams understand:

* Which generated test cases are linked to automation
* Which automation profile is assigned
* Whether the automation link succeeded or failed
* Whether package entry points are available
* Whether configuration or token issues are blocking automation linking

---

## Position in the QualityOps Workflow

```text
Test Manager WriteBack Agent
        ↓
Automation Link Agent
        ↓
Test Cloud Execution Readiness Agent
        ↓
UiPath Test Manager / Test Cloud Execution
        ↓
Test Result Triage Agent
```

This agent runs after test cases are available in UiPath Test Manager and before execution readiness or execution analysis.

---

## What This Agent Does

The Automation Link Agent performs the following actions:

1. Receives a JSON payload from the QualityOps QA Console.
2. Validates the Test Manager project ID.
3. Validates created Test Manager test case IDs.
4. Resolves the automation package identifier.
5. Reads Test Manager configuration from UiPath Assets or environment variables.
6. Fetches package entry points from UiPath Test Manager.
7. Builds a lookup of available package entry points.
8. Maps each test case ID to a simulator profile.
9. Calls Test Manager `updatepackageautomation`.
10. Returns linked mappings, linked count, failed count, blocked reasons, and next action.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent / coded function
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Test Manager / Test Cloud APIs
* UiPath Assets for secure configuration
* UiPath automation package entry points
* UiPath Coded App integration
* Structured input and output schema

This agent helps show how QualityOps connects agent-generated test assets to UiPath automation execution capability.

---

## Demo Automation Package

Default package identifier:

```text
QualityOpsDemoExecutionSimulator
```

This package is used for hackathon demo execution and simulator-based automation mapping.

In production, this can be replaced with a real UiPath automation package that contains actual automated test workflows.

---

## Simulator Profiles

The agent maps created test cases to simulator package entry points.

Default simulator profiles include:

```text
Test Case UI\SIM_PASS_001
Test Case UI\SIM_ASSERTION_FAILURE_001
Test Case UI\SIM_AUTOMATION_UI_FAILURE_001
Test Case UI\SIM_AUTOMATION_BROWSER_FAILURE_001
Test Case UI\SIM_AUTOMATION_SELECTOR_AMBIGUOUS_001
Test Case UI\SIM_ENVIRONMENT_FAILURE_001
Test Case UI\SIM_ASSERTION_FAILURE_002
Test Case UI\SIM_ENVIRONMENT_FAILURE_002
Test Case UI\SIM_PASS_002
Test Case UI\SIM_PASS_E2E_001
```

These simulator profiles allow the demo to show passing tests, assertion failures, automation failures, browser failures, selector issues, and environment failures.

This is useful for demonstrating downstream Test Result Triage Agent behavior.

---

## Configuration

The agent reads Test Manager configuration from UiPath Assets or environment variables.

Expected configuration values:

```text
TEST_MANAGER_BEARER_TOKEN
TEST_MANAGER_REFRESH_TOKEN
TEST_MANAGER_CLIENT_ID
TEST_MANAGER_CLIENT_SECRET
TEST_MANAGER_TOKEN_URL
TEST_MANAGER_BASE_URL
TEST_MANAGER_PROJECT_PREFIX
```

For published cloud execution, UiPath Assets are preferred.

Do not commit real bearer tokens, refresh tokens, client secrets, tenant-specific values, or authorization headers.

---

## Inputs

This agent accepts one input field named `question`.

The `question` value should be a JSON string.

### Required fields inside `question`

| Field                | Required | Description                                        |
| -------------------- | -------- | -------------------------------------------------- |
| `projectId`          | Yes      | UiPath Test Manager project ID                     |
| `createdTestCaseIds` | Yes      | Test Manager test case IDs to link with automation |

### Optional fields inside `question`

| Field               | Required | Description                          |
| ------------------- | -------- | ------------------------------------ |
| `packageIdentifier` | No       | UiPath automation package identifier |

If `packageIdentifier` is not provided, the agent uses:

```text
QualityOpsDemoExecutionSimulator
```

---

## Example Input

```json
{
  "projectId": "your-test-manager-project-id",
  "createdTestCaseIds": [
    "1001",
    "1002",
    "1003"
  ],
  "packageIdentifier": "QualityOpsDemoExecutionSimulator"
}
```

---

## Outputs

The agent returns structured output.

| Output                            | Description                                           |
| --------------------------------- | ----------------------------------------------------- |
| `automationLinkStatus`            | Completed, Partial, or Failed                         |
| `linkedCount`                     | Number of test cases linked successfully              |
| `failedCount`                     | Number of test cases that failed to link              |
| `packageIdentifier`               | Automation package identifier used                    |
| `linkedMappings`                  | Per-test-case mapping results                         |
| `blockedReasons`                  | Reasons automation linking failed or partially failed |
| `nextAction`                      | Recommended next step                                 |
| `packageEntryPointFetchAttempted` | Whether package entry points were fetched             |
| `packageEntryPointFetchSucceeded` | Whether package entry point fetch succeeded           |
| `updateAutomationAttempted`       | Whether updatepackageautomation was attempted         |
| `tokenRefreshAttempted`           | Whether token refresh was attempted                   |
| `tokenRefreshSucceeded`           | Whether token refresh succeeded                       |
| `responseStatusCode`              | API response status code                              |
| `failedEndpointPath`              | Failed API endpoint path, if any                      |

---

## Example Output: Completed

```json
{
  "automationLinkStatus": "Completed",
  "linkedCount": 3,
  "failedCount": 0,
  "packageIdentifier": "QualityOpsDemoExecutionSimulator",
  "linkedMappings": [
    {
      "testCaseId": "1001",
      "simulatorProfile": "Test Case UI\\SIM_PASS_001",
      "status": "Linked"
    },
    {
      "testCaseId": "1002",
      "simulatorProfile": "Test Case UI\\SIM_ASSERTION_FAILURE_001",
      "status": "Linked"
    }
  ],
  "blockedReasons": [],
  "nextAction": "Execute the Test Set in UiPath Test Manager."
}
```

---

## Example Output: Partial

```json
{
  "automationLinkStatus": "Partial",
  "linkedCount": 2,
  "failedCount": 1,
  "packageIdentifier": "QualityOpsDemoExecutionSimulator",
  "linkedMappings": [
    {
      "testCaseId": "1001",
      "simulatorProfile": "Test Case UI\\SIM_PASS_001",
      "status": "Linked"
    },
    {
      "testCaseId": "1003",
      "simulatorProfile": "Test Case UI\\SIM_AUTOMATION_UI_FAILURE_001",
      "status": "Failed"
    }
  ],
  "blockedReasons": [
    "Package entry point not found: Test Case UI\\SIM_AUTOMATION_UI_FAILURE_001"
  ],
  "nextAction": "Resolve blocked reasons, then rerun the automation link agent."
}
```

---

## Package Entry Point Lookup

The agent fetches package entry points using the Test Manager API and builds a lookup table.

It filters entry points by:

```text
packageIdentifier
```

Then it matches package entry point names against the expected simulator profile names.

If a matching entry point is found, the test case is linked to that automation profile.

If a matching entry point is not found, the mapping is marked as failed and returned in `blockedReasons`.

---

## Test Manager API Usage

The agent uses Test Manager API endpoints for:

* Fetching package entry points
* Updating test case automation package mapping

Important endpoint patterns include:

```text
/api/v2/{projectId}/orchestrator/packageentrypoints
/api/v2/{projectId}/testcases/{testCaseId}/updatepackageautomation
```

---

## Token Handling

The agent supports:

* Bearer token normalization
* Reading token from UiPath Assets or environment variables
* Token refresh when access token expires
* Retry after token refresh
* Safe API error formatting

The agent does not return token values.

---

## Error Handling

The agent handles common failure scenarios, including:

* Invalid JSON input
* Input not being a JSON object
* Missing project ID
* Missing created test case IDs
* Empty created test case ID list
* Missing package identifier
* Missing Test Manager bearer token
* Missing Test Manager base URL
* Package entry point fetch failure
* Package entry point not found
* Test Manager API failure
* Token expiry
* Token refresh configuration missing
* Invalid API response

The agent returns structured blocked reasons and diagnostic flags to support troubleshooting.

---

## Security Notes

This agent integrates with UiPath Test Manager APIs, so secure configuration is important.

Rules followed:

* Do not commit `.env`.
* Do not commit bearer tokens.
* Do not commit refresh tokens.
* Do not commit client secrets.
* Do not expose authorization headers.
* Use UiPath Assets for published cloud execution.
* Use environment variables only for local testing.
* Keep sample data generic and demo-safe.
* Redact sensitive API errors where applicable.

---

## Files in This Agent

Typical files in this folder:

```text
main.py
entry-points.json
bindings.json
project.uiproj
pyproject.toml
sample-input-automation-link.json
uipath.json
README.md
```

### `main.py`

Contains the coded implementation for:

* Input parsing
* Test Manager config resolution
* Asset reading
* Token normalization
* Token refresh
* Package entry point fetching
* Package entry point lookup creation
* Test case to automation profile mapping
* Test Manager updatepackageautomation call
* Structured output generation

### `entry-points.json`

Defines the UiPath coded function entry point, input schema, output schema, and execution output.

---

## Role in QualityOps QA Console

This agent connects generated Test Manager test cases with executable UiPath automation assets.

It improves:

* Automation coverage visibility
* Test Manager execution readiness
* Test case to automation traceability
* Demo execution simulation
* Test result triage preparation
* QualityOps end-to-end workflow completeness

---

## Responsibility Separation

This agent is intentionally separate from Test Manager sync and execution readiness.

| Agent                                | Responsibility                                                   |
| ------------------------------------ | ---------------------------------------------------------------- |
| Test Manager WriteBack Agent         | Creates or prepares Test Manager test cases and test sets        |
| Automation Link Agent                | Links Test Manager test cases to automation package entry points |
| Test Cloud Execution Readiness Agent | Checks whether the workflow is ready for Test Cloud execution    |

This separation keeps QualityOps modular and easier to debug.

---

## Production Extension Ideas

This agent can be extended further with:

* Real automation package discovery
* Scenario-to-automation matching by tags
* Automation coverage scoring
* Test case automation candidate filtering
* Bulk automation link retry
* Support for multiple automation packages
* Mapping by scenario ID, title, or requirement area
* Data Service audit logging
* Automation maintenance recommendations
* Flaky automation detection

---

## Summary

The QualityOps Automation Link Agent links UiPath Test Manager test cases to UiPath automation package entry points.

It bridges generated QA assets with executable automation and helps complete the end-to-end Agentic Testing with Test Cloud workflow.
