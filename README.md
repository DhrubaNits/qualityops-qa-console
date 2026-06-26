# QualityOps QA Console

QualityOps QA Console is an agentic QA orchestration solution built for the UiPath AgentHack challenge under the **Agentic Testing with Test Cloud** track.

The solution uses a **UiPath Coded App built with the TypeScript SDK** as the QA lead control console. It orchestrates multiple **UiPath Coded Agents** running through **UiPath Automation Cloud and UiPath Orchestrator Jobs** to support the complete QA lifecycle.

QualityOps helps QA teams move from requirement to release readiness through requirement analysis, human review, test scenario generation, review memory, Azure DevOps test case creation, risk-based planning, UiPath Test Manager / Test Cloud sync, automation mapping, test result analysis, failure triage, bug creation, final QA report generation, and email delivery.

UiPath Automation Cloud is used as the main **orchestration and governance layer**. External frameworks, LLM reasoning, Azure DevOps APIs, React, TypeScript, Python, and coding-agent-assisted development are used around the UiPath Platform to build a realistic enterprise QA workflow.

## Challenge Track

**Track 3: UiPath Test Cloud**

QualityOps aligns with the UiPath Test Cloud track because it reimagines how software testing is designed, governed, executed, and reported using agentic workflows on UiPath Automation Cloud.

## Business Problem

QA teams spend significant manual effort reading requirements, identifying test scenarios, reviewing coverage, creating test cases, deciding what to execute first, triaging failures, creating bugs, and preparing release reports.

This process is often slow, inconsistent, and difficult to govern at scale.

QualityOps solves this by providing an agentic QA operating console where AI agents assist across the testing lifecycle, while the QA lead remains in control through review and approval gates.

## Solution Overview

QualityOps supports the following end-to-end flow:

1. Requirement Analysis
2. Human Review and Approval
3. Test Scenario Generation
4. QA Review Memory using UiPath Data Service
5. Approved Test Case Creation in Azure DevOps
6. Risk-Based Execution Planning
7. UiPath Test Manager Sync
8. Automation Mapping
9. Test Execution Result Triage
10. Azure DevOps Bug Creation
11. Final QA Report Generation
12. QA Report Email Delivery

## UiPath Platform Components Used

* UiPath Coded App using TypeScript SDK
* UiPath Coded Agents
* UiPath Automation Cloud
* UiPath Orchestrator Jobs
* UiPath Test Manager / UiPath Test Cloud
* UiPath Data Fabric
* UiPath Studio Web
* UiPath Integration Service
* UiPath Test Manager APIs

## External Systems and Tools Used

* Azure DevOps REST APIs
* Azure DevOps Test Plans
* TypeScript
* React
* Vite
* Python
* LangGraph
* LLM reasoning
* Rule-based risk scoring
* UiPath for Coding Agents
* Codex / coding-agent-assisted development
* GitHub

## Architecture

```text
QA Lead
  ↓
UiPath Coded App - QualityOps QA Console
  ↓
UiPath Automation Cloud / UiPath Orchestrator Jobs
  ↓
UiPath Coded Agents
  ↓
Azure DevOps / UiPath Test Manager / UiPath Test Cloud / UiPath Data Service
  ↓
Test Result Analysis / Failure Triage / Bug Creation
  ↓
Final QA Report and Email Communication

```

## Repository Structure

```text
qualityops-qa-console/
│
├── src/
│   ├── App.tsx
│   ├── App.css
│   ├── index.css
│   └── services/
│       └── orchestratorService.ts
│
├── coded-agents/
│   ├── requirement-analysis-agent/
│   ├── ado-writeback-agent/
│   ├── test-scenario-generation-agent/
│   ├── test-case-review-memory-agent/
│   ├── ado-testcase-writeback-agent/
│   ├── risk-based-test-planner-agent/
│   ├── test-manager-writeback-agent/
│   ├── automation-link-agent/
│   ├── test-result-triage-agent/
│   └── final-report-mail-agent/
│
├── docs/
│   ├── screenshots/
│   └── diagrams/
│
├── submission/
├── .env.example
├── README.md
├── LICENSE
├── package.json
└── vite.config.ts
```

## Key Agents

### Requirement Analysis Agent

Analyzes Azure DevOps requirements and identifies impacted modules, change type, risk level, testing scope, and suggested test focus areas.

### Requirement Review / Human Approval

Allows the QA lead to review and approve the requirement analysis before continuing the workflow.

### Test Scenario Generation Agent

Generates meaningful functional, regression, integration, negative, and edge-case test scenarios from the approved requirement analysis.

### Test Case Review Memory Agent

Stores QA approval and rejection decisions in UiPath Data Service so review history can be reused and audited.

### Azure DevOps Test Case WriteBack Agent

Creates only approved test cases in Azure DevOps.

### Risk-Based Test Planner Agent

Ranks generated test scenarios based on risk, priority, test type, and coverage needs.

### Test Manager WriteBack Agent

Syncs generated test cases into UiPath Test Manager / UiPath Test Cloud.

### Automation Link Agent

Maps UiPath automated test packages to UiPath Test Manager test cases.

### Test Result Triage Agent

Analyzes execution results and identifies failures requiring action.

### Final QA Report Agent

Generates a consolidated QA readiness report.

### Final Report Mail Agent

Sends the final QA report by email.

## Human-in-the-Loop Governance

QualityOps keeps the QA lead in control at important decision points:

* Requirement review before test generation
* Approval or rejection of generated test scenarios
* Only approved test cases are created in Azure DevOps
* Review decisions are stored in UiPath Data Service
* Release readiness is calculated based on workflow completion
* Final report is generated after execution and triage

## Setup Instructions

### Prerequisites

* UiPath Automation Cloud access
* UiPath Studio Web access
* UiPath Test Manager project
* UiPath Data Service entity configured
* Azure DevOps project access
* Node.js installed
* UiPath CLI installed
* Access to required UiPath folders and processes

### Install Dependencies

```bash
npm install
```

### Configure Environment

Create a `.env` file using `.env.example` as a template.

Do not commit real environment values, tokens, client secrets, or private tenant details.

```bash
copy .env.example .env
```

Update the `.env` file with your own UiPath tenant, folder, process, and Test Manager values.

### Run Locally

```bash
npm run dev
```

### Build

```bash
npm run build
```

### Push UiPath Coded App

```bash
uip codedapp push
```

After pushing, open UiPath Studio Web and publish the Coded App from UiPath Automation Cloud.

## Demo Flow

The demo shows:

1. Opening the QualityOps QA Console as a UiPath Coded App
2. Running requirement analysis
3. Reviewing and approving the requirement
4. Generating test scenarios
5. Approving selected test scenarios
6. Creating approved test cases in Azure DevOps
7. Generating a risk-based execution plan
8. Syncing test cases to UiPath Test Manager
9. Mapping automation
10. Reviewing execution results
11. Creating Azure DevOps bugs
12. Generating and sending the final QA report

## Coding Agents Usage

This project demonstrates coding-agent-assisted development using **Codex** and **UiPath for Coding Agents** practices during implementation.

Codex was used to help build, debug, and refine:

* React and TypeScript implementation for the UiPath Coded App
* UiPath TypeScript SDK integration
* Dashboard workflow navigation
* Agent payload mapping and response handling
* Orchestrator job integration logic
* Coded App deployment troubleshooting
* README, documentation, and submission preparation

The final solution itself is orchestrated and governed through the UiPath Platform, while Codex was used as a development accelerator. This supports the UiPath AgentHack bonus criteria for demonstrating the use of coding agents during solution development.


## Hackathon Submission Compliance

* **Track:** Agentic Testing with Test Cloud
* **Built during hackathon period:** Yes
* **Runs on UiPath Automation Cloud:** Yes
* **UiPath used as orchestration layer:** Yes
* **Coded App used:** Yes
* **Coded Agents used:** Yes
* **Orchestrator Jobs used:** Yes
* **UiPath Test Manager / Test Cloud used:** Yes
* **UiPath Data Fabric used:** Yes
* **Public GitHub repository:** Yes
* **Coding Agents bonus:** Codex / UiPath for Coding Agents used during development

## Production Potential

QualityOps can be extended for enterprise QA teams by adding:

* Role-based access control
* Multi-project support
* Advanced risk scoring
* Test coverage analytics
* CI/CD pipeline triggers
* Release gate integrations
* More detailed audit history
* Maestro BPMN or Maestro Case as a future enterprise orchestration layer

## License

This project is licensed under the MIT License.
