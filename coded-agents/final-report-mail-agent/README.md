# QualityOps Final Report Mail Agent

The **QualityOps Final Report Mail Agent** is a UiPath Coded Agent used in the QualityOps QA Console workflow to send the final QA report to stakeholders by email.

This agent is the final communication step in the QualityOps end-to-end QA orchestration flow. It sends the generated QA sign-off report using UiPath Integration Service with Gmail.

---

## Purpose

After requirement analysis, test generation, review, planning, Test Manager sync, automation mapping, execution triage, bug creation, and final report generation, the QA lead needs to communicate the final QA status to stakeholders.

The purpose of this agent is to send the final QA report by email in a structured and governed way.

It helps QA teams communicate:

* Final QA status
* Test execution summary
* Open bugs
* Risk and readiness summary
* Test Manager execution link
* Recommended next action
* QA sign-off status

---

## Position in the QualityOps Workflow

```text
Requirement Analysis
        ↓
Human Review and Approval
        ↓
Test Scenario Generation
        ↓
Test Case Creation
        ↓
Risk-Based Planning
        ↓
Test Manager / Test Cloud Sync
        ↓
Automation Mapping
        ↓
Test Result Triage
        ↓
Bug Creation
        ↓
Final QA Report Agent
        ↓
Final Report Mail Agent
```

This agent runs at the end of the workflow after the final QA report is generated.

---

## What This Agent Does

The Final Report Mail Agent performs the following actions:

1. Receives final QA report details from the QualityOps QA Console.
2. Accepts direct input fields or a JSON `question` payload.
3. Validates recipient, subject, and report content.
4. Converts plain text report into simple HTML when HTML is not provided.
5. Prepares Gmail send email activity input.
6. Sends the report using UiPath Integration Service.
7. Returns email status, sent timestamp, blocked reasons, and next action.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* UiPath Coded Agent
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Integration Service
* Gmail connector
* UiPath Coded App integration
* Structured input and output schema
* Governed stakeholder communication

The agent is called from the QualityOps QA Console and runs as part of the UiPath-governed QA workflow.

---

## Integration Service Usage

This agent uses UiPath Integration Service to send email through Gmail.

Connection key:

```text
qualityopsagent-gmail
```

Connector key:

```text
uipath-google-gmail
```

Activity object path:

```text
/SendEmail
```

The agent invokes the Gmail send email activity through UiPath platform connections.

---

## Inputs

This agent supports both direct input fields and JSON through the `question` field.

### Supported input fields

| Field                      | Required                        | Description                          |
| -------------------------- | ------------------------------- | ------------------------------------ |
| `mode`                     | Yes                             | Must be `sendFinalReportEmail`       |
| `to`                       | Yes                             | Email recipient list                 |
| `cc`                       | No                              | CC recipient list                    |
| `subject`                  | Yes                             | Email subject                        |
| `htmlReport`               | Required if plain text is empty | HTML report body                     |
| `plainTextReport`          | Required if HTML is empty       | Plain text report body               |
| `executionName`            | No                              | Test execution or report name        |
| `adoBugLinks`              | No                              | Azure DevOps bug links               |
| `testManagerExecutionLink` | No                              | UiPath Test Manager execution link   |
| `variationId`              | No                              | Optional variation or run identifier |

---

## Example Input

```json
{
  "mode": "sendFinalReportEmail",
  "to": "qa.lead@example.com",
  "cc": "release.manager@example.com",
  "subject": "QualityOps Final QA Report - Requirement 514",
  "htmlReport": "<h2>Final QA Report</h2><p>Status: Ready for QA sign-off.</p>",
  "plainTextReport": "Final QA Report\nStatus: Ready for QA sign-off.",
  "executionName": "QualityOps Execution - Requirement 514",
  "adoBugLinks": [
    "https://dev.azure.com/example/project/_workitems/edit/1005"
  ],
  "testManagerExecutionLink": "https://test-manager-execution-link"
}
```

---

## Example Input Using `question`

```json
{
  "question": "{\"mode\":\"sendFinalReportEmail\",\"to\":\"qa.lead@example.com\",\"subject\":\"QualityOps Final QA Report\",\"plainTextReport\":\"Final QA Report generated successfully.\"}"
}
```

---

## Outputs

The agent returns structured output.

| Output           | Description                            |
| ---------------- | -------------------------------------- |
| `status`         | Completed or Failed                    |
| `emailStatus`    | Sent or Not Sent                       |
| `to`             | Recipient list                         |
| `cc`             | CC list                                |
| `subject`        | Email subject                          |
| `sentAt`         | UTC timestamp when email was sent      |
| `nextAction`     | Recommended next action                |
| `blockedReasons` | Validation or provider failure reasons |

---

## Example Success Output

```json
{
  "status": "Completed",
  "emailStatus": "Sent",
  "to": "qa.lead@example.com",
  "cc": "release.manager@example.com",
  "subject": "QualityOps Final QA Report - Requirement 514",
  "sentAt": "2026-06-26T10:30:00+00:00",
  "nextAction": "Final QA sign-off report email sent successfully.",
  "blockedReasons": []
}
```

---

## Example Failure Output

```json
{
  "status": "Failed",
  "emailStatus": "Not Sent",
  "to": "",
  "cc": "",
  "subject": "",
  "sentAt": "",
  "nextAction": "",
  "blockedReasons": [
    "to is required.",
    "subject is required.",
    "htmlReport or plainTextReport is required."
  ]
}
```

---

## Validation Rules

The agent validates:

| Check                                       | Failure Reason                            |
| ------------------------------------------- | ----------------------------------------- |
| Mode is not `sendFinalReportEmail`          | mode must be sendFinalReportEmail         |
| Recipient is missing                        | to is required                            |
| Subject is missing                          | subject is required                       |
| Both HTML and plain text report are missing | htmlReport or plainTextReport is required |

This prevents incomplete or accidental email sending.

---

## Report Body Handling

The agent supports both HTML and plain text reports.

If `htmlReport` is provided, it is used as the email body.

If `htmlReport` is empty but `plainTextReport` is provided, the agent converts line breaks into `<br/>` and sends it as simple HTML.

This allows the final report to be sent even when only plain text output is available.

---

## Recipient Handling

The agent supports multiple recipients.

Recipient strings can use commas or semicolons.

Example:

```text
qa.lead@example.com; release.manager@example.com
```

The agent normalizes recipients into the format required by the Gmail send email activity.

---

## Error Handling

The agent handles common failure scenarios, including:

* Invalid JSON in `question`
* Missing recipient
* Missing subject
* Missing report body
* Unsupported mode
* Gmail Integration Service failure
* Authentication or authorization issue
* Connector or connection issue

When an email provider error contains sensitive terms, the agent returns a safe message and does not expose credentials.

---

## Security Notes

This agent uses UiPath Integration Service and a configured Gmail connection.

Security rules:

* Do not commit credentials.
* Do not expose access tokens.
* Do not expose refresh tokens.
* Do not expose client secrets.
* Do not expose connector authorization details.
* Use UiPath Integration Service connections for email sending.
* Keep sample email addresses generic in documentation.

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

* Input normalization
* Input validation
* Mail message construction
* Recipient normalization
* Gmail activity metadata construction
* UiPath Integration Service invocation
* Safe error handling
* Structured output generation

### `entry-points.json`

Defines the UiPath coded agent entry point, input schema, output schema, and graph.

---

## Role in QualityOps QA Console

This agent completes the QualityOps workflow by sending the final QA report to stakeholders.

It improves:

* QA communication
* Release visibility
* Stakeholder alignment
* Sign-off traceability
* Final report distribution
* End-to-end workflow completeness

---

## Responsibility Separation

This agent is intentionally separate from the Final QA Report Agent.

| Agent                   | Responsibility                |
| ----------------------- | ----------------------------- |
| Final QA Report Agent   | Generates the final QA report |
| Final Report Mail Agent | Sends the report by email     |

This separation keeps report generation and report delivery independent and easier to debug.

---

## Production Extension Ideas

This agent can be extended further with:

* Microsoft Outlook connector support
* Attachment support
* PDF report attachment
* Dynamic stakeholder list from Data Service
* Email template selection
* Slack or Teams notification
* Draft mode before sending
* Approval before sending final report
* Delivery audit logging
* Multi-environment report routing

---

## Summary

The QualityOps Final Report Mail Agent sends the final QA report using UiPath Integration Service and Gmail.

It completes the end-to-end QualityOps QA workflow by turning generated QA insights, execution results, triage output, and release recommendations into stakeholder communication.
