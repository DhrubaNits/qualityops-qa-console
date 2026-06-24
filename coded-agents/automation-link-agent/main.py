from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any
from urllib import parse

import requests
from pydantic import BaseModel, Field

try:
    from uipath.tracing import traced
except Exception:  # pragma: no cover - keeps local unit tests independent of UiPath runtime
    def traced(*args: Any, **kwargs: Any):
        def decorator(func):
            return func

        return decorator


DEFAULT_PACKAGE_IDENTIFIER = "QualityOpsDemoExecutionSimulator"

SIMULATOR_PROFILE_ORDER = [
    r"Test Case UI\SIM_PASS_001",
    r"Test Case UI\SIM_ASSERTION_FAILURE_001",
    r"Test Case UI\SIM_AUTOMATION_UI_FAILURE_001",
    r"Test Case UI\SIM_AUTOMATION_BROWSER_FAILURE_001",
    r"Test Case UI\SIM_AUTOMATION_SELECTOR_AMBIGUOUS_001",
    r"Test Case UI\SIM_ENVIRONMENT_FAILURE_001",
    r"Test Case UI\SIM_ASSERTION_FAILURE_002",
    r"Test Case UI\SIM_ENVIRONMENT_FAILURE_002",
    r"Test Case UI\SIM_PASS_002",
    r"Test Case UI\SIM_PASS_E2E_001",
]

TEST_MANAGER_CONFIG_NAMES = (
    "TEST_MANAGER_BEARER_TOKEN",
    "TEST_MANAGER_REFRESH_TOKEN",
    "TEST_MANAGER_CLIENT_ID",
    "TEST_MANAGER_CLIENT_SECRET",
    "TEST_MANAGER_TOKEN_URL",
    "TEST_MANAGER_BASE_URL",
    "TEST_MANAGER_PROJECT_PREFIX",
)


class Input(BaseModel):
    question: str = Field(default="")


class LinkedMapping(BaseModel):
    testCaseId: str
    simulatorProfile: str
    status: str


class Output(BaseModel):
    automationLinkStatus: str
    linkedCount: int = 0
    failedCount: int = 0
    packageIdentifier: str = DEFAULT_PACKAGE_IDENTIFIER
    linkedMappings: list[LinkedMapping] = Field(default_factory=list)
    blockedReasons: list[str] = Field(default_factory=list)
    nextAction: str
    packageEntryPointFetchAttempted: bool = False
    packageEntryPointFetchSucceeded: bool = False
    updateAutomationAttempted: bool = False
    tokenRefreshAttempted: bool = False
    tokenRefreshSucceeded: bool = False
    responseStatusCode: int | str = ""
    failedEndpointPath: str = ""


@dataclass
class RequestDiagnostics:
    package_entry_point_fetch_attempted: bool = False
    package_entry_point_fetch_succeeded: bool = False
    update_automation_attempted: bool = False
    token_refresh_attempted: bool = False
    token_refresh_succeeded: bool = False
    response_status_code: int | str = ""
    failed_endpoint_path: str = ""


@dataclass
class TestManagerAuthState:
    config: dict[str, str]
    access_token: str


class TmApiError(Exception):
    def __init__(
        self,
        status: int | str,
        response_text: str,
        endpoint_path: str = "",
        content_type: str = "",
    ) -> None:
        self.status = status
        self.response_text = response_text
        self.endpoint_path = endpoint_path
        self.content_type = content_type
        super().__init__(f"Test Manager API failed with status {status}.")


def _create_uipath_client() -> Any:
    from uipath.platform import UiPath

    return UiPath()


def _asset_to_string(asset: Any) -> str:
    value = _extract_asset_value(asset)
    return value.strip()


def _extract_asset_value(asset: Any, seen: set[int] | None = None) -> str:
    if asset is None:
        return ""
    if isinstance(asset, str):
        return asset
    if isinstance(asset, int | float | bool):
        return str(asset)

    seen = seen or set()
    asset_id = id(asset)
    if asset_id in seen:
        return ""
    seen.add(asset_id)

    preferred_keys = (
        "value",
        "Value",
        "string_value",
        "stringValue",
        "StringValue",
        "secret_value",
        "secretValue",
        "SecretValue",
        "secret",
        "Secret",
        "credential_password",
        "credentialPassword",
        "CredentialPassword",
        "password",
        "Password",
        "result",
        "Result",
        "data",
        "Data",
    )

    if isinstance(asset, dict):
        for key in preferred_keys:
            if key in asset and asset[key] is not None:
                value = _extract_asset_value(asset[key], seen)
                if value:
                    return value
        for value in asset.values():
            extracted = _extract_asset_value(value, seen)
            if extracted:
                return extracted
        return ""

    if hasattr(asset, "model_dump"):
        try:
            extracted = _extract_asset_value(asset.model_dump(), seen)
        except Exception:
            extracted = ""
        if extracted:
            return extracted

    if hasattr(asset, "__dict__"):
        extracted = _extract_asset_value(vars(asset), seen)
        if extracted:
            return extracted

    for attr in preferred_keys:
        value = getattr(asset, attr, None)
        if value is not None:
            extracted = _extract_asset_value(value, seen)
            if extracted:
                return extracted

    return ""


def _retrieve_asset_value(sdk: Any, asset_name: str) -> str:
    try:
        return _asset_to_string(sdk.assets.retrieve(name=asset_name))
    except TypeError:
        return _asset_to_string(sdk.assets.retrieve(asset_name))


def _read_asset_config() -> dict[str, str]:
    try:
        sdk = _create_uipath_client()
    except Exception:
        return {}

    values: dict[str, str] = {}
    for name in TEST_MANAGER_CONFIG_NAMES:
        try:
            values[name] = _retrieve_asset_value(sdk, name)
        except Exception:
            pass
    return values


def _resolve_test_manager_config() -> dict[str, str]:
    asset_values = _read_asset_config()
    resolved: dict[str, str] = {}
    for name in TEST_MANAGER_CONFIG_NAMES:
        resolved[name] = asset_values.get(name, "").strip() or os.getenv(name, "").strip()

    resolved["TEST_MANAGER_BEARER_TOKEN"] = _normalize_bearer_token(
        resolved.get("TEST_MANAGER_BEARER_TOKEN", "")
    )
    resolved["TEST_MANAGER_BASE_URL"] = _normalize_base_url(
        resolved.get("TEST_MANAGER_BASE_URL", "")
    )
    return resolved


def _normalize_bearer_token(value: str) -> str:
    token = str(value or "").strip()
    if token.casefold().startswith("bearer "):
        token = token[7:]
    return re.sub(r"\s+", "", token)


def _normalize_base_url(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def _join_url(base_url: str, path: str) -> str:
    return f"{_normalize_base_url(base_url)}/{path.lstrip('/')}"


def _endpoint_path(url: str) -> str:
    parsed = parse.urlparse(url)
    path = parsed.path or url
    return f"{path}?{parsed.query}" if parsed.query else path


def _headers_for_request(method: str, token: str) -> dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {_normalize_bearer_token(token)}",
    }
    if method.upper() != "GET":
        headers["Content-Type"] = "application/json"
    return headers


def _missing_refresh_config(config: dict[str, str]) -> list[str]:
    return [
        name
        for name in (
            "TEST_MANAGER_REFRESH_TOKEN",
            "TEST_MANAGER_CLIENT_ID",
            "TEST_MANAGER_CLIENT_SECRET",
            "TEST_MANAGER_TOKEN_URL",
        )
        if not config.get(name)
    ]


def _refresh_test_manager_access_token(
    auth_state: TestManagerAuthState,
    diagnostics: RequestDiagnostics,
) -> str:
    diagnostics.token_refresh_attempted = True
    config = auth_state.config
    if _missing_refresh_config(config):
        raise TmApiError(
            "TokenRefreshConfigurationMissing",
            "Test Manager token expired and refresh configuration is missing.",
        )

    try:
        response = requests.post(
            config["TEST_MANAGER_TOKEN_URL"],
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "refresh_token",
                "client_id": config["TEST_MANAGER_CLIENT_ID"],
                "client_secret": config["TEST_MANAGER_CLIENT_SECRET"],
                "refresh_token": config["TEST_MANAGER_REFRESH_TOKEN"],
            },
            timeout=30,
        )
    except requests.RequestException as exc:
        raise TmApiError("TokenRefreshFailed", str(exc)) from exc

    diagnostics.response_status_code = response.status_code
    if not response.ok:
        raise TmApiError(
            response.status_code,
            response.text or "",
            endpoint_path=_endpoint_path(config["TEST_MANAGER_TOKEN_URL"]),
            content_type=response.headers.get("Content-Type", ""),
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise TmApiError("InvalidTokenRefreshResponse", "Token refresh response was not valid JSON.") from exc

    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise TmApiError("InvalidTokenRefreshResponse", "Token refresh response did not include access_token.")

    new_access_token = _normalize_bearer_token(str(payload["access_token"]))
    auth_state.access_token = new_access_token
    config["TEST_MANAGER_BEARER_TOKEN"] = new_access_token
    if payload.get("refresh_token"):
        config["TEST_MANAGER_REFRESH_TOKEN"] = str(payload["refresh_token"]).strip()
    diagnostics.token_refresh_succeeded = True
    return new_access_token


def _send_test_manager_request(
    method: str,
    url: str,
    token: str,
    body: Any | None = None,
) -> requests.Response:
    headers = _headers_for_request(method, token)
    if method.upper() == "GET":
        return requests.get(url, headers=headers, timeout=30)
    if method.upper() == "POST":
        return requests.post(url, headers=headers, json=body if body is not None else {}, timeout=30)
    raise TmApiError("ConfigurationError", f"Unsupported HTTP method {method}.")


def _parse_test_manager_response(
    response: requests.Response,
    *,
    url: str,
    diagnostics: RequestDiagnostics,
) -> dict[str, Any]:
    diagnostics.response_status_code = response.status_code
    if not response.ok:
        raise TmApiError(
            response.status_code,
            response.text or "",
            endpoint_path=_endpoint_path(url),
            content_type=response.headers.get("Content-Type", ""),
        )
    if not (response.text or "").strip():
        return {}
    parsed = response.json()
    return parsed if isinstance(parsed, dict) else {"value": parsed}


def _http_json(
    method: str,
    url: str,
    token: str,
    body: Any | None = None,
    diagnostics: RequestDiagnostics | None = None,
    auth_state: TestManagerAuthState | None = None,
) -> dict[str, Any]:
    diagnostics = diagnostics or RequestDiagnostics()
    token_to_use = auth_state.access_token if auth_state is not None else token
    try:
        response = _send_test_manager_request(method, url, token_to_use, body)
        try:
            return _parse_test_manager_response(response, url=url, diagnostics=diagnostics)
        except TmApiError as exc:
            if exc.status != 401 or auth_state is None or diagnostics.token_refresh_attempted:
                raise
            refreshed_token = _refresh_test_manager_access_token(auth_state, diagnostics)
            retry_response = _send_test_manager_request(method, url, refreshed_token, body)
            return _parse_test_manager_response(retry_response, url=url, diagnostics=diagnostics)
    except requests.RequestException as exc:
        raise TmApiError("ConnectionError", str(exc), endpoint_path=_endpoint_path(url)) from exc
    except ValueError as exc:
        raise TmApiError("InvalidResponse", "Response was not valid JSON.", endpoint_path=_endpoint_path(url)) from exc


def package_entry_points_path(project_id: str) -> str:
    return (
        f"/api/v2/{project_id}/orchestrator/packageentrypoints"
        "?Top=100&Skip=0&Search=&DistinctByPackageEntryPointIdAndPackageName=true"
    )


def update_package_automation_path(project_id: str, test_case_id: str) -> str:
    return f"/api/v2/{project_id}/testcases/{test_case_id}/updatepackageautomation"


def _extract_collection(payload: dict[str, Any]) -> list[Any]:
    for key in ("value", "items", "data", "results", "packageEntryPoints"):
        value = payload.get(key)
        if isinstance(value, list):
            return value
    if isinstance(payload.get("Data"), list):
        return payload["Data"]
    return []


def _field(item: dict[str, Any], *names: str) -> str:
    for name in names:
        if item.get(name) is not None:
            return str(item[name]).strip()
    return ""


def _profile_lookup_key(name: str) -> str:
    return str(name or "").strip().rstrip(".").casefold()


def build_entry_point_lookup(
    payload: dict[str, Any],
    package_identifier: str,
) -> dict[str, dict[str, str]]:
    lookup: dict[str, dict[str, str]] = {}
    for item in _extract_collection(payload):
        if not isinstance(item, dict):
            continue
        package_name = _field(item, "packageName", "PackageName", "packageIdentifier", "PackageIdentifier")
        if package_name != package_identifier:
            continue
        entry_point_name = _field(
            item,
            "packageEntryPointName",
            "PackageEntryPointName",
            "entryPointName",
            "EntryPointName",
            "name",
            "Name",
        )
        entry_point_id = _field(
            item,
            "packageEntryPointId",
            "PackageEntryPointId",
            "packageEntryPointUniqueId",
            "PackageEntryPointUniqueId",
            "id",
            "Id",
        )
        if entry_point_name and entry_point_id:
            lookup[_profile_lookup_key(entry_point_name)] = {
                "packageEntryPointName": entry_point_name,
                "packageEntryPointId": entry_point_id,
            }
    return lookup


def _safe_error_text(text: str, config: dict[str, str]) -> str:
    safe_text = str(text)
    for name in (
        "TEST_MANAGER_BEARER_TOKEN",
        "TEST_MANAGER_REFRESH_TOKEN",
        "TEST_MANAGER_CLIENT_SECRET",
    ):
        secret = config.get(name, "")
        if secret:
            safe_text = safe_text.replace(secret, "[REDACTED]")
    return safe_text


def _compact_json_error(response_text: str) -> str:
    try:
        payload = json.loads(response_text)
    except json.JSONDecodeError:
        return " ".join(response_text.split())

    if isinstance(payload, dict):
        for key in ("message", "error_description", "error", "title", "detail"):
            value = payload.get(key)
            if value:
                return str(value)
        return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)


def _format_api_error(exc: TmApiError, config: dict[str, str]) -> str:
    if exc.status == "TokenRefreshConfigurationMissing":
        return "Test Manager token expired and refresh configuration is missing."

    endpoint = f" at {exc.endpoint_path}" if exc.endpoint_path else ""
    response_text = _safe_error_text(exc.response_text, config).strip()
    content_type = exc.content_type.casefold()
    if "text/html" in content_type or response_text.lstrip().casefold().startswith("<!doctype html"):
        return (
            f"Test Manager API call failed with status {exc.status}{endpoint}. "
            "Authentication/session was rejected by UiPath Platform."
        )

    compact_message = _compact_json_error(response_text) if response_text else ""
    if compact_message:
        return f"Test Manager API call failed with status {exc.status}{endpoint}: {compact_message}"
    return f"Test Manager API call failed with status {exc.status}{endpoint}."


def _output(
    *,
    status: str,
    package_identifier: str,
    linked_mappings: list[LinkedMapping] | None = None,
    blocked_reasons: list[str] | None = None,
    diagnostics: RequestDiagnostics | None = None,
) -> Output:
    diagnostics = diagnostics or RequestDiagnostics()
    linked_mappings = linked_mappings or []
    failed_count = len([mapping for mapping in linked_mappings if mapping.status != "Linked"])
    return Output(
        automationLinkStatus=status,
        linkedCount=len([mapping for mapping in linked_mappings if mapping.status == "Linked"]),
        failedCount=failed_count,
        packageIdentifier=package_identifier,
        linkedMappings=linked_mappings,
        blockedReasons=blocked_reasons or [],
        nextAction=(
            "Execute the Test Set in UiPath Test Manager."
            if status == "Completed"
            else "Resolve blocked reasons, then rerun the automation link agent."
        ),
        packageEntryPointFetchAttempted=diagnostics.package_entry_point_fetch_attempted,
        packageEntryPointFetchSucceeded=diagnostics.package_entry_point_fetch_succeeded,
        updateAutomationAttempted=diagnostics.update_automation_attempted,
        tokenRefreshAttempted=diagnostics.token_refresh_attempted,
        tokenRefreshSucceeded=diagnostics.token_refresh_succeeded,
        responseStatusCode=diagnostics.response_status_code,
        failedEndpointPath=diagnostics.failed_endpoint_path,
    )


def link_automation(payload: dict[str, Any]) -> Output:
    package_identifier = str(payload.get("packageIdentifier") or DEFAULT_PACKAGE_IDENTIFIER).strip()
    project_id = str(payload.get("projectId") or "").strip()
    created_ids_value = payload.get("createdTestCaseIds")

    blocked_reasons: list[str] = []
    if not project_id:
        blocked_reasons.append("Invalid input: projectId is required.")
    if not isinstance(created_ids_value, list) or not created_ids_value:
        blocked_reasons.append("Invalid input: createdTestCaseIds is required and cannot be empty.")

    created_test_case_ids = [
        str(test_case_id).strip()
        for test_case_id in created_ids_value
        if str(test_case_id or "").strip()
    ] if isinstance(created_ids_value, list) else []
    if isinstance(created_ids_value, list) and created_ids_value and not created_test_case_ids:
        blocked_reasons.append("Invalid input: createdTestCaseIds must contain at least one non-empty id.")
    if not package_identifier:
        blocked_reasons.append("Invalid input: packageIdentifier is required.")

    diagnostics = RequestDiagnostics()
    if blocked_reasons:
        return _output(
            status="Failed",
            package_identifier=package_identifier or DEFAULT_PACKAGE_IDENTIFIER,
            blocked_reasons=blocked_reasons,
            diagnostics=diagnostics,
        )

    config = _resolve_test_manager_config()
    if not config.get("TEST_MANAGER_BEARER_TOKEN"):
        blocked_reasons.append("TEST_MANAGER_BEARER_TOKEN is required.")
    if not config.get("TEST_MANAGER_BASE_URL"):
        blocked_reasons.append("TEST_MANAGER_BASE_URL is required.")
    if blocked_reasons:
        return _output(
            status="Failed",
            package_identifier=package_identifier,
            blocked_reasons=blocked_reasons,
            diagnostics=diagnostics,
        )

    auth_state = TestManagerAuthState(
        config=config,
        access_token=config["TEST_MANAGER_BEARER_TOKEN"],
    )

    try:
        diagnostics.package_entry_point_fetch_attempted = True
        entry_points_payload = _http_json(
            "GET",
            _join_url(config["TEST_MANAGER_BASE_URL"], package_entry_points_path(project_id)),
            auth_state.access_token,
            diagnostics=diagnostics,
            auth_state=auth_state,
        )
        diagnostics.package_entry_point_fetch_succeeded = True
        lookup = build_entry_point_lookup(entry_points_payload, package_identifier)

        linked_mappings: list[LinkedMapping] = []
        blocked_profiles: list[str] = []
        for index, test_case_id in enumerate(created_test_case_ids):
            simulator_profile = SIMULATOR_PROFILE_ORDER[index % len(SIMULATOR_PROFILE_ORDER)]
            entry_point = lookup.get(_profile_lookup_key(simulator_profile))
            if entry_point is None:
                linked_mappings.append(
                    LinkedMapping(
                        testCaseId=test_case_id,
                        simulatorProfile=simulator_profile,
                        status="Failed",
                    )
                )
                blocked_profiles.append(f"Package entry point not found: {simulator_profile}")
                continue

            endpoint = _join_url(
                config["TEST_MANAGER_BASE_URL"],
                update_package_automation_path(project_id, test_case_id),
            )
            body = {
                "testCaseId": test_case_id,
                "packageEntryPointUniqueId": entry_point["packageEntryPointId"],
                "packageIdentifier": package_identifier,
                "packageEntryPointName": entry_point["packageEntryPointName"],
                "correlationId": str(uuid.uuid4()),
            }
            diagnostics.update_automation_attempted = True
            try:
                _http_json(
                    "POST",
                    endpoint,
                    auth_state.access_token,
                    body,
                    diagnostics=diagnostics,
                    auth_state=auth_state,
                )
                linked_mappings.append(
                    LinkedMapping(
                        testCaseId=test_case_id,
                        simulatorProfile=simulator_profile,
                        status="Linked",
                    )
                )
            except TmApiError as exc:
                diagnostics.failed_endpoint_path = exc.endpoint_path
                linked_mappings.append(
                    LinkedMapping(
                        testCaseId=test_case_id,
                        simulatorProfile=simulator_profile,
                        status="Failed",
                    )
                )
                blocked_reasons.append(_format_api_error(exc, config))

        blocked_reasons.extend(dict.fromkeys(blocked_profiles))
        linked_count = len([mapping for mapping in linked_mappings if mapping.status == "Linked"])
        if linked_count == len(created_test_case_ids):
            status = "Completed"
        elif linked_count == 0:
            status = "Failed"
        else:
            status = "Partial"
        return _output(
            status=status,
            package_identifier=package_identifier,
            linked_mappings=linked_mappings,
            blocked_reasons=blocked_reasons,
            diagnostics=diagnostics,
        )
    except TmApiError as exc:
        diagnostics.failed_endpoint_path = exc.endpoint_path
        return _output(
            status="Failed",
            package_identifier=package_identifier,
            blocked_reasons=[_format_api_error(exc, config)],
            diagnostics=diagnostics,
        )


@traced()
async def main(input: Input) -> Output:
    try:
        payload = json.loads(input.question or "{}")
    except json.JSONDecodeError as exc:
        return _output(
            status="Failed",
            package_identifier=DEFAULT_PACKAGE_IDENTIFIER,
            blocked_reasons=[f"Invalid input: question must be valid JSON. {exc.msg}."],
        )

    if not isinstance(payload, dict):
        return _output(
            status="Failed",
            package_identifier=DEFAULT_PACKAGE_IDENTIFIER,
            blocked_reasons=["Invalid input: question must be a JSON object."],
        )

    return link_automation(payload)
