# QualityOps Test Result Triage Agent

Clean UiPath coded agent project for Test Manager execution triage.

## Modes

- `listExecutions`
- `analyzeExecution`
- `createDefect`

## Required Orchestrator Assets

- `TEST_MANAGER_BEARER_TOKEN`
- `TEST_MANAGER_REFRESH_TOKEN`
- `TEST_MANAGER_CLIENT_ID`
- `TEST_MANAGER_CLIENT_SECRET`

Set `TEST_MANAGER_BASE_URL` or rely on `UIPATH_URL` at runtime.
