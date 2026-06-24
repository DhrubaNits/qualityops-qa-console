from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel, Field
from uipath.tracing import traced


class Input(BaseModel):
    question: str = Field(default="", description="JSON string with QA readiness inputs.")


class TestToRun(BaseModel):
    rank: int
    scenarioId: str
    scenarioTitle: str
    priority: str
    testType: str


class Output(BaseModel):
    readinessStatus: str
    requirementId: str
    executionReadinessStatus: str
    recommendedTestSet: str
    executionMode: str
    testsToRunFirst: list[TestToRun]
    blockedReasons: list[str]
    nextAction: str


def _as_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _normalize(value: Any) -> str:
    return str(value or "").strip()


def _invalid(requirement_id: str, reason: str) -> Output:
    return Output(
        readinessStatus="Failed",
        requirementId=requirement_id,
        executionReadinessStatus="Not Ready",
        recommendedTestSet="",
        executionMode="",
        testsToRunFirst=[],
        blockedReasons=[reason],
        nextAction="",
    )


def _select_test_set(risk_level: str, coverage_summary: dict[str, Any]) -> str:
    functional = _as_int(coverage_summary.get("functional"))
    integration = _as_int(coverage_summary.get("integration"))
    negative = _as_int(coverage_summary.get("negative"))
    regression = _as_int(coverage_summary.get("regression"))
    edge_case = _as_int(coverage_summary.get("edgeCase"))
    total = max(_as_int(coverage_summary.get("total")), functional + integration + negative + regression + edge_case)

    if risk_level.lower() == "high" and functional > 0 and integration > 0 and negative > 0:
        return "High Risk Functional + Integration Suite"
    if total > 0 and regression >= max(2, total // 2):
        return "Regression Suite"
    if total > 0 and edge_case > (total / 2):
        return "Exploratory / Edge Case Suite"
    return "Standard QA Validation Suite"


def _select_execution_mode(risk_level: str) -> str:
    match risk_level.lower():
        case "high":
            return "Manual + Automated"
        case "medium":
            return "Automated + QA Review"
        case "low":
            return "Automated"
        case _:
            return "Automated + QA Review"


def _select_tests_to_run_first(recommended_order: list[Any]) -> list[TestToRun]:
    scenarios = [item for item in recommended_order if isinstance(item, dict)]
    high_priority = [item for item in scenarios if _normalize(item.get("priority")).lower() == "high"]
    selected = (high_priority or scenarios)[:5]
    if len(selected) < 3:
        remaining = [item for item in scenarios if item not in selected]
        selected.extend(remaining[: 3 - len(selected)])

    return [
        TestToRun(
            rank=_as_int(item.get("rank")),
            scenarioId=_normalize(item.get("scenarioId")),
            scenarioTitle=_normalize(item.get("scenarioTitle")),
            priority=_normalize(item.get("priority")),
            testType=_normalize(item.get("testType")),
        )
        for item in selected
    ]


def _blocked_reasons(data: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if _normalize(data.get("qaReviewStatus")).lower() != "approved":
        reasons.append("QA Lead approval is required before execution.")
    if _as_int(data.get("testScenarioCount")) <= 0:
        reasons.append("Test scenarios have not been generated.")
    if _as_int(data.get("adoTestCaseCreatedCount")) <= 0:
        reasons.append("ADO test cases have not been created.")
    if _normalize(data.get("riskPlanningStatus")).lower() != "completed":
        reasons.append("Risk-based execution planning must be completed before execution.")
    return reasons


def _next_action(test_set: str) -> str:
    if test_set == "High Risk Functional + Integration Suite":
        return "Trigger high-risk functional and integration tests in UiPath Test Cloud."
    if test_set == "Regression Suite":
        return "Trigger the regression suite in UiPath Test Cloud."
    if test_set == "Exploratory / Edge Case Suite":
        return "Trigger exploratory and edge case validation in UiPath Test Cloud."
    return "Trigger the standard QA validation suite in UiPath Test Cloud."


@traced()
async def main(input: Input) -> Output:
    try:
        data = json.loads(input.question)
    except json.JSONDecodeError:
        return _invalid("", "Invalid input: question must be a valid JSON string.")

    if not isinstance(data, dict):
        return _invalid("", "Invalid input: question must contain a JSON object.")

    requirement_id = _normalize(data.get("requirementId"))
    if not requirement_id:
        return _invalid("", "Invalid input: requirementId is required.")

    reasons = _blocked_reasons(data)
    if reasons:
        return Output(
            readinessStatus="Completed",
            requirementId=requirement_id,
            executionReadinessStatus="Not Ready",
            recommendedTestSet="",
            executionMode="",
            testsToRunFirst=[],
            blockedReasons=reasons,
            nextAction="Complete the blocked items before triggering Test Cloud execution.",
        )

    risk_level = _normalize(data.get("riskLevel"))
    coverage_summary = data.get("coverageSummary") if isinstance(data.get("coverageSummary"), dict) else {}
    recommended_order = (
        data.get("recommendedExecutionOrder")
        if isinstance(data.get("recommendedExecutionOrder"), list)
        else []
    )
    test_set = _select_test_set(risk_level, coverage_summary)

    return Output(
        readinessStatus="Completed",
        requirementId=requirement_id,
        executionReadinessStatus="Ready",
        recommendedTestSet=test_set,
        executionMode=_select_execution_mode(risk_level),
        testsToRunFirst=_select_tests_to_run_first(recommended_order),
        blockedReasons=[],
        nextAction=_next_action(test_set),
    )
