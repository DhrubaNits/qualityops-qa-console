from __future__ import annotations

import json
import os
import re
import hashlib
from dataclasses import dataclass, field
from typing import Any
from urllib import parse

import requests
from pydantic import BaseModel, Field
from uipath.tracing import traced


class Input(BaseModel):
    question: str = Field(default="")


class Summary(BaseModel):
    requirementsPrepared: int = 0
    testCasesPrepared: int = 0
    linksPrepared: int = 0
    testSetsPrepared: int = 0


class Output(BaseModel):
    syncStatus: str
    syncMode: str = "DryRun"
    requirementId: str = ""
    testManagerProjectId: str = ""
    testManagerProjectKey: str = ""
    testManagerProjectName: str = ""
    requirementPayload: dict[str, Any] | None = None
    testCasePayloads: list[dict[str, Any]] = Field(default_factory=list)
    requirementLinks: list[dict[str, Any]] = Field(default_factory=list)
    testSetPayload: dict[str, Any] | None = None
    testSetMembership: list[dict[str, Any]] = Field(default_factory=list)
    summary: Summary = Field(default_factory=Summary)
    blockedReasons: list[str] = Field(default_factory=list)
    nextAction: str
    realSyncAttempted: bool = False
    authTokenPresent: bool = False
    authHeaderPrepared: bool = False
    baseUrlUsed: str = ""
    firstEndpointPath: str = ""
    tokenLength: int = 0
    tokenFingerprint: str = ""
    tokenStartsWithBearerPrefix: bool = False
    requestUrlUsed: str = ""
    requestHeadersPrepared: dict[str, Any] = Field(default_factory=dict)
    responseContentType: str = ""
    responseStatusCode: int | str = ""
    tokenRefreshAttempted: bool = False
    tokenRefreshSucceeded: bool = False
    retryAttempted: bool = False
    createdRequirement: str = ""
    createdTestCases: list[str] = Field(default_factory=list)
    createdTestSet: str = ""
    createdTestCaseIds: list[str] = Field(default_factory=list)
    reusedTestCaseIds: list[str] = Field(default_factory=list)
    allTestCaseIds: list[str] = Field(default_factory=list)
    createdTestSetId: str = ""
    testCaseReuseEnabled: bool = True
    testCaseSyncDetails: list[dict[str, Any]] = Field(default_factory=list)
    reuseSearchAttempted: bool = False
    reuseSearchSucceeded: bool = False
    createdCount: int = 0
    reusedCount: int = 0
    assignTestSetPayloadShape: str = ""
    failedEndpointPath: str = ""


TEST_MANAGER_CONFIG_NAMES = (
    "TEST_MANAGER_BEARER_TOKEN",
    "TEST_MANAGER_BASE_URL",
    "TEST_MANAGER_PROJECT_PREFIX",
    "TEST_MANAGER_REFRESH_TOKEN",
    "TEST_MANAGER_CLIENT_ID",
    "TEST_MANAGER_CLIENT_SECRET",
    "TEST_MANAGER_TOKEN_URL",
)


def clean_duplicate_consecutive_words(text: str) -> str:
    words = str(text or "").split()
    cleaned: list[str] = []

    for word in words:
        if not cleaned or _word_key(cleaned[-1]) != _word_key(word):
            cleaned.append(word)

    return " ".join(cleaned)


def _word_key(word: str) -> str:
    return re.sub(r"^\W+|\W+$", "", word).casefold()


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
        "text_value",
        "textValue",
        "TextValue",
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
            dumped = asset.model_dump()
        except Exception:
            dumped = None
        extracted = _extract_asset_value(dumped, seen)
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


def _create_uipath_client() -> Any:
    from uipath.platform import UiPath

    return UiPath()


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

    raw_token = resolved.get("TEST_MANAGER_BEARER_TOKEN", "")
    resolved["TEST_MANAGER_BEARER_TOKEN"] = _normalize_bearer_token(
        raw_token
    )
    resolved["_TEST_MANAGER_TOKEN_STARTS_WITH_BEARER_PREFIX"] = (
        "true" if _token_starts_with_bearer_prefix(raw_token) else "false"
    )
    resolved["TEST_MANAGER_BASE_URL"] = _normalize_base_url(
        resolved.get("TEST_MANAGER_BASE_URL", "")
    )
    return resolved


@dataclass
class RealSyncResult:
    requirement_id: str
    test_case_ids: list[str]
    created_test_case_ids: list[str]
    reused_test_case_ids: list[str]
    test_case_sync_details: list[dict[str, Any]]
    test_set_id: str
    assign_test_set_payload_shape: str = ""


@dataclass
class RealSyncProgress:
    requirement_id: str = ""
    test_case_ids: list[str] = field(default_factory=list)
    created_test_case_ids: list[str] = field(default_factory=list)
    reused_test_case_ids: list[str] = field(default_factory=list)
    test_case_sync_details: list[dict[str, Any]] = field(default_factory=list)
    reuse_search_attempted: bool = False
    reuse_search_succeeded: bool = False
    test_set_id: str = ""
    assign_test_set_payload_shape: str = ""


@dataclass
class TestCaseMatch:
    test_case_id: str = ""
    strategy: str = ""


@dataclass
class RequestDiagnostics:
    request_url_used: str = ""
    request_headers_prepared: dict[str, Any] | None = None
    response_content_type: str = ""
    response_status_code: int | str = ""
    token_refresh_attempted: bool = False
    token_refresh_succeeded: bool = False
    retry_attempted: bool = False


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


def normalize_sync_mode(value: Any) -> str:
    mode = str(value or "DryRun").strip().casefold()
    if mode == "realsync":
        return "RealSync"
    return "DryRun"


def select_test_set(risk_level: str) -> tuple[str, str]:
    risk = str(risk_level or "").strip().casefold()
    if risk == "high":
        return (
            "High Risk Functional + Integration Suite",
            "QualityOps generated test set for high-risk execution.",
        )
    if risk == "medium":
        return (
            "Standard Regression Validation Suite",
            "QualityOps generated test set for standard regression validation.",
        )
    if risk == "low":
        return (
            "Smoke Validation Suite",
            "QualityOps generated test set for smoke validation.",
        )
    return (
        "QualityOps Generated Test Suite",
        "QualityOps generated test set.",
    )


def _extract_response_id(response_body: dict[str, Any], context: str) -> str:
    value = response_body.get("id") or response_body.get("Id")
    if value:
        return str(value)

    raise TmApiError("InvalidResponse", f"{context} response did not include id.")


def _endpoint_path(url: str) -> str:
    parsed = parse.urlparse(url)
    path = parsed.path or url
    return f"{path}?{parsed.query}" if parsed.query else path


def _normalize_bearer_token(value: str) -> str:
    token = str(value or "").strip()
    if _token_starts_with_bearer_prefix(token):
        token = token[7:]
    return re.sub(r"\s+", "", token)


def normalize_token(token: str) -> str:
    return _normalize_bearer_token(token)


def _token_starts_with_bearer_prefix(value: str) -> bool:
    return str(value or "").strip().casefold().startswith("bearer ")


def _normalize_base_url(value: str) -> str:
    return str(value or "").strip().rstrip("/")


def _token_fingerprint(token: str) -> str:
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def build_get_headers(token: str) -> dict[str, str]:
    normalized_token = normalize_token(token)
    return {
        "Accept": "application/json",
        "Authorization": f"Bearer {normalized_token}",
    }


def build_post_headers(token: str) -> dict[str, str]:
    headers = build_get_headers(token)
    headers["Content-Type"] = "application/json"
    return headers


def _headers_for_request(method: str, token: str) -> dict[str, str]:
    if method.upper() != "GET":
        return build_post_headers(token)
    return build_get_headers(token)


def _safe_header_diagnostics(headers: dict[str, str]) -> dict[str, Any]:
    return {
        "AuthorizationPresent": bool(headers.get("Authorization")),
        "Accept": headers.get("Accept", ""),
        "Content-Type": headers.get("Content-Type", ""),
    }


def _record_request_diagnostics(
    diagnostics: RequestDiagnostics | None,
    *,
    url: str,
    headers: dict[str, str],
) -> None:
    if diagnostics is None or diagnostics.request_url_used:
        return
    diagnostics.request_url_used = url
    diagnostics.request_headers_prepared = _safe_header_diagnostics(headers)


def _record_response_diagnostics(
    diagnostics: RequestDiagnostics | None,
    *,
    status_code: int | str,
    content_type: str,
) -> None:
    if diagnostics is None:
        return
    diagnostics.response_status_code = status_code
    diagnostics.response_content_type = content_type


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
    diagnostics: RequestDiagnostics | None = None,
) -> str:
    config = auth_state.config
    if diagnostics is not None:
        diagnostics.token_refresh_attempted = True

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

    content_type = response.headers.get("Content-Type", "")
    response_text = response.text or ""
    if not response.ok:
        raise TmApiError(
            response.status_code,
            response_text,
            endpoint_path=_endpoint_path(config["TEST_MANAGER_TOKEN_URL"]),
            content_type=content_type,
        )

    try:
        payload = response.json()
    except ValueError as exc:
        raise TmApiError(
            "InvalidTokenRefreshResponse",
            "Token refresh response was not valid JSON.",
            endpoint_path=_endpoint_path(config["TEST_MANAGER_TOKEN_URL"]),
            content_type=content_type,
        ) from exc

    if not isinstance(payload, dict) or not payload.get("access_token"):
        raise TmApiError(
            "InvalidTokenRefreshResponse",
            "Token refresh response did not include access_token.",
            endpoint_path=_endpoint_path(config["TEST_MANAGER_TOKEN_URL"]),
            content_type=content_type,
        )

    new_access_token = _normalize_bearer_token(str(payload["access_token"]))
    auth_state.access_token = new_access_token
    config["TEST_MANAGER_BEARER_TOKEN"] = new_access_token
    if payload.get("refresh_token"):
        config["TEST_MANAGER_REFRESH_TOKEN"] = str(payload["refresh_token"]).strip()

    if diagnostics is not None:
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
    diagnostics: RequestDiagnostics | None = None,
) -> dict[str, Any]:
    content_type = response.headers.get("Content-Type", "")
    _record_response_diagnostics(
        diagnostics,
        status_code=response.status_code,
        content_type=content_type,
    )

    response_text = response.text or ""
    if not response.ok:
        raise TmApiError(
            response.status_code,
            response_text,
            endpoint_path=_endpoint_path(url),
            content_type=content_type,
        )

    if not response_text.strip():
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
    token_to_use = auth_state.access_token if auth_state is not None else token
    headers = _headers_for_request(method, token_to_use)
    _record_request_diagnostics(diagnostics, url=url, headers=headers)

    try:
        response = _send_test_manager_request(method, url, token_to_use, body)
        try:
            return _parse_test_manager_response(response, url=url, diagnostics=diagnostics)
        except TmApiError as exc:
            if exc.status != 401 or auth_state is None or diagnostics is None:
                raise
            if diagnostics.token_refresh_attempted:
                raise

            refreshed_token = _refresh_test_manager_access_token(auth_state, diagnostics)
            diagnostics.retry_attempted = True
            retry_response = _send_test_manager_request(method, url, refreshed_token, body)
            return _parse_test_manager_response(retry_response, url=url, diagnostics=diagnostics)
    except requests.RequestException as exc:
        response = getattr(exc, "response", None)
        if response is not None:
            content_type = response.headers.get("Content-Type", "")
            _record_response_diagnostics(
                diagnostics,
                status_code=response.status_code,
                content_type=content_type,
            )
            raise TmApiError(
                response.status_code,
                response.text or str(exc),
                endpoint_path=_endpoint_path(url),
                content_type=content_type,
            ) from exc
        raise TmApiError("ConnectionError", str(exc), endpoint_path=_endpoint_path(url)) from exc
    except json.JSONDecodeError as exc:
        raise TmApiError(
            "InvalidResponse",
            f"Response was not valid JSON. {exc.msg}.",
            endpoint_path=_endpoint_path(url),
        ) from exc
    except ValueError as exc:
        raise TmApiError(
            "InvalidResponse",
            "Response was not valid JSON.",
            endpoint_path=_endpoint_path(url),
        ) from exc


def _join_url(base_url: str, path: str) -> str:
    return f"{_normalize_base_url(base_url)}/{path.lstrip('/')}"


def _project_lookup_path(project_prefix: str) -> str:
    return f"/api/v2/projects/prefix/{parse.quote(str(project_prefix), safe='')}"


def lookup_test_manager_project_by_prefix(
    *,
    base_url: str,
    project_prefix: str,
    token: str,
    diagnostics: RequestDiagnostics | None = None,
    auth_state: TestManagerAuthState | None = None,
) -> dict[str, Any]:
    return _http_json(
        "GET",
        _join_url(base_url, _project_lookup_path(project_prefix)),
        token,
        diagnostics=diagnostics,
        auth_state=auth_state,
    )


def _collection_items(response_body: dict[str, Any]) -> list[dict[str, Any]]:
    for key in ("items", "value", "data", "results"):
        value = response_body.get(key)
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if isinstance(value, dict):
            nested = _collection_items(value)
            if nested:
                return nested
    return []


def _field_value(item: dict[str, Any], *names: str) -> str:
    for name in names:
        for key, value in item.items():
            if key.casefold() == name.casefold() and value is not None:
                return str(value).strip()
    return ""


def _test_case_id(item: dict[str, Any]) -> str:
    return _field_value(item, "id", "testCaseId", "key")


def _normalize_match_text(value: Any) -> str:
    text = str(value or "").casefold().strip()
    text = re.sub(r"\btargeted\s+validation\s+for\b", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\bts\s+0*(\d+)\b", r"ts\1", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _all_text_values(value: Any) -> list[str]:
    values: list[str] = []
    if value is None:
        return values
    if isinstance(value, str | int | float | bool):
        return [str(value)]
    if isinstance(value, dict):
        for nested in value.values():
            values.extend(_all_text_values(nested))
        return values
    if isinstance(value, list):
        for nested in value:
            values.extend(_all_text_values(nested))
    return values


def _item_text_blob(item: dict[str, Any]) -> str:
    return " ".join(_all_text_values(item))


def _contains_exact_token(text: str, token: str) -> bool:
    if not token:
        return False
    return re.search(rf"(?<![A-Za-z0-9]){re.escape(token)}(?![A-Za-z0-9])", text, re.IGNORECASE) is not None


def _extract_scenario_index(value: str) -> int | None:
    match = re.search(r"(?:^|[^A-Za-z0-9])TS[-_\s]*0*(\d+)(?:[^A-Za-z0-9]|$)", str(value or ""), re.IGNORECASE)
    if not match:
        return None
    return int(match.group(1))


def _test_case_match_strategy(
    item: dict[str, Any],
    *,
    foreign_reference: str,
    requirement_external_id: str,
    scenario_id: str,
    name: str,
) -> str:
    if foreign_reference:
        candidate_reference = _field_value(
            item,
            "foreignReference",
            "externalId",
            "externalReference",
            "reference",
        )
        if candidate_reference == foreign_reference:
            return "foreignReference"

    text_blob = _item_text_blob(item)
    if scenario_id and _contains_exact_token(text_blob, scenario_id):
        return "scenarioId"

    candidate_name = _field_value(item, "name", "title")
    if name and candidate_name and _normalize_match_text(candidate_name) == _normalize_match_text(name):
        return "normalizedTitle"

    same_requirement = bool(
        requirement_external_id and _contains_exact_token(text_blob, requirement_external_id)
    )
    if same_requirement:
        desired_index = _extract_scenario_index(scenario_id)
        candidate_index = _extract_scenario_index(text_blob)
        if desired_index is not None and candidate_index == desired_index:
            return "scenarioIndex"

    return ""


def _choose_best_test_case_match(
    candidates: list[dict[str, Any]],
    *,
    foreign_reference: str,
    requirement_external_id: str,
    scenario_id: str,
    name: str,
) -> TestCaseMatch:
    strategy_rank = {
        "foreignReference": 0,
        "scenarioId": 1,
        "normalizedTitle": 2,
        "scenarioIndex": 3,
    }
    best: tuple[int, str, str] | None = None
    seen_ids: set[str] = set()

    for item in candidates:
        test_case_id = _test_case_id(item)
        if not test_case_id or test_case_id in seen_ids:
            continue
        seen_ids.add(test_case_id)
        strategy = _test_case_match_strategy(
            item,
            foreign_reference=foreign_reference,
            requirement_external_id=requirement_external_id,
            scenario_id=scenario_id,
            name=name,
        )
        if not strategy:
            continue
        candidate = (strategy_rank[strategy], test_case_id, strategy)
        if best is None or candidate[0] < best[0]:
            best = candidate

    if best is None:
        return TestCaseMatch()
    return TestCaseMatch(test_case_id=best[1], strategy=best[2])


def _search_test_cases(
    *,
    base_url: str,
    project_id: str,
    query: str,
    token: str,
    diagnostics: RequestDiagnostics | None = None,
    auth_state: TestManagerAuthState | None = None,
) -> dict[str, Any]:
    query_string = parse.urlencode({"search": query}) if query else ""
    path = f"/api/v2/{project_id}/testcases"
    if query_string:
        path = f"{path}?{query_string}"
    return _http_json(
        "GET",
        _join_url(base_url, path),
        token,
        diagnostics=diagnostics,
        auth_state=auth_state,
    )


def _find_existing_test_case(
    *,
    base_url: str,
    project_id: str,
    foreign_reference: str,
    requirement_external_id: str,
    scenario_id: str,
    name: str,
    token: str,
    diagnostics: RequestDiagnostics | None = None,
    auth_state: TestManagerAuthState | None = None,
) -> TestCaseMatch:
    search_values: list[str] = []
    for value in (foreign_reference, scenario_id, name, requirement_external_id):
        if value and value not in search_values:
            search_values.append(value)

    candidates: list[dict[str, Any]] = []

    for search_value in search_values:
        try:
            response = _search_test_cases(
                base_url=base_url,
                project_id=project_id,
                query=search_value,
                token=token,
                diagnostics=diagnostics,
                auth_state=auth_state,
            )
        except TmApiError as exc:
            if str(exc.status) in {"400", "404"} and search_value == foreign_reference:
                continue
            raise

        candidates.extend(_collection_items(response))
        match = _choose_best_test_case_match(
            candidates,
            foreign_reference=foreign_reference,
            requirement_external_id=requirement_external_id,
            scenario_id=scenario_id,
            name=name,
        )
        if match.test_case_id and match.strategy in {"foreignReference", "scenarioId"}:
            return match

    return _choose_best_test_case_match(
        candidates,
        foreign_reference=foreign_reference,
        requirement_external_id=requirement_external_id,
        scenario_id=scenario_id,
        name=name,
    )


def _assign_test_cases_to_test_set(
    *,
    base_url: str,
    project_id: str,
    test_set_id: str,
    test_case_ids: list[str],
    token: str,
    diagnostics: RequestDiagnostics | None = None,
    progress: RealSyncProgress | None = None,
    auth_state: TestManagerAuthState | None = None,
) -> str:
    endpoint = _join_url(
        base_url,
        f"/api/v2/{project_id}/testsets/{test_set_id}/assigntestcases",
    )
    ids = [str(test_case_id) for test_case_id in test_case_ids]

    payload_attempts: list[tuple[str, Any]] = [
        ("array", ids),
        ("ids", {"ids": ids}),
    ]
    last_error: TmApiError | None = None

    for payload_shape, payload in payload_attempts:
        if progress is not None:
            progress.assign_test_set_payload_shape = payload_shape
        try:
            _http_json("POST", endpoint, token, payload, diagnostics, auth_state)
            return payload_shape
        except TmApiError as exc:
            last_error = exc
            if str(exc.status) != "400":
                raise

    assert last_error is not None
    raise last_error


def _run_real_sync(
    *,
    config: dict[str, str],
    project_id: str,
    project_prefix: str,
    requirement_payload: dict[str, Any],
    test_case_payloads: list[dict[str, Any]],
    test_set_payload: dict[str, Any],
    diagnostics: RequestDiagnostics | None = None,
    progress: RealSyncProgress | None = None,
) -> RealSyncResult:
    progress = progress or RealSyncProgress()
    base_url = config["TEST_MANAGER_BASE_URL"]
    token = config["TEST_MANAGER_BEARER_TOKEN"]
    auth_state = TestManagerAuthState(config=config, access_token=token)

    resolved_project_id = project_id
    if project_prefix:
        project_response = lookup_test_manager_project_by_prefix(
            base_url=base_url,
            project_prefix=project_prefix,
            token=token,
            diagnostics=diagnostics,
            auth_state=auth_state,
        )
        resolved_project_id = _extract_response_id(project_response, "Project lookup")
    elif not resolved_project_id:
        raise TmApiError("ConfigurationError", "Project ID or project prefix is required.")

    requirement_response = _http_json(
        "POST",
        _join_url(base_url, f"/api/v2/{resolved_project_id}/requirements"),
        token,
        requirement_payload,
        diagnostics,
        auth_state,
    )
    created_requirement_id = _extract_response_id(requirement_response, "Create requirement")
    progress.requirement_id = created_requirement_id

    created_test_case_ids: list[str] = []
    reused_test_case_ids: list[str] = []
    all_test_case_ids: list[str] = []
    test_case_sync_details: list[dict[str, Any]] = []
    requirement_external_id = str(requirement_payload.get("externalId") or "").strip()
    for test_case_payload in test_case_payloads:
        scenario_id = str(test_case_payload.get("scenarioId") or "").strip()
        test_case_name = str(test_case_payload.get("name") or "").strip()
        progress.reuse_search_attempted = True
        existing_test_case = _find_existing_test_case(
            base_url=base_url,
            project_id=resolved_project_id,
            foreign_reference=str(test_case_payload.get("foreignReference") or "").strip(),
            requirement_external_id=requirement_external_id,
            scenario_id=scenario_id,
            name=test_case_name,
            token=token,
            diagnostics=diagnostics,
            auth_state=auth_state,
        )

        if existing_test_case.test_case_id:
            reused_test_case_ids.append(existing_test_case.test_case_id)
            all_test_case_ids.append(existing_test_case.test_case_id)
            test_case_sync_details.append(
                {
                    "scenarioId": scenario_id,
                    "title": test_case_name,
                    "testCaseId": existing_test_case.test_case_id,
                    "syncAction": "Reused",
                    "matchStrategy": existing_test_case.strategy,
                }
            )
            progress.reused_test_case_ids = [str(test_case_id) for test_case_id in reused_test_case_ids]
            progress.test_case_ids = [str(test_case_id) for test_case_id in all_test_case_ids]
            progress.test_case_sync_details = list(test_case_sync_details)
            progress.reuse_search_succeeded = True
            continue

        test_case_response = _http_json(
            "POST",
            _join_url(base_url, f"/api/v2/{resolved_project_id}/testcases"),
            token,
            test_case_payload,
            diagnostics,
            auth_state,
        )
        created_test_case_id = _extract_response_id(test_case_response, "Create test case")
        created_test_case_ids.append(created_test_case_id)
        all_test_case_ids.append(created_test_case_id)
        test_case_sync_details.append(
            {
                "scenarioId": scenario_id,
                "title": test_case_name,
                "testCaseId": created_test_case_id,
                "syncAction": "Created",
                "matchStrategy": "createdNew",
            }
        )
        progress.created_test_case_ids = [str(test_case_id) for test_case_id in created_test_case_ids]
        progress.test_case_ids = [str(test_case_id) for test_case_id in all_test_case_ids]
        progress.test_case_sync_details = list(test_case_sync_details)

    progress.created_test_case_ids = [str(test_case_id) for test_case_id in created_test_case_ids]
    progress.reused_test_case_ids = [str(test_case_id) for test_case_id in reused_test_case_ids]
    progress.test_case_ids = [str(test_case_id) for test_case_id in all_test_case_ids]
    progress.test_case_sync_details = list(test_case_sync_details)
    progress.reuse_search_succeeded = progress.reuse_search_attempted

    _http_json(
        "POST",
        _join_url(
            base_url,
            f"/api/v2/{resolved_project_id}/requirements/{created_requirement_id}/assigntestcases",
        ),
        token,
        {"testCaseIds": all_test_case_ids},
        diagnostics,
        auth_state,
    )

    test_set_response = _http_json(
        "POST",
        _join_url(base_url, f"/api/v2/{resolved_project_id}/testsets"),
        token,
        test_set_payload,
        diagnostics,
        auth_state,
    )
    created_test_set_id = _extract_response_id(test_set_response, "Create test set")
    progress.test_set_id = created_test_set_id

    assign_payload_shape = _assign_test_cases_to_test_set(
        base_url=base_url,
        project_id=resolved_project_id,
        test_set_id=created_test_set_id,
        test_case_ids=all_test_case_ids,
        token=token,
        diagnostics=diagnostics,
        progress=progress,
        auth_state=auth_state,
    )

    return RealSyncResult(
        requirement_id=created_requirement_id,
        test_case_ids=all_test_case_ids,
        created_test_case_ids=created_test_case_ids,
        reused_test_case_ids=reused_test_case_ids,
        test_case_sync_details=test_case_sync_details,
        test_set_id=created_test_set_id,
        assign_test_set_payload_shape=assign_payload_shape,
    )


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
        if any(key in payload for key in ("errors", "propertyName", "validationErrors")):
            return json.dumps(payload, separators=(",", ":"), ensure_ascii=False)

        for key in ("message", "error_description", "error", "title", "detail"):
            value = payload.get(key)
            if value:
                return str(value)

        errors = payload.get("errors")
        if isinstance(errors, dict):
            parts: list[str] = []
            for field, messages in errors.items():
                if isinstance(messages, list):
                    parts.append(f"{field}: {'; '.join(str(item) for item in messages)}")
                else:
                    parts.append(f"{field}: {messages}")
            if parts:
                return "; ".join(parts)

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


def build_sync_plan(payload: dict[str, Any]) -> Output:
    requirement_id = str(payload.get("requirementId") or "").strip()
    project_id = str(payload.get("testManagerProjectId") or "").strip()
    project_key = str(payload.get("testManagerProjectKey") or "").strip()
    input_project_prefix = str(payload.get("testManagerProjectPrefix") or "").strip()
    project_name = str(payload.get("testManagerProjectName") or "").strip()
    sync_mode = normalize_sync_mode(payload.get("syncMode", "DryRun"))
    scenarios = payload.get("testScenarios")

    blocked_reasons: list[str] = []
    if not requirement_id:
        blocked_reasons.append("Invalid input: requirementId is required.")
    if not project_key:
        blocked_reasons.append("Invalid input: testManagerProjectKey is required.")
    if not isinstance(scenarios, list) or len(scenarios) == 0:
        blocked_reasons.append("Invalid input: testScenarios is required and cannot be empty.")

    if blocked_reasons:
        return failed_output(
            requirement_id=requirement_id,
            project_id=project_id,
            project_key=project_key,
            project_name=project_name,
            sync_mode=sync_mode,
            blocked_reasons=blocked_reasons,
        )

    requirement_external_id = f"ADO-{requirement_id}"
    requirement_payload = {
        "externalId": requirement_external_id,
        "name": str(payload.get("requirementTitle") or "").strip(),
        "description": str(payload.get("requirementDescription") or "").strip(),
    }

    test_case_payloads: list[dict[str, Any]] = []
    requirement_links: list[dict[str, Any]] = []
    test_set_membership: list[dict[str, Any]] = []
    test_set_name, test_set_description = select_test_set(str(payload.get("riskLevel") or ""))

    for scenario in scenarios:
        if not isinstance(scenario, dict):
            scenario = {}
        scenario_id = str(scenario.get("scenarioId") or "").strip()
        scenario_title = clean_duplicate_consecutive_words(
            str(scenario.get("scenarioTitle") or "").strip()
        )
        steps = scenario.get("steps") if isinstance(scenario.get("steps"), list) else []
        expected_result = str(scenario.get("expectedResult") or "")

        test_case_payloads.append(
            {
                "scenarioId": scenario_id,
                "foreignReference": "-".join(
                    part for part in (requirement_external_id, scenario_id) if part
                ),
                "name": f"{scenario_id} - {scenario_title}".strip(" -"),
                "priority": str(scenario.get("priority") or "").strip(),
                "testType": str(scenario.get("testType") or "").strip(),
                "steps": [
                    {
                        "stepNumber": index + 1,
                        "action": str(step),
                        "expectedResult": expected_result if index == len(steps) - 1 else "",
                    }
                    for index, step in enumerate(steps)
                ],
            }
        )
        requirement_links.append(
            {
                "requirementExternalId": requirement_external_id,
                "scenarioId": scenario_id,
                "linkType": "RequirementToTestCase",
            }
        )
        test_set_membership.append(
            {
                "testSetName": test_set_name,
                "scenarioId": scenario_id,
            }
        )

    test_set_payload = {
        "name": test_set_name,
        "environment": str(payload.get("environment") or "").strip(),
        "description": test_set_description,
    }

    if sync_mode == "DryRun":
        return Output(
            syncStatus="ReadyToSync",
            syncMode=sync_mode,
            requirementId=requirement_id,
            testManagerProjectId=project_id,
            testManagerProjectKey=project_key,
            testManagerProjectName=project_name,
            requirementPayload=requirement_payload,
            testCasePayloads=test_case_payloads,
            requirementLinks=requirement_links,
            testSetPayload=test_set_payload,
            testSetMembership=test_set_membership,
            summary=Summary(
                requirementsPrepared=1,
                testCasesPrepared=len(test_case_payloads),
                linksPrepared=len(requirement_links),
                testSetsPrepared=1,
            ),
            blockedReasons=[],
            nextAction="Review prepared payloads and rerun with syncMode RealSync to call UiPath Test Manager APIs.",
        )

    test_manager_config = _resolve_test_manager_config()
    token = test_manager_config.get("TEST_MANAGER_BEARER_TOKEN", "")
    auth_token_present = bool(token)
    auth_header_prepared = auth_token_present
    base_url_used = test_manager_config.get("TEST_MANAGER_BASE_URL", "")
    project_prefix = (
        test_manager_config.get("TEST_MANAGER_PROJECT_PREFIX")
        or input_project_prefix
        or project_key
    ).strip()
    first_endpoint_path = (
        _project_lookup_path(project_prefix)
        if project_prefix
        else f"/api/v2/{project_id}/requirements"
    )
    request_diagnostics = RequestDiagnostics(
        request_url_used=(
            _join_url(base_url_used, first_endpoint_path)
            if base_url_used and first_endpoint_path
            else ""
        ),
        request_headers_prepared=_safe_header_diagnostics(
            _headers_for_request("GET" if project_prefix else "POST", token)
        )
        if token
        else {
            "AuthorizationPresent": False,
            "Accept": "application/json",
            "Content-Type": "" if project_prefix else "application/json",
        },
    )
    token_starts_with_bearer_prefix = (
        test_manager_config.get("_TEST_MANAGER_TOKEN_STARTS_WITH_BEARER_PREFIX") == "true"
    )
    missing_config: list[str] = []
    if not test_manager_config.get("TEST_MANAGER_BEARER_TOKEN"):
        missing_config.append("TEST_MANAGER_BEARER_TOKEN is required for RealSync.")
    if not test_manager_config.get("TEST_MANAGER_BASE_URL"):
        missing_config.append("TEST_MANAGER_BASE_URL is required for RealSync.")
    if not project_id and not project_prefix:
        missing_config.append("TEST_MANAGER_PROJECT_PREFIX or testManagerProjectKey is required when projectId is empty.")

    if missing_config:
        return configuration_required_output(
            requirement_id=requirement_id,
            project_id=project_id,
            project_key=project_key,
            project_name=project_name,
            blocked_reasons=missing_config,
            auth_token_present=auth_token_present,
            auth_header_prepared=auth_header_prepared,
            base_url_used=base_url_used,
            first_endpoint_path=first_endpoint_path,
            token_length=len(token),
            token_fingerprint=_token_fingerprint(token),
            token_starts_with_bearer_prefix=token_starts_with_bearer_prefix,
            request_diagnostics=request_diagnostics,
        )

    real_sync_progress = RealSyncProgress()
    try:
        sync_result = _run_real_sync(
            config=test_manager_config,
            project_id=project_id,
            project_prefix=project_prefix,
            requirement_payload=requirement_payload,
            test_case_payloads=test_case_payloads,
            test_set_payload=test_set_payload,
            diagnostics=request_diagnostics,
            progress=real_sync_progress,
        )
    except TmApiError as exc:
        return failed_output(
            requirement_id=requirement_id,
            project_id=project_id,
            project_key=project_key,
            project_name=project_name,
            sync_mode="RealSync",
            blocked_reasons=[_format_api_error(exc, test_manager_config)],
            real_sync_attempted=True,
            auth_token_present=auth_token_present,
            auth_header_prepared=auth_header_prepared,
            base_url_used=base_url_used,
            first_endpoint_path=first_endpoint_path,
            token_length=len(token),
            token_fingerprint=_token_fingerprint(token),
            token_starts_with_bearer_prefix=token_starts_with_bearer_prefix,
            request_diagnostics=request_diagnostics,
            created_requirement=real_sync_progress.requirement_id,
            created_test_cases=real_sync_progress.created_test_case_ids,
            reused_test_case_ids=real_sync_progress.reused_test_case_ids,
            all_test_case_ids=real_sync_progress.test_case_ids,
            test_case_sync_details=real_sync_progress.test_case_sync_details,
            reuse_search_attempted=real_sync_progress.reuse_search_attempted,
            reuse_search_succeeded=real_sync_progress.reuse_search_succeeded,
            created_test_set=real_sync_progress.test_set_id,
            assign_test_set_payload_shape=real_sync_progress.assign_test_set_payload_shape,
            failed_endpoint_path=exc.endpoint_path,
        )

    return Output(
        syncStatus="Completed",
        syncMode=sync_mode,
        requirementId=requirement_id,
        testManagerProjectId=project_id,
        testManagerProjectKey=project_key,
        testManagerProjectName=project_name,
        requirementPayload=requirement_payload,
        testCasePayloads=test_case_payloads,
        requirementLinks=[
            {
                **link,
                "createdRequirementId": sync_result.requirement_id,
                "createdTestCaseIds": sync_result.created_test_case_ids,
                "reusedTestCaseIds": sync_result.reused_test_case_ids,
                "allTestCaseIds": sync_result.test_case_ids,
            }
            for link in requirement_links
        ],
        testSetPayload={**test_set_payload, "createdTestSetId": sync_result.test_set_id},
        testSetMembership=test_set_membership,
        summary=Summary(
            requirementsPrepared=1,
            testCasesPrepared=len(test_case_payloads),
            linksPrepared=len(requirement_links),
            testSetsPrepared=1,
        ),
        blockedReasons=[],
        nextAction="UiPath Test Manager sync completed.",
        realSyncAttempted=True,
        authTokenPresent=auth_token_present,
        authHeaderPrepared=auth_header_prepared,
        baseUrlUsed=base_url_used,
        firstEndpointPath=first_endpoint_path,
        tokenLength=len(token),
        tokenFingerprint=_token_fingerprint(token),
        tokenStartsWithBearerPrefix=token_starts_with_bearer_prefix,
        requestUrlUsed=request_diagnostics.request_url_used,
        requestHeadersPrepared=request_diagnostics.request_headers_prepared or {},
        responseContentType=request_diagnostics.response_content_type,
        responseStatusCode=request_diagnostics.response_status_code,
        tokenRefreshAttempted=request_diagnostics.token_refresh_attempted,
        tokenRefreshSucceeded=request_diagnostics.token_refresh_succeeded,
        retryAttempted=request_diagnostics.retry_attempted,
        createdRequirement=sync_result.requirement_id,
        createdTestCases=sync_result.created_test_case_ids,
        createdTestSet=sync_result.test_set_id,
        createdTestCaseIds=sync_result.created_test_case_ids,
        reusedTestCaseIds=sync_result.reused_test_case_ids,
        allTestCaseIds=sync_result.test_case_ids,
        createdTestSetId=sync_result.test_set_id,
        testCaseReuseEnabled=True,
        testCaseSyncDetails=sync_result.test_case_sync_details,
        reuseSearchAttempted=True,
        reuseSearchSucceeded=True,
        createdCount=len(sync_result.created_test_case_ids),
        reusedCount=len(sync_result.reused_test_case_ids),
        assignTestSetPayloadShape=sync_result.assign_test_set_payload_shape,
    )


def failed_output(
    requirement_id: str = "",
    project_id: str = "",
    project_key: str = "",
    project_name: str = "",
    sync_mode: str = "DryRun",
    blocked_reasons: list[str] | None = None,
    real_sync_attempted: bool = False,
    auth_token_present: bool = False,
    auth_header_prepared: bool = False,
    base_url_used: str = "",
    first_endpoint_path: str = "",
    token_length: int = 0,
    token_fingerprint: str = "",
    token_starts_with_bearer_prefix: bool = False,
    request_diagnostics: RequestDiagnostics | None = None,
    created_requirement: str = "",
    created_test_cases: list[str] | None = None,
    reused_test_case_ids: list[str] | None = None,
    all_test_case_ids: list[str] | None = None,
    test_case_sync_details: list[dict[str, Any]] | None = None,
    reuse_search_attempted: bool = False,
    reuse_search_succeeded: bool = False,
    created_test_set: str = "",
    assign_test_set_payload_shape: str = "",
    failed_endpoint_path: str = "",
) -> Output:
    request_diagnostics = request_diagnostics or RequestDiagnostics()
    created_test_cases = created_test_cases or []
    reused_test_case_ids = reused_test_case_ids or []
    all_test_case_ids = all_test_case_ids or [*created_test_cases, *reused_test_case_ids]
    test_case_sync_details = test_case_sync_details or []
    return Output(
        syncStatus="Failed",
        syncMode=sync_mode or "DryRun",
        requirementId=requirement_id,
        testManagerProjectId=project_id,
        testManagerProjectKey=project_key,
        testManagerProjectName=project_name,
        requirementPayload=None,
        testCasePayloads=[],
        requirementLinks=[],
        testSetPayload=None,
        testSetMembership=[],
        summary=Summary(),
        blockedReasons=blocked_reasons or [],
        nextAction="Fix blocked reasons before syncing to UiPath Test Manager.",
        realSyncAttempted=real_sync_attempted,
        authTokenPresent=auth_token_present,
        authHeaderPrepared=auth_header_prepared,
        baseUrlUsed=base_url_used,
        firstEndpointPath=first_endpoint_path,
        tokenLength=token_length,
        tokenFingerprint=token_fingerprint,
        tokenStartsWithBearerPrefix=token_starts_with_bearer_prefix,
        requestUrlUsed=request_diagnostics.request_url_used,
        requestHeadersPrepared=request_diagnostics.request_headers_prepared or {},
        responseContentType=request_diagnostics.response_content_type,
        responseStatusCode=request_diagnostics.response_status_code,
        tokenRefreshAttempted=request_diagnostics.token_refresh_attempted,
        tokenRefreshSucceeded=request_diagnostics.token_refresh_succeeded,
        retryAttempted=request_diagnostics.retry_attempted,
        createdRequirement=created_requirement,
        createdTestCases=created_test_cases,
        createdTestSet=created_test_set,
        createdTestCaseIds=created_test_cases,
        reusedTestCaseIds=reused_test_case_ids,
        allTestCaseIds=all_test_case_ids,
        createdTestSetId=created_test_set,
        testCaseReuseEnabled=True,
        testCaseSyncDetails=test_case_sync_details,
        reuseSearchAttempted=reuse_search_attempted,
        reuseSearchSucceeded=reuse_search_succeeded,
        createdCount=len(created_test_cases),
        reusedCount=len(reused_test_case_ids),
        assignTestSetPayloadShape=assign_test_set_payload_shape,
        failedEndpointPath=failed_endpoint_path,
    )


def configuration_required_output(
    requirement_id: str = "",
    project_id: str = "",
    project_key: str = "",
    project_name: str = "",
    blocked_reasons: list[str] | None = None,
    auth_token_present: bool = False,
    auth_header_prepared: bool = False,
    base_url_used: str = "",
    first_endpoint_path: str = "",
    token_length: int = 0,
    token_fingerprint: str = "",
    token_starts_with_bearer_prefix: bool = False,
    request_diagnostics: RequestDiagnostics | None = None,
) -> Output:
    request_diagnostics = request_diagnostics or RequestDiagnostics()
    return Output(
        syncStatus="ConfigurationRequired",
        syncMode="RealSync",
        requirementId=requirement_id,
        testManagerProjectId=project_id,
        testManagerProjectKey=project_key,
        testManagerProjectName=project_name,
        requirementPayload=None,
        testCasePayloads=[],
        requirementLinks=[],
        testSetPayload=None,
        testSetMembership=[],
        summary=Summary(),
        blockedReasons=blocked_reasons or ["TEST_MANAGER_BEARER_TOKEN is required for RealSync."],
        nextAction="Configure TEST_MANAGER_BEARER_TOKEN and Test Manager API settings to perform real sync.",
        realSyncAttempted=True,
        authTokenPresent=auth_token_present,
        authHeaderPrepared=auth_header_prepared,
        baseUrlUsed=base_url_used,
        firstEndpointPath=first_endpoint_path,
        tokenLength=token_length,
        tokenFingerprint=token_fingerprint,
        tokenStartsWithBearerPrefix=token_starts_with_bearer_prefix,
        requestUrlUsed=request_diagnostics.request_url_used,
        requestHeadersPrepared=request_diagnostics.request_headers_prepared or {},
        responseContentType=request_diagnostics.response_content_type,
        responseStatusCode=request_diagnostics.response_status_code,
        tokenRefreshAttempted=request_diagnostics.token_refresh_attempted,
        tokenRefreshSucceeded=request_diagnostics.token_refresh_succeeded,
        retryAttempted=request_diagnostics.retry_attempted,
    )


@traced()
async def main(input: Input) -> Output:
    try:
        payload = json.loads(input.question or "{}")
    except json.JSONDecodeError as exc:
        return failed_output(blocked_reasons=[f"Invalid input: question must be valid JSON. {exc.msg}."])

    if not isinstance(payload, dict):
        return failed_output(blocked_reasons=["Invalid input: question must be a JSON object."])

    return build_sync_plan(payload)
