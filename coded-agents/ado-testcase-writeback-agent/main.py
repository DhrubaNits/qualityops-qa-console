from __future__ import annotations

import base64
import html
import json
import os
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

try:
    from pydantic import BaseModel, Field
except ImportError:  # Keeps local smoke tests runnable before dependencies are installed.
    class BaseModel:
        def __init__(self, **data: Any) -> None:
            annotations = getattr(self.__class__, "__annotations__", {})
            for name in annotations:
                setattr(self, name, data.get(name, getattr(self.__class__, name, None)))

        def model_dump(self) -> dict[str, Any]:
            return dict(self.__dict__)

    def Field(default_factory=None, default=None):  # type: ignore[no-untyped-def]
        if default_factory is not None:
            return default_factory()
        return default

try:
    from uipath.tracing import traced
except ImportError:
    def traced(*_args: Any, **_kwargs: Any):  # type: ignore[no-untyped-def]
        def decorator(func):
            return func

        return decorator


class Input(BaseModel):
    question: str


class CreatedTestCase(BaseModel):
    scenarioId: str
    testCaseId: int
    title: str
    url: str


class FailedScenario(BaseModel):
    scenarioId: str
    error: str


class Output(BaseModel):
    writeBackStatus: str
    requirementId: str = ""
    createdTestCases: list[CreatedTestCase] = Field(default_factory=list)
    failedScenarios: list[FailedScenario] = Field(default_factory=list)


ADO_CONFIG_NAMES = ("ADO_ORGANIZATION", "ADO_PROJECT", "ADO_PAT")


def _failed(requirement_id: str, failures: list[FailedScenario]) -> Output:
    return Output(
        writeBackStatus="Failed",
        requirementId=requirement_id,
        createdTestCases=[],
        failedScenarios=failures,
    )


def _asset_to_string(asset: Any) -> str:
    for attr in (
        "value",
        "string_value",
        "text_value",
        "secret_value",
        "credential_password",
        "password",
    ):
        value = getattr(asset, attr, None)
        if value is not None:
            return str(value).strip()

    if hasattr(asset, "model_dump"):
        dumped = asset.model_dump()
        if isinstance(dumped, dict):
            for key in (
                "value",
                "Value",
                "string_value",
                "text_value",
                "secret_value",
                "credential_password",
                "password",
            ):
                value = dumped.get(key)
                if value is not None:
                    return str(value).strip()

    if isinstance(asset, dict):
        for key in (
            "value",
            "Value",
            "string_value",
            "text_value",
            "secret_value",
            "credential_password",
            "password",
        ):
            value = asset.get(key)
            if value is not None:
                return str(value).strip()

    return ""


def _read_asset_config() -> dict[str, str]:
    try:
        from uipath.platform import UiPath

        sdk = UiPath()
    except Exception:
        return {}

    values: dict[str, str] = {}

    try:
        values["ADO_ORGANIZATION"] = _asset_to_string(sdk.assets.retrieve("ADO_ORGANIZATION"))
    except Exception:
        pass

    try:
        values["ADO_PROJECT"] = _asset_to_string(sdk.assets.retrieve("ADO_PROJECT"))
    except Exception:
        pass

    try:
        values["ADO_PAT"] = _asset_to_string(sdk.assets.retrieve("ADO_PAT"))
    except Exception:
        pass

    return values


def _resolve_ado_config() -> tuple[dict[str, str], list[str]]:
    asset_values = _read_asset_config()
    resolved: dict[str, str] = {}

    for name in ADO_CONFIG_NAMES:
        resolved[name] = asset_values.get(name, "").strip() or os.getenv(name, "").strip()

    missing = [name for name, value in resolved.items() if not value]
    return resolved, missing


def _read_question(question: str) -> tuple[dict[str, Any] | None, Output | None]:
    try:
        payload = json.loads(question)
    except json.JSONDecodeError as exc:
        return None, _failed("", [FailedScenario(scenarioId="", error=f"Invalid JSON: {exc.msg}")])

    if not isinstance(payload, dict):
        return None, _failed("", [FailedScenario(scenarioId="", error="Input JSON must be an object")])

    requirement_id = str(payload.get("requirementId", "")).strip()
    scenarios = payload.get("testScenarios")
    failures: list[FailedScenario] = []

    if not requirement_id:
        failures.append(FailedScenario(scenarioId="", error="requirementId is required"))
    if not isinstance(scenarios, list) or not scenarios:
        failures.append(FailedScenario(scenarioId="", error="testScenarios must be a non-empty array"))

    if failures:
        return None, _failed(requirement_id, failures)

    return payload, None


def _priority_value(priority: Any) -> int | None:
    priority_map = {"critical": 1, "high": 1, "medium": 2, "normal": 2, "low": 3}
    if isinstance(priority, int):
        return priority
    if isinstance(priority, str):
        return priority_map.get(priority.strip().lower())
    return None


def _clean_text(value: Any, max_length: int = 1000) -> str:
    text = str(value or "")
    text = re.sub(r"\s+", " ", text).strip()
    return text[:max_length].strip()


def _string_list(value: Any, max_items: int = 10, max_length: int = 700) -> list[str]:
    if not isinstance(value, list):
        return []

    cleaned: list[str] = []
    for item in value[:max_items]:
        if isinstance(item, dict):
            action = item.get("action") or item.get("step") or item.get("description") or item.get("name")
            expected = item.get("expectedResult") or item.get("expected") or ""
            text = _clean_text(action, max_length)
            if expected:
                text = f"{text} Expected: {_clean_text(expected, max_length)}"
        else:
            text = _clean_text(item, max_length)

        if text:
            cleaned.append(text)

    return cleaned


def normalize_step(step: Any) -> tuple[str, str]:
    if isinstance(step, dict):
        action = (
            step.get("action")
            or step.get("step")
            or step.get("description")
            or ""
        )

        expected = (
            step.get("expectedResult")
            or step.get("expected_result")
            or step.get("expected")
            or step.get("result")
            or ""
        )

        return _clean_text(action, 700), _clean_text(expected, 700)

    text = str(step or "").strip()

    markers = [
        " Expected Result:",
        " Expected result:",
        " expected result:",
        " Expected:",
        " expected:",
    ]

    for marker in markers:
        if marker in text:
            parts = text.split(marker, 1)
            action = parts[0].strip()
            expected = parts[1].strip()
            return _clean_text(action, 700), _clean_text(expected, 700)

    return _clean_text(text, 700), ""


def _step_list(value: Any, max_items: int = 10) -> list[Any]:
    if not isinstance(value, list):
        return []

    steps: list[Any] = []
    for item in value[:max_items]:
        action, expected = normalize_step(item)
        if not action and not expected:
            continue

        if isinstance(item, dict):
            steps.append({"action": action, "expectedResult": expected})
        elif expected:
            steps.append({"action": action, "expectedResult": expected})
        else:
            steps.append(action)

    return steps


def _normalize_scenario(raw: dict[str, Any], index: int) -> dict[str, Any]:
    scenario_id = _clean_text(
        raw.get("scenarioId") or raw.get("testCaseId") or raw.get("id") or f"TS-{index:03d}",
        40,
    )

    title = _clean_text(
        raw.get("scenarioTitle") or raw.get("title") or raw.get("name") or f"Generated Test Scenario {index}",
        200,
    )

    test_type = _clean_text(raw.get("testType") or raw.get("type") or "Functional", 50)
    priority = raw.get("priority") or "High"

    preconditions = _string_list(raw.get("preconditions"), max_items=6, max_length=400)
    steps = _step_list(raw.get("steps"), max_items=10)

    expected_result = _clean_text(
        raw.get("expectedResult") or raw.get("expected") or raw.get("expectedOutcome") or "",
        1500,
    )

    if not steps:
        steps = ["Validate the generated QualityOps test scenario."]

    if not expected_result:
        expected_result = "The system behavior matches the expected outcome described by the generated QualityOps scenario."

    return {
        **raw,
        "scenarioId": scenario_id,
        "scenarioTitle": title,
        "title": title,
        "testCaseId": scenario_id,
        "testType": test_type,
        "type": test_type,
        "priority": priority,
        "preconditions": preconditions,
        "steps": steps,
        "expectedResult": expected_result,
    }


def _scenario_title(scenario: dict[str, Any]) -> str:
    scenario_id = str(scenario.get("scenarioId", "")).strip()
    scenario_title = str(
        scenario.get("scenarioTitle")
        or scenario.get("title")
        or scenario.get("name")
        or ""
    ).strip()
    scenario_title = re.sub(r"\b(\w+)(\s+\1\b)+", r"\1", scenario_title, flags=re.IGNORECASE)
    if scenario_id and scenario_title:
        return f"{scenario_id} - {scenario_title}"
    return scenario_title or scenario_id or "Generated test scenario"


def _description(payload: dict[str, Any], scenario: dict[str, Any]) -> str:
    lines = [
        f"Generated by QualityOps for requirement {payload.get('requirementId')}.",
        f"Submitted by: {payload.get('submittedBy', '')}",
        f"Environment: {payload.get('environment', '')}",
        "",
        "Preconditions:",
    ]
    lines.extend(f"- {item}" for item in scenario.get("preconditions", []) if str(item).strip())
    lines.extend(["", "Steps:"])
    lines.extend(f"{index}. {step}" for index, step in enumerate(scenario.get("steps", []), start=1) if str(step).strip())
    lines.extend(["", "Expected Result:", str(scenario.get("expectedResult", "")).strip()])
    return "\n".join(lines)


def _test_steps_xml(scenario: dict[str, Any]) -> str:
    steps = [step for step in scenario.get("steps", []) if normalize_step(step)[0] or normalize_step(step)[1]]
    expected_result = str(scenario.get("expectedResult", "")).strip()

    if not steps:
        steps = ["Validate scenario"]

    last = len(steps)
    step_nodes = []
    for index, step in enumerate(steps, start=1):
        action, expected = normalize_step(step)
        if not expected:
            expected = expected_result
        step_nodes.append(
            f'<step id="{index}" type="ValidateStep">'
            f'<parameterizedString isformatted="true">{html.escape(action)}</parameterizedString>'
            f'<parameterizedString isformatted="true">{html.escape(expected)}</parameterizedString>'
            "<description/>"
            "</step>"
        )

    return f'<steps id="0" last="{last}">' + "".join(step_nodes) + "</steps>"


def _work_item_url(organization: str, project: str, work_item_id: str) -> str:
    return (
        f"https://dev.azure.com/{quote(organization, safe='')}/"
        f"{quote(project, safe='')}/_apis/wit/workItems/{quote(work_item_id, safe='')}"
    )


def _create_test_case(
    organization: str,
    project: str,
    pat: str,
    requirement_id: str,
    payload: dict[str, Any],
    scenario: dict[str, Any],
) -> dict[str, Any]:
    scenario_id = str(scenario.get("scenarioId", "")).strip() or "UNKNOWN"
    title = _scenario_title(scenario)
    test_type = str(scenario.get("testType", "")).strip()
    tags = "; ".join(tag for tag in ["QualityOps", "AI Generated", test_type] if tag)
    parent_url = _work_item_url(organization, project, requirement_id)
    endpoint = (
        f"https://dev.azure.com/{quote(organization, safe='')}/"
        f"{quote(project, safe='')}/_apis/wit/workitems/$Test%20Case?api-version=7.1"
    )

    patch_document: list[dict[str, Any]] = [
        {"op": "add", "path": "/fields/System.Title", "value": title},
        {"op": "add", "path": "/fields/System.Description", "value": _description(payload, scenario)},
        {"op": "add", "path": "/fields/System.Tags", "value": tags},
        {"op": "add", "path": "/fields/Microsoft.VSTS.TCM.Steps", "value": _test_steps_xml(scenario)},
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": parent_url,
                "attributes": {"comment": "Linked to source User Story by QualityOps"},
            },
        },
    ]

    priority = _priority_value(scenario.get("priority"))
    if priority is not None:
        patch_document.insert(
            2,
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.Common.Priority",
                "value": priority,
            },
        )

    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
    request = Request(
        endpoint,
        data=json.dumps(patch_document).encode("utf-8"),
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json-patch+json",
            "Accept": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=30) as response:
            response_payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Azure DevOps API returned HTTP {exc.code}: {detail}") from exc
    except URLError as exc:
        raise RuntimeError(f"Azure DevOps API request failed: {exc.reason}") from exc

    test_case_id = int(response_payload["id"])
    return {
        "scenarioId": scenario_id,
        "testCaseId": test_case_id,
        "title": title,
        "url": response_payload.get("url", _work_item_url(organization, project, str(test_case_id))),
    }


@traced(name="qualityops_ado_testcase_writeback", span_type="tool")
async def main(input: Input) -> Output:
    payload, validation_error = _read_question(input.question)
    if validation_error is not None:
        return validation_error

    assert payload is not None
    requirement_id = str(payload["requirementId"]).strip()
    print(
        "ADO Test Case WriteBack payload parsed",
        {
            "requirementId": requirement_id,
            "scenarioCount": len(payload.get("testScenarios", [])),
        },
    )

    config, missing = _resolve_ado_config()
    organization = config["ADO_ORGANIZATION"]
    project = config["ADO_PROJECT"]
    pat = config["ADO_PAT"]

    if missing:
        return _failed(
            requirement_id,
            [
                FailedScenario(
                    scenarioId="",
                    error=(
                        "Missing required configuration values: "
                        f"{', '.join(missing)}. Configure them as UiPath Orchestrator Assets "
                        "or environment variables for local testing."
                    ),
                )
            ],
        )

    created: list[CreatedTestCase] = []
    failed: list[FailedScenario] = []

    for scenario in payload["testScenarios"]:
        if not isinstance(scenario, dict):
            failed.append(FailedScenario(scenarioId="", error="Scenario must be an object"))
            continue

        scenario = _normalize_scenario(scenario, len(created) + len(failed) + 1)
        scenario_id = str(scenario.get("scenarioId", "")).strip()
        if not scenario_id or not str(scenario.get("scenarioTitle", "")).strip():
            failed.append(
                FailedScenario(
                    scenarioId=scenario_id,
                    error="Unable to normalize scenarioId or scenarioTitle",
                )
            )
            continue

        try:
            print(
                "Creating ADO Test Case",
                {
                    "scenarioId": scenario_id,
                    "title": scenario.get("scenarioTitle", ""),
                },
            )
            created.append(
                CreatedTestCase(
                    **_create_test_case(organization, project, pat, requirement_id, payload, scenario)
                )
            )
        except Exception as exc:
            failed.append(FailedScenario(scenarioId=scenario_id, error=str(exc)))

    return Output(
        writeBackStatus="Completed" if not failed else "Failed",
        requirementId=requirement_id,
        createdTestCases=created,
        failedScenarios=failed,
    )
