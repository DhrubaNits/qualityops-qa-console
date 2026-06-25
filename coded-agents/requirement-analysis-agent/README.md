# QualityOps Requirement Analysis Agent

The **QualityOps Requirement Analysis Agent** is the first UiPath Coded Agent in the QualityOps QA Console workflow.

This agent is responsible for converting a raw Azure DevOps requirement into structured, QA-ready analysis. It fetches the requirement details, evaluates the requirement from a QA testing perspective, checks readiness using local QA/RAG checklist context, identifies gaps, calculates a readiness score, and returns a structured JSON response to the UiPath Coded App.

This agent helps ensure that test scenario generation starts only after the requirement is understood, reviewed, and ready for downstream QA activities.

---

## Purpose

In many QA teams, requirements are often incomplete, unclear, or not directly test-ready. QA leads and QA engineers spend significant manual effort reading the requirement, identifying impacted modules, understanding testing scope, checking acceptance criteria, and deciding whether clarification is required.

The purpose of this agent is to reduce that manual analysis effort by producing a consistent QA assessment for every requirement.

The agent helps answer questions such as:

* Is the requirement clear enough for QA?
* Are acceptance criteria present and testable?
* Which modules or workflows may be impacted?
* What type of change is this?
* What is the QA risk level?
* What testing scope is required?
* What test focus areas should be considered?
* Are there any requirement gaps?
* Does the QA lead need to review or request clarification?
* Can the workflow proceed to test scenario generation?

---

## Position in the QualityOps Workflow

This agent starts the QualityOps end-to-end testing workflow.

```text
Azure DevOps Requirement
        ↓
Requirement Analysis Agent
        ↓
Human Review and Approval
        ↓
Test Scenario Generation Agent
        ↓
Test Case Review Memory Agent
        ↓
Azure DevOps Test Case WriteBack Agent
        ↓
Risk-Based Test Planner Agent
        ↓
UiPath Test Manager / Test Cloud Sync
        ↓
Automation Mapping
        ↓
Test Result Analysis and Triage
        ↓
Bug Creation
        ↓
Final QA Report and Email
```

The output of this agent becomes the input for the human review step and the test scenario generation step.

---

## What This Agent Does

The Requirement Analysis Agent performs the following actions:

1. Receives a requirement ID from the QualityOps QA Console.
2. Validates the required input values.
3. Fetches the Azure DevOps work item details.
4. Extracts important requirement fields.
5. Performs QA impact analysis.
6. Identifies impacted modules.
7. Determines change type.
8. Assesses risk level.
9. Recommends testing scope.
10. Suggests test focus areas.
11. Retrieves local QA/RAG checklist context.
12. Evaluates requirement quality.
13. Identifies missing or unclear requirement information.
14. Calculates a readiness score from 0 to 100.
15. Decides whether QA lead review is required.
16. Returns structured JSON output for downstream workflow steps.

---

## UiPath Platform Usage

This agent demonstrates UiPath platform usage through:

* **UiPath Coded Agent**
* **UiPath Automation Cloud**
* **UiPath Orchestrator Jobs**
* **UiPath Assets**
* **UiPath Coded App integration**
* **Structured input and output schemas**
* **Cloud-based governed agent execution**

The agent is designed to run as part of a governed UiPath Automation Cloud workflow. The QualityOps Coded App acts as the user-facing QA console, while UiPath Orchestrator manages agent job execution.

---

## External Integration

This agent integrates with **Azure DevOps** to fetch requirement or work item details.

It reads the following work item fields where available:

* Work item ID
* Title
* Description
* Acceptance criteria
* State
* Area path
* Tags
* Work item type
* Work item URL

---

## Configuration

Azure DevOps configuration can be supplied in two ways.

### Local development

For local development, configuration can be supplied using environment variables:

```text
AZURE_DEVOPS_ORG
AZURE_DEVOPS_PROJECT
AZURE_DEVOPS_PAT
```

### Published UiPath cloud execution

For published execution through UiPath Orchestrator Jobs, configuration can be supplied using UiPath Assets:

```text
AzureDevOps_Org
AzureDevOps_Project
AzureDevOps_PAT
```

The agent first checks local environment variables. If those are not available, it attempts to read the required values from UiPath Assets.

Real tokens, PAT values, client secrets, and tenant-specific credentials must never be committed to Git.

---

## Inputs

| Input           | Required | Description                                                |
| --------------- | -------- | ---------------------------------------------------------- |
| `requirementId` | Yes      | Azure DevOps work item ID to fetch and analyze             |
| `submittedBy`   | Yes      | Name or email of the user/system submitting the request    |
| `environment`   | No       | Target environment selected from the QualityOps QA Console |

Example input:

```json
{
  "requirementId": "514",
  "submittedBy": "qa.lead@example.com",
  "environment": "SQA"
}
```

---

## Outputs

The agent returns structured JSON with the following high-level fields:

| Output                       | Description                                                       |
| ---------------------------- | ----------------------------------------------------------------- |
| `processingStatus`           | Overall processing outcome                                        |
| `requirementTitle`           | Requirement title fetched from Azure DevOps                       |
| `requirementDescription`     | Requirement description fetched from Azure DevOps                 |
| `acceptanceCriteria`         | Acceptance criteria fetched from Azure DevOps                     |
| `qaAnalysisSummary`          | QA impact, risk, testing scope, and suggested focus               |
| `requirementQualityAnalysis` | Readiness score, gaps, checklist usage, and review recommendation |
| `qaLeadNotificationRequired` | Indicates whether QA lead action is required                      |
| `adoUpdateStatus`            | Current ADO update status for this agent step                     |

---

## QA Analysis Summary

The `qaAnalysisSummary` section contains the main QA impact assessment.

It includes:

* `impactedModules`
* `changeType`
* `riskLevel`
* `testingScope`
* `suggestedTestFocus`
* `humanReviewRequired`
* `nextStep`

### Change Type Classification

The agent classifies the requirement into one of the following change types:

```text
New Feature
Enhancement
Bug Fix
Configuration Change
Performance Improvement
Security Update
Unknown
```

### Risk Level Classification

The agent classifies QA risk as:

```text
High
Medium
Low
```

Risk level is determined based on business impact, workflow complexity, affected modules, integration dependency, and testing scope.

High-risk examples include:

* Healthcare workflows
* Scheduling
* Clinical documentation
* Patient-facing workflows
* Authentication
* Security changes
* External system integrations
* End-to-end business-critical workflows

---

## Requirement Quality Analysis

The `requirementQualityAnalysis` section checks whether the requirement is ready for test scenario generation.

It includes:

* `readinessStatus`
* `readinessScore`
* `identifiedGaps`
* `ragChecklistUsed`
* `ragEvidenceUsed`
* `qaLeadActionRequired`
* `approvalRecommendation`
* `qaLeadDecisionStatus`

---

## Local QA/RAG Checklist Context

The agent uses local markdown-based QA knowledge files as lightweight RAG context.

The checklist context may include:

* Definition of Ready
* Acceptance Criteria Checklist
* QA Test Design Standard
* Healthcare Workflow Validation Checklist
* Regression Impact Checklist

The agent retrieves relevant checklist content and uses it to evaluate requirement quality. The response includes evidence fields so the QA lead can understand which checklist sources influenced the readiness decision.

---

## Requirement Gaps Checked

The agent checks for common requirement gaps, including:

* Missing or unclear description
* Missing or weak acceptance criteria
* Missing validation rules
* Missing error messages
* Missing negative scenarios
* Missing edge cases
* Missing non-functional requirements
* Missing dependency or integration details
* Missing audit/logging expectations
* Unclear impacted modules
* Unclear expected behavior
* Unclear pass/fail conditions
* Unclear user role or workflow entry point
* Unclear data setup or preconditions

The agent is designed to avoid only generic gap statements. It attempts to provide requirement-specific gap observations whenever possible.

---

## Readiness Scoring

The agent calculates a readiness score from 0 to 100.

The score starts from 100 and is reduced based on requirement gaps.

Example scoring logic:

| Gap                                                       | Score Impact |
| --------------------------------------------------------- | ------------ |
| Missing requirement description                           | -25          |
| Missing acceptance criteria                               | -30          |
| Missing validation rules                                  | -10          |
| Missing error messages                                    | -10          |
| Missing negative scenarios or edge cases                  | -10          |
| Missing non-functional requirements                       | -5           |
| Missing integration or dependency details                 | -10          |
| Missing audit/logging expectations for critical workflows | -5           |
| Unclear expected behavior or pass/fail condition          | -15          |

The final score cannot be less than 0.

---

## Readiness Status

The agent classifies readiness using the calculated score and critical gaps.

| Score / Condition                 | Status       |
| --------------------------------- | ------------ |
| 85 or higher and no critical gaps | Ready        |
| 60 to 84                          | Needs Review |
| Below 60 or critical gaps present | Not Ready    |

Critical gaps include:

* Missing acceptance criteria
* Missing requirement description
* Unclear expected behavior
* Unclear pass/fail conditions for a high-risk workflow

---

## Human Review Decision

The agent recommends a QA lead decision based on requirement readiness.

| Readiness Status | Human Review Result                                      |
| ---------------- | -------------------------------------------------------- |
| Ready            | Requirement can proceed                                  |
| Needs Review     | QA lead should review before proceeding                  |
| Not Ready        | Clarification should be requested before test generation |

Possible approval recommendations:

```text
Approve
Needs QA Lead Review
Reject and request clarification
```

This supports the human-in-the-loop design of QualityOps QA Console. The agent assists with analysis, but the QA lead remains responsible for final approval and quality decisions.

---

## Azure DevOps Write-back Note

This agent focuses on:

* Requirement fetch
* QA analysis
* RAG-based readiness validation
* Structured output generation

In the full QualityOps workflow, Azure DevOps comment write-back is handled by the separate **QualityOps ADO WriteBack Agent**.

This separation keeps responsibilities clear:

| Agent                      | Responsibility                                  |
| -------------------------- | ----------------------------------------------- |
| Requirement Analysis Agent | Fetch and analyze requirement                   |
| ADO WriteBack Agent        | Write QA analysis comments back to Azure DevOps |

This makes the workflow easier to govern, debug, and extend.

---

## Error Handling

The agent handles common failure scenarios, including:

* Missing requirement ID
* Missing submitted by value
* Missing Azure DevOps configuration
* Azure DevOps authentication failure
* Azure DevOps work item not found
* Unexpected Azure DevOps API errors
* Requirement parsing issues
* Missing local RAG checklist files

When an error occurs, the agent returns structured output instead of failing silently.

Typical error response behavior includes:

* Descriptive `processingStatus`
* `humanReviewRequired` set to true
* `qaLeadNotificationRequired` set to true
* ADO write-back skipped status
* Empty requirement fields where data is not available

---

## Security Notes

Security is important because the agent integrates with Azure DevOps and UiPath cloud configuration.

Rules followed:

* No PAT or secret should be committed to Git.
* `.env` should be used only for local development.
* `.env.example` should contain placeholders only.
* Published cloud jobs should use UiPath Assets or secured configuration.
* The agent should not expose credentials in logs or output.
* The agent should not return authorization headers or internal connection details.
* Error responses should be descriptive but should not leak secrets.

---

## Example Output Structure

```json
{
  "processingStatus": "Requirement fetched and analyzed successfully.",
  "requirementTitle": "Validate end-to-end patient care workflow",
  "requirementDescription": "Requirement description from Azure DevOps",
  "acceptanceCriteria": "Acceptance criteria from Azure DevOps",
  "qaAnalysisSummary": {
    "impactedModules": [
      "Patient Registration",
      "Scheduler",
      "Clinical Documentation"
    ],
    "changeType": "Enhancement",
    "riskLevel": "High",
    "testingScope": [
      "Functional Testing",
      "Regression Testing",
      "Integration Testing",
      "End-to-End Testing"
    ],
    "suggestedTestFocus": [
      "Validate patient registration flow",
      "Validate appointment scheduling",
      "Validate clinical documentation updates"
    ],
    "humanReviewRequired": true,
    "nextStep": "Notify QA Lead for approval"
  },
  "requirementQualityAnalysis": {
    "readinessStatus": "Needs Review",
    "readinessScore": 75,
    "identifiedGaps": [
      "Acceptance criteria should clarify expected validation behavior.",
      "Negative scenarios should be added for invalid or missing patient data."
    ],
    "ragChecklistUsed": [
      "Definition Of Ready",
      "Acceptance Criteria Checklist"
    ],
    "ragEvidenceUsed": [
      {
        "sourceName": "Definition Of Ready",
        "reasonUsed": "Used to evaluate whether the requirement is ready for test design."
      }
    ],
    "qaLeadActionRequired": true,
    "approvalRecommendation": "Needs QA Lead Review",
    "qaLeadDecisionStatus": "Pending QA Lead Approval"
  },
  "qaLeadNotificationRequired": true,
  "adoUpdateStatus": "ADO write-back handled by separate ADO WriteBack Agent."
}
```

---

## Files in This Agent

Typical files in this agent folder:

```text
agent.json
entry-points.json
main.py
rag_knowledge_base/
README.md
```

### `agent.json`

Defines the agent metadata, model settings, schemas, and agent instructions.

### `entry-points.json`

Defines the UiPath entry point schema for inputs, outputs, and graph execution.

### `main.py`

Contains the coded implementation for:

* Azure DevOps requirement fetch
* UiPath asset reading
* Local RAG document loading
* RAG chunking and retrieval
* Prompt construction
* LLM-based QA analysis
* Structured output generation

### `rag_knowledge_base/`

Contains local markdown checklist files used as QA/RAG context.

---

## Role in QualityOps QA Console

The Requirement Analysis Agent helps QualityOps QA Console make requirements test-ready.

It supports the larger workflow:

```text
Requirement Analysis
→ Human Review
→ Test Scenario Generation
→ Test Case Creation
→ Risk-Based Planning
→ Test Manager Sync
→ Automation Mapping
→ Test Result Analysis
→ Failure Triage
→ Bug Creation
→ Final QA Report
```

This agent is important because poor requirement quality can affect every downstream QA activity. By identifying gaps early, the agent helps reduce rework, improve test coverage, and support better release decisions.

---

## Production Extension Ideas

This agent can be extended further with:

* More advanced vector-based RAG retrieval
* Project-specific QA checklist configuration
* Role-based approval routing
* Direct Azure DevOps comment write-back toggle
* Requirement version comparison
* Change impact scoring
* Historical defect correlation
* Domain-specific validation rules
* Multi-project Azure DevOps support
* Audit logging in UiPath Data Service

---

## Summary

The QualityOps Requirement Analysis Agent converts Azure DevOps requirements into structured QA insights.

It improves requirement readiness, identifies gaps early, supports QA lead review, and prepares downstream agents for better test scenario generation.

It demonstrates how UiPath Coded Agents, UiPath Automation Cloud, Azure DevOps, local RAG context, and human-in-the-loop governance can work together to improve enterprise QA workflows.
