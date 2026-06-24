import json

import pytest

from main import Input, main


@pytest.mark.asyncio
async def test_ready_high_risk_functional_integration_suite():
    payload = {
        "requirementId": "26",
        "submittedBy": "Dhruba",
        "environment": "SQA",
        "requirementTitle": "Validate End-to-End Patient Care Workflow",
        "riskLevel": "High",
        "qaReviewStatus": "Approved",
        "testScenarioCount": 8,
        "adoTestCaseCreatedCount": 8,
        "riskPlanningStatus": "Completed",
        "recommendedExecutionOrder": [
            {
                "rank": 1,
                "scenarioId": "TS-001",
                "scenarioTitle": "Validate End-to-End Patient Care Workflow happy path",
                "priority": "High",
                "testType": "Functional",
                "executionType": "Manual",
                "riskReason": "Covers high-risk patient workflow.",
            }
        ],
        "coverageSummary": {
            "functional": 4,
            "negative": 1,
            "integration": 1,
            "regression": 1,
            "edgeCase": 1,
            "total": 8,
        },
    }

    result = await main(Input(question=json.dumps(payload)))

    assert result.readinessStatus == "Completed"
    assert result.requirementId == "26"
    assert result.executionReadinessStatus == "Ready"
    assert result.recommendedTestSet == "High Risk Functional + Integration Suite"
    assert result.executionMode == "Manual + Automated"
    assert result.testsToRunFirst[0].scenarioId == "TS-001"
    assert result.blockedReasons == []
    assert result.nextAction == "Trigger high-risk functional and integration tests in UiPath Test Cloud."


@pytest.mark.asyncio
async def test_not_ready_lists_blocked_reasons():
    payload = {
        "requirementId": "26",
        "riskLevel": "High",
        "qaReviewStatus": "Pending",
        "testScenarioCount": 8,
        "adoTestCaseCreatedCount": 0,
        "riskPlanningStatus": "Completed",
        "coverageSummary": {},
        "recommendedExecutionOrder": [],
    }

    result = await main(Input(question=json.dumps(payload)))

    assert result.readinessStatus == "Completed"
    assert result.executionReadinessStatus == "Not Ready"
    assert result.recommendedTestSet == ""
    assert result.executionMode == ""
    assert result.testsToRunFirst == []
    assert result.blockedReasons == [
        "QA Lead approval is required before execution.",
        "ADO test cases have not been created.",
    ]
    assert result.nextAction == "Complete the blocked items before triggering Test Cloud execution."


@pytest.mark.asyncio
async def test_invalid_missing_requirement_id():
    payload = {"qaReviewStatus": "Approved"}

    result = await main(Input(question=json.dumps(payload)))

    assert result.readinessStatus == "Failed"
    assert result.requirementId == ""
    assert result.executionReadinessStatus == "Not Ready"
    assert result.recommendedTestSet == ""
    assert result.executionMode == ""
    assert result.testsToRunFirst == []
    assert result.blockedReasons == ["Invalid input: requirementId is required."]
    assert result.nextAction == ""


@pytest.mark.asyncio
async def test_medium_risk_regression_suite():
    payload = {
        "requirementId": "27",
        "riskLevel": "Medium",
        "qaReviewStatus": "Approved",
        "testScenarioCount": 6,
        "adoTestCaseCreatedCount": 6,
        "riskPlanningStatus": "Completed",
        "coverageSummary": {
            "functional": 1,
            "negative": 0,
            "integration": 0,
            "regression": 4,
            "edgeCase": 1,
            "total": 6,
        },
        "recommendedExecutionOrder": [
            {"rank": 1, "scenarioId": "TS-001", "scenarioTitle": "Regression A", "priority": "Medium", "testType": "Regression"},
            {"rank": 2, "scenarioId": "TS-002", "scenarioTitle": "Regression B", "priority": "High", "testType": "Regression"},
            {"rank": 3, "scenarioId": "TS-003", "scenarioTitle": "Regression C", "priority": "Low", "testType": "Regression"},
        ],
    }

    result = await main(Input(question=json.dumps(payload)))

    assert result.executionReadinessStatus == "Ready"
    assert result.recommendedTestSet == "Regression Suite"
    assert result.executionMode == "Automated + QA Review"
    assert [test.scenarioId for test in result.testsToRunFirst] == ["TS-002", "TS-001", "TS-003"]
