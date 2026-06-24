from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field


class Input(BaseModel):
    question: str = ""


class FailedScenario(BaseModel):
    scenarioId: str = ""
    error: str = ""


class RecommendedScenario(BaseModel):
    rank: int = 0
    scenarioId: str = ""
    scenarioTitle: str = ""
    priority: str = ""
    testType: str = ""
    executionType: str = ""
    riskReason: str = ""


class CoverageSummary(BaseModel):
    functional: int = 0
    negative: int = 0
    integration: int = 0
    regression: int = 0
    edgeCase: int = 0
    total: int = 0


class Output(BaseModel):
    planningStatus: Literal["Completed", "Failed"] = "Completed"
    requirementId: str = ""
    recommendedExecutionOrder: list[RecommendedScenario] = Field(default_factory=list)
    coverageSummary: CoverageSummary = Field(default_factory=CoverageSummary)
    releaseRecommendation: str = ""
    failedScenarios: list[FailedScenario] = Field(default_factory=list)


TYPE_ALIASES = {
    "functional": "functional",
    "integration": "integration",
    "regression": "regression",
    "negative": "negative",
    "edge": "edgeCase",
    "edgecase": "edgeCase",
    "edge case": "edgeCase",
}

PRIORITY_SCORE = {
    "critical": 40,
    "high": 30,
    "medium": 20,
    "low": 10,
}

RISK_SCORE = {
    "critical": 50,
    "high": 40,
    "medium": 25,
    "low": 10,
}

TYPE_SCORE = {
    "negative": 35,
    "functional": 30,
    "integration": 28,
    "regression": 24,
    "edgeCase": 18,
}


def main(input: Input) -> Output:
    try:
        payload = json.loads(input.question or "")
    except json.JSONDecodeError as exc:
        return failed_output("", f"question must be valid JSON: {exc.msg}")

    requirement_id = str(payload.get("requirementId", "")).strip()
    scenarios = payload.get("testScenarios")

    if not requirement_id:
        return failed_output("", "requirementId is required")
    if not isinstance(scenarios, list) or not scenarios:
        return failed_output(requirement_id, "testScenarios must be a non-empty array")

    invalid = validate_scenarios(scenarios)
    if invalid:
        return Output(
            planningStatus="Failed",
            requirementId=requirement_id,
            failedScenarios=invalid,
        )

    risk_level = str(payload.get("riskLevel", "")).strip()
    testing_scope = normalize_scope(payload.get("testingScope", []))
    focus_terms = [str(item).lower() for item in payload.get("suggestedTestFocus", []) if str(item).strip()]

    ranked = sorted(
        enumerate(scenarios),
        key=lambda item: scenario_sort_key(item[1], item[0], risk_level, testing_scope, focus_terms),
    )

    recommended = [
        RecommendedScenario(
            rank=rank,
            scenarioId=str(scenario["scenarioId"]),
            scenarioTitle=str(scenario["scenarioTitle"]),
            priority=str(scenario.get("priority", "")),
            testType=str(scenario.get("testType", "")),
            executionType=execution_type(str(scenario.get("testType", "")), testing_scope),
            riskReason=risk_reason(scenario, risk_level, focus_terms),
        )
        for rank, (_, scenario) in enumerate(ranked, start=1)
    ]

    return Output(
        planningStatus="Completed",
        requirementId=requirement_id,
        recommendedExecutionOrder=recommended,
        coverageSummary=coverage_summary(scenarios),
        releaseRecommendation=release_recommendation(risk_level, testing_scope, scenarios),
        failedScenarios=[],
    )


def failed_output(requirement_id: str, error: str) -> Output:
    return Output(
        planningStatus="Failed",
        requirementId=requirement_id,
        failedScenarios=[FailedScenario(error=error)],
    )


def validate_scenarios(scenarios: list[Any]) -> list[FailedScenario]:
    failed: list[FailedScenario] = []
    for index, scenario in enumerate(scenarios, start=1):
        if not isinstance(scenario, dict):
            failed.append(FailedScenario(error=f"testScenarios[{index}] must be an object"))
            continue

        scenario_id = str(scenario.get("scenarioId", "")).strip()
        if not scenario_id:
            failed.append(FailedScenario(error=f"testScenarios[{index}].scenarioId is required"))
        if not str(scenario.get("scenarioTitle", "")).strip():
            failed.append(FailedScenario(scenarioId=scenario_id, error="scenarioTitle is required"))
        if not str(scenario.get("testType", "")).strip():
            failed.append(FailedScenario(scenarioId=scenario_id, error="testType is required"))
    return failed


def scenario_sort_key(
    scenario: dict[str, Any],
    original_index: int,
    risk_level: str,
    testing_scope: set[str],
    focus_terms: list[str],
) -> tuple[int, int]:
    score = scenario_score(scenario, risk_level, testing_scope, focus_terms)
    return (-score, original_index)


def scenario_score(
    scenario: dict[str, Any],
    risk_level: str,
    testing_scope: set[str],
    focus_terms: list[str],
) -> int:
    test_type = normalize_test_type(str(scenario.get("testType", "")))
    title = str(scenario.get("scenarioTitle", "")).lower()
    steps = " ".join(str(step).lower() for step in scenario.get("steps", []))

    score = RISK_SCORE.get(risk_level.lower(), 0)
    score += PRIORITY_SCORE.get(str(scenario.get("priority", "")).lower(), 0)
    score += TYPE_SCORE.get(test_type, 0)

    if test_type in testing_scope:
        score += 15
    if risk_level.lower() in {"critical", "high"} and test_type in {"functional", "integration", "regression", "negative"}:
        score += 20
    if "negative" in title:
        score += 16
    if any(term in title or term in steps for term in focus_terms):
        score += 10

    return score


def normalize_scope(scope: Any) -> set[str]:
    if not isinstance(scope, list):
        return set()
    return {normalize_test_type(str(item)) for item in scope}


def normalize_test_type(test_type: str) -> str:
    cleaned = " ".join(test_type.strip().lower().replace("-", " ").replace("_", " ").split())
    return TYPE_ALIASES.get(cleaned, cleaned)


def coverage_summary(scenarios: list[dict[str, Any]]) -> CoverageSummary:
    summary = CoverageSummary(total=len(scenarios))
    for scenario in scenarios:
        test_type = normalize_test_type(str(scenario.get("testType", "")))
        if test_type == "functional":
            summary.functional += 1
        elif test_type == "negative":
            summary.negative += 1
        elif test_type == "integration":
            summary.integration += 1
        elif test_type == "regression":
            summary.regression += 1
        elif test_type == "edgeCase":
            summary.edgeCase += 1
    return summary


def execution_type(test_type: str, testing_scope: set[str]) -> str:
    normalized = normalize_test_type(test_type)
    if normalized == "regression" or "regression" in testing_scope:
        return "Manual + Regression"
    if normalized == "integration":
        return "Manual + Integration"
    if normalized == "negative":
        return "Manual + Negative"
    return "Manual"


def risk_reason(scenario: dict[str, Any], risk_level: str, focus_terms: list[str]) -> str:
    test_type = normalize_test_type(str(scenario.get("testType", "")))
    title = str(scenario.get("scenarioTitle", "")).lower()
    steps = " ".join(str(step).lower() for step in scenario.get("steps", []))

    reasons: list[str] = []
    if risk_level.lower() in {"critical", "high"}:
        reasons.append(f"Covers {risk_level.lower()}-risk requirement")
    if test_type in {"functional", "integration", "regression", "negative"}:
        reasons.append(f"prioritizes {readable_type(test_type)} validation")
    if any(term in title or term in steps for term in focus_terms):
        reasons.append("aligns with suggested test focus")
    if not reasons:
        reasons.append("Provides additional coverage for the requirement")

    return "; ".join(reasons).capitalize() + "."


def readable_type(test_type: str) -> str:
    return "edge case" if test_type == "edgeCase" else test_type


def release_recommendation(risk_level: str, testing_scope: set[str], scenarios: list[dict[str, Any]]) -> str:
    available_types = {normalize_test_type(str(scenario.get("testType", ""))) for scenario in scenarios}
    priority_types = [name for name in ["functional", "integration", "negative", "regression"] if name in available_types]

    if risk_level.lower() in {"critical", "high"}:
        has_integration = "integration" in testing_scope or "integration" in available_types
        has_negative = "negative" in available_types
        if has_integration and has_negative:
            return "Run high-risk functional, integration, and negative tests first before regression execution."
        if has_integration:
            return "Run high-risk functional and integration tests first before regression execution."
        if has_negative:
            return "Run high-risk functional and negative tests first before regression execution."
        return "Run high-risk functional tests first before regression execution."
    if priority_types:
        return f"Run {', '.join(priority_types)} tests before lower-priority exploratory coverage."
    return "Run the recommended order and confirm coverage gaps before release sign-off."
