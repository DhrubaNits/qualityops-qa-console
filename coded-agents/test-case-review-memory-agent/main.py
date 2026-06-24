import json
import os
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict
from urllib.parse import quote

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from uipath.platform import UiPath
from uipath.platform.common import Endpoint


DATA_SERVICE_ENTITY_NAME = os.getenv(
    "QUALITYOPS_REVIEW_MEMORY_ENTITY_NAME",
    "QATestReviewMemory",
)
MEMORY_FIELDS = [
    "RequirementId",
    "ScenarioKey",
    "ScenarioTitle",
    "ReviewStatus",
    "ReviewComment",
    "ReviewedBy",
    "ReviewedAt",
    "ScenarioJson",
    "StepsJson",
    "CreatedAdoTestCaseId",
    "CreatedAdoUrl",
    "Source",
    "UpdatedAt",
]


class GraphInput(BaseModel):
    question: str = Field(description="JSON string containing the requested memory operation.")


class GraphOutput(BaseModel):
    status: str
    operation: str
    message: str
    createdCount: int = 0
    updatedCount: int = 0
    failedCount: int = 0
    entityName: str = DATA_SERVICE_ENTITY_NAME
    dataServicePathUsed: str = ""
    requirementId: str | None = None
    records: list[dict[str, Any]] = Field(default_factory=list)
    failures: list[dict[str, Any]] = Field(default_factory=list)


class GraphState(TypedDict, total=False):
    question: str
    status: str
    operation: str
    message: str
    createdCount: int
    updatedCount: int
    failedCount: int
    entityName: str
    dataServicePathUsed: str
    requirementId: str | None
    records: list[dict[str, Any]]
    failures: list[dict[str, Any]]


class DataServiceRequestError(Exception):
    def __init__(self, path: str, original: Exception) -> None:
        self.path = path
        self.original = original
        super().__init__(str(original))


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), default=str)


def _first_present(source: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None:
            return value
    return default


def _requirement_id(payload: dict[str, Any]) -> str:
    return str(
        payload.get("requirementId")
        or payload.get("requirement_id")
        or payload.get("RequirementId")
        or ""
    ).strip()


def _data_service_path(action: Literal["query", "insert", "update"], record_id: str | None = None) -> str:
    entity_name = quote(DATA_SERVICE_ENTITY_NAME, safe="")
    if action == "update":
        if not record_id:
            raise ValueError("record_id is required for update.")
        return f"/datafabric_/api/EntityService/{entity_name}({quote(record_id, safe='')})/update"
    return f"/datafabric_/api/EntityService/{entity_name}/{action}"


def _query_body(**field_values: str) -> dict[str, Any]:
    return {
        "filterGroup": {
            "logicalOperator": 0,
            "queryFilters": [
                {
                    "fieldName": field_name,
                    "operator": "=",
                    "value": value,
                }
                for field_name, value in field_values.items()
            ],
        }
    }


def _format_error(exc: Exception) -> str:
    message = str(exc.original if isinstance(exc, DataServiceRequestError) else exc)
    invalid_entity_text = f"The value '{DATA_SERVICE_ENTITY_NAME}' is not valid"
    if invalid_entity_text in message:
        return (
            f"Entity name '{DATA_SERVICE_ENTITY_NAME}' was not accepted by UiPath Data Service. "
            "Check Manage Entity -> Name, not Display Name, and ensure the process runs in the same folder "
            "or has Data Service permission."
        )
    return message


def _error_path(exc: Exception) -> str:
    if isinstance(exc, DataServiceRequestError):
        return exc.path
    return ""


def _finalize_batch_response(response: dict[str, Any], success_message: str) -> dict[str, Any]:
    failure_messages = [failure.get("message") for failure in response["failures"] if failure.get("message")]
    entity_failure = next(
        (
            message
            for message in failure_messages
            if message.startswith(f"Entity name '{DATA_SERVICE_ENTITY_NAME}'")
        ),
        None,
    )

    if response["failedCount"] == 0:
        response["status"] = "Success"
        response["message"] = success_message
    elif response["createdCount"] == 0 and response["updatedCount"] == 0:
        response["status"] = "Failed"
        response["message"] = entity_failure or success_message
    else:
        response["status"] = "PartialSuccess"
        response["message"] = entity_failure or success_message
    return response


def _record_to_dict(record: Any) -> dict[str, Any]:
    if isinstance(record, dict):
        data = dict(record)
    elif hasattr(record, "model_dump"):
        data = record.model_dump(by_alias=True, exclude_none=False)
    elif hasattr(record, "dict"):
        data = record.dict()
    else:
        data = dict(getattr(record, "__dict__", {}))

    fields = data.get("Fields")
    if isinstance(fields, dict):
        data.update(fields)

    record_id = data.get("Id") or data.get("id")
    result: dict[str, Any] = {}
    if record_id:
        result["Id"] = record_id
    for field in MEMORY_FIELDS:
        if field in data:
            result[field] = data[field]
    return result


def _empty_response(operation: str = "UNKNOWN", status: Literal["Success", "Failed", "PartialSuccess"] = "Success") -> dict[str, Any]:
    return {
        "status": status,
        "operation": operation,
        "message": "",
        "createdCount": 0,
        "updatedCount": 0,
        "failedCount": 0,
        "entityName": DATA_SERVICE_ENTITY_NAME,
        "dataServicePathUsed": "",
        "requirementId": None,
        "records": [],
        "failures": [],
    }


async def _data_service_request(sdk: UiPath, path: str, body: dict[str, Any]) -> Any:
    try:
        response = await sdk.entities._data.request_async("POST", Endpoint(path), json=body)
        return response.json() if response.content else {}
    except Exception as exc:
        raise DataServiceRequestError(path, exc) from exc


async def _query_records(sdk: UiPath, **field_values: str) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    start = 0
    limit = 100

    while True:
        path = _data_service_path("query")
        body = _query_body(**field_values)
        body["start"] = start
        body["limit"] = limit
        page = await _data_service_request(sdk, path, body)

        page_records = (
            page.get("value")
            or page.get("items")
            or page.get("records")
            or page.get("Records")
            or []
        )
        records.extend(_record_to_dict(record) for record in page_records)

        total_count = page.get("@odata.count") or page.get("totalCount") or page.get("total_count")
        has_next_page = bool(page.get("hasNextPage") or page.get("has_next_page"))
        if total_count is not None:
            has_next_page = start + len(page_records) < int(total_count)
        if not has_next_page or not page_records:
            break
        start += len(page_records)

    return records


async def _insert_record(sdk: UiPath, record: dict[str, Any]) -> tuple[dict[str, Any], str]:
    path = _data_service_path("insert")
    created = await _data_service_request(sdk, path, record)
    return _record_to_dict(created) or created or record, path


async def _update_record(sdk: UiPath, record_id: str, record: dict[str, Any]) -> tuple[dict[str, Any], str]:
    path = _data_service_path("update", record_id)
    updated = await _data_service_request(sdk, path, record)
    return _record_to_dict(updated) or updated or {"Id": record_id, **record}, path


async def _save_review_memory(payload: dict[str, Any]) -> dict[str, Any]:
    response = _empty_response("SAVE_REVIEW_MEMORY")
    requirement_id = _requirement_id(payload)
    response["requirementId"] = requirement_id
    response["dataServicePathUsed"] = _data_service_path("query")
    scenarios = payload.get("scenarios")

    if not requirement_id:
        response.update(status="Failed", message="Missing required field: requirementId", failedCount=1)
        return response
    if not isinstance(scenarios, list):
        response.update(status="Failed", message="Missing or invalid required field: scenarios", failedCount=1)
        return response

    sdk = UiPath()
    now = _now_iso()

    for index, scenario in enumerate(scenarios):
        try:
            if not isinstance(scenario, dict):
                raise ValueError("Scenario must be an object.")

            scenario_key = str(_first_present(scenario, "scenarioKey", "ScenarioKey", "key", "id", default="")).strip()
            if not scenario_key:
                raise ValueError("Scenario is missing scenarioKey.")

            record = {
                "RequirementId": requirement_id,
                "ScenarioKey": scenario_key,
                "ScenarioTitle": _first_present(scenario, "scenarioTitle", "ScenarioTitle", "title", "name", default=""),
                "ReviewStatus": _first_present(scenario, "reviewStatus", "ReviewStatus", "status", default=""),
                "ReviewComment": _first_present(scenario, "reviewComment", "ReviewComment", "comment", default=""),
                "ReviewedBy": _first_present(scenario, "reviewedBy", "ReviewedBy", default=""),
                "ReviewedAt": _first_present(scenario, "reviewedAt", "ReviewedAt", default=now),
                "ScenarioJson": _json_dumps(scenario),
                "StepsJson": _json_dumps(_first_present(scenario, "steps", "Steps", "stepsJson", "StepsJson", default=[])),
                "Source": _first_present(scenario, "source", "Source", default="QualityOps"),
                "UpdatedAt": now,
            }

            existing = await _query_records(sdk, RequirementId=requirement_id, ScenarioKey=scenario_key)
            if existing:
                record_id = existing[0]["Id"]
                updated, path = await _update_record(sdk, record_id, record)
                response["dataServicePathUsed"] = path
                response["updatedCount"] += 1
                response["records"].append(updated)
            else:
                created, path = await _insert_record(sdk, record)
                response["dataServicePathUsed"] = path
                response["createdCount"] += 1
                response["records"].append(created)
        except Exception as exc:
            path = _error_path(exc) or response["dataServicePathUsed"]
            response["dataServicePathUsed"] = path
            response["failedCount"] += 1
            response["failures"].append(
                {
                    "index": index,
                    "scenarioKey": scenario.get("scenarioKey") if isinstance(scenario, dict) else None,
                    "dataServicePathUsed": path,
                    "message": _format_error(exc),
                }
            )

    return _finalize_batch_response(
        response,
        f"Processed {len(scenarios)} scenario(s): "
        f"{response['createdCount']} created, {response['updatedCount']} updated, {response['failedCount']} failed.",
    )


async def _load_review_memory(payload: dict[str, Any]) -> dict[str, Any]:
    response = _empty_response("LOAD_REVIEW_MEMORY")
    requirement_id = _requirement_id(payload)
    response["requirementId"] = requirement_id
    response["dataServicePathUsed"] = _data_service_path("query")

    if not requirement_id:
        response.update(status="Failed", message="Missing required field: requirementId", failedCount=1)
        return response

    sdk = UiPath()
    try:
        records = await _query_records(sdk, RequirementId=requirement_id)
        response["message"] = f"Loaded {len(records)} review memory record(s)."
        response["requirementId"] = requirement_id
        response["records"] = records
        return response
    except Exception as exc:
        path = _error_path(exc) or response["dataServicePathUsed"]
        response.update(
            status="Failed",
            message=_format_error(exc),
            failedCount=1,
            requirementId=requirement_id,
            dataServicePathUsed=path,
            failures=[{"dataServicePathUsed": path, "message": _format_error(exc)}],
        )
        return response


async def _update_ado_creation_result(payload: dict[str, Any]) -> dict[str, Any]:
    response = _empty_response("UPDATE_ADO_CREATION_RESULT")
    requirement_id = _requirement_id(payload)
    response["requirementId"] = requirement_id
    response["dataServicePathUsed"] = _data_service_path("query")
    created_test_cases = payload.get("createdTestCases")

    if not requirement_id:
        response.update(status="Failed", message="Missing required field: requirementId", failedCount=1)
        return response
    if not isinstance(created_test_cases, list):
        response.update(status="Failed", message="Missing or invalid required field: createdTestCases", failedCount=1)
        return response

    sdk = UiPath()
    now = _now_iso()

    for index, test_case in enumerate(created_test_cases):
        try:
            if not isinstance(test_case, dict):
                raise ValueError("Created test case must be an object.")

            scenario_key = str(_first_present(test_case, "scenarioKey", "ScenarioKey", default="")).strip()
            if not scenario_key:
                raise ValueError("Created test case is missing scenarioKey.")

            existing = await _query_records(sdk, RequirementId=requirement_id, ScenarioKey=scenario_key)
            if not existing:
                raise ValueError("No memory record found for requirementId and scenarioKey.")

            record = {
                "CreatedAdoTestCaseId": _first_present(
                    test_case,
                    "adoTestCaseId",
                    "CreatedAdoTestCaseId",
                    "testCaseId",
                    default="",
                ),
                "CreatedAdoUrl": _first_present(test_case, "adoUrl", "CreatedAdoUrl", "url", default=""),
                "UpdatedAt": now,
            }
            record_id = existing[0]["Id"]
            updated, path = await _update_record(sdk, record_id, record)
            response["dataServicePathUsed"] = path
            response["updatedCount"] += 1
            response["records"].append(updated)
        except Exception as exc:
            path = _error_path(exc) or response["dataServicePathUsed"]
            response["dataServicePathUsed"] = path
            response["failedCount"] += 1
            response["failures"].append(
                {
                    "index": index,
                    "scenarioKey": test_case.get("scenarioKey") if isinstance(test_case, dict) else None,
                    "dataServicePathUsed": path,
                    "message": _format_error(exc),
                }
            )

    return _finalize_batch_response(
        response,
        f"Processed {len(created_test_cases)} created test case result(s): "
        f"{response['updatedCount']} updated, {response['failedCount']} failed.",
    )


async def process_request(state: GraphState) -> dict[str, Any]:
    try:
        payload = json.loads(state.get("question") or "")
        if not isinstance(payload, dict):
            raise ValueError("Question JSON must be an object.")
    except Exception as exc:
        response = _empty_response(status="Failed")
        response.update(message=f"Invalid question JSON: {exc}", failedCount=1)
        return response

    operation = str(payload.get("operation") or "").strip().upper()
    if operation == "SAVE_REVIEW_MEMORY":
        return await _save_review_memory(payload)
    if operation == "LOAD_REVIEW_MEMORY":
        return await _load_review_memory(payload)
    if operation == "UPDATE_ADO_CREATION_RESULT":
        return await _update_ado_creation_result(payload)

    response = _empty_response(operation=operation or "UNKNOWN", status="Failed")
    response.update(message=f"Unsupported operation: {operation or '<missing>'}", failedCount=1)
    return response


builder = StateGraph(GraphState, input_schema=GraphInput, output_schema=GraphOutput)
builder.add_node("process_request", process_request)
builder.add_edge(START, "process_request")
builder.add_edge("process_request", END)

graph = builder.compile()
