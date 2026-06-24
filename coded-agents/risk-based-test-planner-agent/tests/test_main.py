import json

from main import Input, main


def test_sample_input_completes_with_expected_coverage():
    payload = {
        "requirementId": "26",
        "submittedBy": "Dhruba",
        "environment": "SQA",
        "requirementTitle": "Validate End-to-End Patient Care Workflow",
        "riskLevel": "High",
        "testingScope": ["Functional", "Integration", "Regression"],
        "suggestedTestFocus": ["Patient creation", "Scheduler", "Documentation"],
        "testScenarios": [
            {
                "scenarioId": "TS-001",
                "scenarioTitle": "Validate end-to-end patient care workflow happy path",
                "priority": "High",
                "testType": "Functional",
                "preconditions": ["Requirement 26 is available for testing"],
                "steps": ["Open workflow", "Create patient", "Schedule appointment"],
                "expectedResult": "Workflow completes successfully",
            }
        ],
    }

    result = main(Input(question=json.dumps(payload)))

    assert result.planningStatus == "Completed"
    assert result.requirementId == "26"
    assert result.recommendedExecutionOrder[0].scenarioId == "TS-001"
    assert result.recommendedExecutionOrder[0].executionType == "Manual + Regression"
    assert result.coverageSummary.functional == 1
    assert result.coverageSummary.total == 1
    assert result.failedScenarios == []


def test_prioritizes_high_risk_negative_and_integration_scenarios():
    payload = {
        "requirementId": "26",
        "riskLevel": "High",
        "testingScope": ["Functional", "Integration", "Regression"],
        "suggestedTestFocus": ["Scheduler"],
        "testScenarios": [
            {
                "scenarioId": "TS-LOW",
                "scenarioTitle": "Validate label rendering",
                "priority": "Low",
                "testType": "Functional",
            },
            {
                "scenarioId": "TS-NEG",
                "scenarioTitle": "Validate negative scheduler conflict handling",
                "priority": "High",
                "testType": "Negative",
            },
            {
                "scenarioId": "TS-INT",
                "scenarioTitle": "Validate Scheduler integration",
                "priority": "High",
                "testType": "Integration",
            },
        ],
    }

    result = main(Input(question=json.dumps(payload)))

    assert [item.scenarioId for item in result.recommendedExecutionOrder] == ["TS-NEG", "TS-INT", "TS-LOW"]
    assert result.coverageSummary.negative == 1
    assert result.coverageSummary.integration == 1
    assert result.coverageSummary.functional == 1


def test_invalid_input_returns_failed_shape():
    result = main(Input(question=json.dumps({"requirementId": "", "testScenarios": []})))

    assert result.planningStatus == "Failed"
    assert result.requirementId == ""
    assert result.recommendedExecutionOrder == []
    assert result.coverageSummary.total == 0
    assert result.releaseRecommendation == ""
    assert result.failedScenarios[0].error == "requirementId is required"
