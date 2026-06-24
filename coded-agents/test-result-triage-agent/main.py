from __future__ import annotations

import hashlib
import base64
import html
import json
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote, urljoin, urlparse

import requests
from pydantic import BaseModel, Field

try:
    from uipath.tracing import traced
except ImportError:  # Allows local static tests before the UiPath SDK is installed.
    def traced(*args: Any, **kwargs: Any):  # type: ignore[no-redef]
        if args and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(func: Any) -> Any:
            return func

        return decorator


SUPPORTED_MODES = {"listExecutions", "analyzeExecution", "createDefect"}
TEST_MANAGER_BASE_URL = "https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_"
TEST_MANAGER_ASSET_NAMES = (
    "TEST_MANAGER_BEARER_TOKEN",
    "TEST_MANAGER_REFRESH_TOKEN",
    "TEST_MANAGER_CLIENT_ID",
    "TEST_MANAGER_CLIENT_SECRET",
)
AZURE_DEVOPS_ASSET_NAMES = (
    "AzureDevOps_Org",
    "AzureDevOps_Project",
    "AzureDevOps_PAT",
)


class Input(BaseModel):
    question: str | None = None
    variationId: str | None = None
    mode: str | None = None
    projectId: str | None = None
    testExecutionId: str | None = None
    testCaseId: str | None = None
    testCaseName: str | None = None
    runtimeType: str | None = None
    robotName: str | None = None
    hostMachineName: str | None = None
    automationTestCaseName: str | None = None
    linkToTestCaseLog: str | None = None
    classification: str | None = None
    evidence: str | None = None
    recommendedAction: str | None = None
    adoParentId: str | None = None


class Output(BaseModel):
    status: str
    mode: str | None = None
    projectId: str | None = None
    result: dict[str, Any] = Field(default_factory=dict)
    blockedReasons: list[str] = Field(default_factory=list)
    nextAction: str | None = None


@dataclass
class AuthDiagnostics:
    bearerTokenPresent: bool = False
    bearerTokenSource: str = "asset"
    tokenRefreshAttempted: bool = False
    tokenRefreshSucceeded: bool = False
    tokenFingerprint: str = ""
    tokenLength: int = 0
    baseUrlUsed: str = ""
    requestUrlUsed: str = ""
    failedEndpointPath: str = ""
    responseStatusCode: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "bearerTokenPresent": self.bearerTokenPresent,
            "bearerTokenSource": self.bearerTokenSource,
            "tokenRefreshAttempted": self.tokenRefreshAttempted,
            "tokenRefreshSucceeded": self.tokenRefreshSucceeded,
            "tokenFingerprint": self.tokenFingerprint,
            "tokenLength": self.tokenLength,
            "baseUrlUsed": self.baseUrlUsed,
            "requestUrlUsed": self.requestUrlUsed,
            "failedEndpointPath": self.failedEndpointPath,
            "responseStatusCode": self.responseStatusCode,
        }


class MissingBearerTokenAssetError(RuntimeError):
    pass


PRODUCT_DEFECT_TERMS = [
    "Verification failed",
    "Assertion failed",
    "Expected",
    "Actual",
    "did not match",
    "warning message not displayed",
    "Saved status after update operation",
]

AUTOMATION_ISSUE_TERMS = [
    "Could not find the user-interface",
    "UI element",
    "selector",
    "Strict selector failure",
    "Multiple similar matches",
    "Cannot communicate with the browser",
    "browser extension",
    "active session",
]

ENVIRONMENT_ISSUE_TERMS = [
    "HTTP 503",
    "Service Unavailable",
    "database connection timeout",
    "dependent API",
    "environment",
    "service did not respond",
    "timeout occurred while retrieving test data",
]

DATA_ISSUE_TERMS = [
    "test data",
    "missing data",
    "invalid input data",
    "data setup",
]

CLASSIFICATION_RULES = [
    ("Product Defect", PRODUCT_DEFECT_TERMS),
    ("Automation Issue", AUTOMATION_ISSUE_TERMS),
    ("Environment Issue", ENVIRONMENT_ISSUE_TERMS),
    ("Data Issue", DATA_ISSUE_TERMS),
]


def _json_response(status: str, mode: str | None, project_id: str | None, result: dict[str, Any]) -> Output:
    return Output(status=status, mode=mode, projectId=project_id, result=result)


def _failed_response(blocked_reason: str, next_action: str, mode: str | None = None, project_id: str | None = None) -> Output:
    return Output(
        status="Failed",
        mode=mode,
        projectId=project_id,
        blockedReasons=[blocked_reason],
        nextAction=next_action,
    )


def _merge_input(input_data: Input) -> tuple[Input | None, Output | None]:
    question_fields: dict[str, Any] = {}
    if input_data.question:
        try:
            parsed = json.loads(input_data.question)
        except json.JSONDecodeError:
            return None, _failed_response(
                "question must contain valid JSON.",
                "Provide question as a valid JSON string or pass mode and projectId directly.",
                input_data.mode,
                input_data.projectId,
            )
        if not isinstance(parsed, dict):
            return None, _failed_response(
                "question JSON must be an object.",
                "Provide question as a JSON object string with mode and projectId.",
                input_data.mode,
                input_data.projectId,
            )
        question_fields = parsed

    direct_fields = {
        key: value
        for key, value in input_data.model_dump().items()
        if key != "question" and value not in (None, "")
    }
    merged = {**question_fields, **direct_fields}
    merged.setdefault("question", input_data.question)
    resolved = Input(**merged)

    if not resolved.mode or not resolved.projectId:
        return None, _failed_response(
            "mode and projectId are required.",
            "Provide mode and projectId.",
            resolved.mode,
            resolved.projectId,
        )
    if resolved.mode not in SUPPORTED_MODES:
        return None, _failed_response(
            f"Unsupported mode: {resolved.mode}",
            "Use one of: listExecutions, analyzeExecution, createDefect.",
            resolved.mode,
            resolved.projectId,
        )
    return resolved, None


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _redact_secret(key, _redact(item)) for key, item in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return _redact_secret("", value)
    return value


def _redact_secret(key: str, value: Any) -> Any:
    safe_diagnostic_keys = {
        "bearerTokenPresent",
        "bearerTokenSource",
        "tokenRefreshAttempted",
        "tokenRefreshSucceeded",
        "tokenFingerprint",
        "tokenLength",
        "baseUrlUsed",
        "requestUrlUsed",
        "failedEndpointPath",
        "responseStatusCode",
    }
    if key in safe_diagnostic_keys:
        return value
    sensitive_key = any(
        token in key.lower() for token in ["token", "secret", "authorization", "bearer", "password", "cookie"]
    )
    if sensitive_key:
        return "***REDACTED***"
    if not isinstance(value, str):
        return value
    redacted = re.sub(r"Bearer\s+[A-Za-z0-9._\-+/=]+", "Bearer ***REDACTED***", value, flags=re.IGNORECASE)
    redacted = re.sub(
        r"(?i)\b(access_token|refresh_token|client_secret|authorization|password|cookie|cookies)(['\"\s:=]+)([^,'\"\s}]+)",
        "***REDACTED***",
        redacted,
    )
    return redacted


def _diagnostics_for_token(token: str, diagnostics: AuthDiagnostics) -> None:
    normalized = _normalize_bearer_token(token)
    diagnostics.bearerTokenPresent = bool(normalized)
    diagnostics.bearerTokenSource = "asset"
    diagnostics.tokenLength = len(normalized)
    diagnostics.tokenFingerprint = _token_fingerprint(normalized)


def _normalize_bearer_token(value: str) -> str:
    token = str(value or "").strip()
    if token.casefold().startswith("bearer "):
        token = token[7:]
    return re.sub(r"\s+", "", token)


def _token_fingerprint(token: str) -> str:
    if not token:
        return ""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()[:8]


def _with_diagnostics(result: dict[str, Any], diagnostics: AuthDiagnostics) -> dict[str, Any]:
    merged = dict(result)
    merged["diagnostics"] = diagnostics.to_dict()
    return merged


def _join_url(base_url: str, path: str) -> str:
    return f"{str(base_url).strip().rstrip('/')}/{str(path).lstrip('/')}"


def _endpoint_path(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or url
    return f"{path}?{parsed.query}" if parsed.query else path


def classify_failure(text: str) -> dict[str, Any]:
    haystack = text.lower()
    for classification, terms in CLASSIFICATION_RULES:
        matched = [term for term in terms if term.lower() in haystack]
        if matched:
            return {
                "classification": classification,
                "matchedTerms": matched,
                "recommendedAction": _recommended_action(classification),
            }

    return {
        "classification": "Needs Review",
        "matchedTerms": [],
        "recommendedAction": _recommended_action("Needs Review"),
    }


def _recommended_action(classification: str) -> str:
    actions = {
        "Product Defect": "Create a product defect and assign it to the application team.",
        "Automation Issue": "Review automation selector, browser, package, or workflow stability.",
        "Environment Issue": "Check environment availability, dependent services, database/API connectivity, and test data setup.",
        "Data Issue": "Review test data setup and required input data.",
        "Needs Review": "Manually inspect logs and failure evidence.",
    }
    return actions[classification]


def _collect_failure_text(value: Any) -> str:
    fragments: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, dict):
            for key, item in node.items():
                if isinstance(item, str) and _is_failure_text_key(str(key)):
                    fragments.append(item)
                else:
                    visit(item)
        elif isinstance(node, list):
            for item in node:
                visit(item)
        elif isinstance(node, str):
            fragments.append(node)

    visit(value)
    return "\n".join(fragment for fragment in fragments if fragment)


def _is_failure_text_key(key: str) -> bool:
    normalized = key.lower()
    return any(token in normalized for token in ["message", "error", "failure", "actual", "expected", "log", "details"])


def _require(value: str | None, field_name: str) -> str:
    if not value:
        raise ValueError(f"{field_name} is required")
    return value


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
    return _read_named_assets(TEST_MANAGER_ASSET_NAMES)


def _read_azure_devops_asset_config() -> dict[str, str]:
    return _read_named_assets(AZURE_DEVOPS_ASSET_NAMES)


def _read_named_assets(asset_names: tuple[str, ...]) -> dict[str, str]:
    sdk = _create_uipath_client()
    values: dict[str, str] = {}

    for name in asset_names:
        try:
            values[name] = _retrieve_asset_value(sdk, name)
        except Exception:
            values[name] = ""

    return values


def _asset_value(name: str) -> str:
    return _read_asset_config().get(name, "").strip()


def _base_url() -> str:
    return TEST_MANAGER_BASE_URL.rstrip("/")


def _identity_url(base_url: str) -> str:
    configured = os.getenv("UIPATH_IDENTITY_URL")
    if configured:
        return configured.rstrip("/") + "/"
    if "staging.uipath.com" in base_url:
        return "https://staging.uipath.com/identity_/"
    if "cloud.uipath.com" in base_url:
        return "https://cloud.uipath.com/identity_/"
    return urljoin(base_url, "identity_/")


class TestManagerClient:
    def __init__(self) -> None:
        self.diagnostics = AuthDiagnostics()
        self.asset_config = _read_asset_config()
        bearer_token = _normalize_bearer_token(self.asset_config.get("TEST_MANAGER_BEARER_TOKEN", ""))
        _diagnostics_for_token(bearer_token, self.diagnostics)
        if not bearer_token:
            raise MissingBearerTokenAssetError("TEST_MANAGER_BEARER_TOKEN asset could not be read from Orchestrator.")

        self.base_url = _base_url()
        self.diagnostics.baseUrlUsed = self.base_url
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {bearer_token}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }
        )

    def list_executions(self, project_id: str) -> dict[str, Any]:
        return self._get(f"/api/v2/{project_id}/testexecutions")

    def execution_results(self, project_id: str, execution_id: str) -> dict[str, Any]:
        candidates = [
            f"/api/v2/{project_id}/testexecutions/{execution_id}/results",
            f"/api/v2/{project_id}/testexecutions/{execution_id}",
        ]
        return self._first_success("GET", candidates)

    def execution_summary(self, project_id: str, execution_id: str) -> dict[str, Any]:
        return self._get(f"/api/v2/{project_id}/testexecutions/{execution_id}/withStats")

    def test_case_logs(self, project_id: str, execution_id: str) -> dict[str, Any]:
        return self._get(
            f"/api/v2/{project_id}/testcaselogs/testexecution/{execution_id}/paged"
            "?Top=50&Skip=0&Search=&OrderBy=ExecutionEnd%20desc"
        )

    def robot_logs(self, project_id: str, execution_id: str, test_case_id: str) -> dict[str, Any]:
        return self._get(
            f"/api/v2/{project_id}/orchestrator/testexecution/{execution_id}/robotlogs/paged"
            f"?Top=25&Skip=0&OrderBy=Timestamp%20desc&testcaseid={test_case_id}"
        )

    def assertions(self, project_id: str, test_case_log_id: str) -> dict[str, Any]:
        return self._get(f"/api/v2/{project_id}/testcaselogartifacts/{test_case_log_id}/assertions")

    def create_defect(self, project_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        candidates = [
            f"/api/v2/{project_id}/defects",
            f"/api/v2/{project_id}/testexecutions/{payload['testExecutionId']}/defects",
        ]
        return self._first_success("POST", candidates, json=payload)

    def _get(self, path: str) -> dict[str, Any]:
        request_url = _join_url(self.base_url, path)
        self.diagnostics.requestUrlUsed = request_url
        self.diagnostics.failedEndpointPath = ""
        response = self.session.get(request_url, timeout=60)
        self.diagnostics.responseStatusCode = response.status_code
        if response.status_code == 401:
            self._refresh_access_token()
            response = self.session.get(request_url, timeout=60)
            self.diagnostics.responseStatusCode = response.status_code
        if not response.ok:
            self.diagnostics.failedEndpointPath = _endpoint_path(request_url)
        return _parse_response(response)

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request_url = _join_url(self.base_url, path)
        self.diagnostics.requestUrlUsed = request_url
        self.diagnostics.failedEndpointPath = ""
        response = self.session.post(request_url, json=payload, timeout=60)
        self.diagnostics.responseStatusCode = response.status_code
        if response.status_code == 401:
            self._refresh_access_token()
            response = self.session.post(request_url, json=payload, timeout=60)
            self.diagnostics.responseStatusCode = response.status_code
        if not response.ok:
            self.diagnostics.failedEndpointPath = _endpoint_path(request_url)
        return _parse_response(response)

    def _first_success(self, method: str, paths: list[str], json: dict[str, Any] | None = None) -> dict[str, Any]:
        errors: list[dict[str, Any]] = []
        for path in paths:
            try:
                if method == "GET":
                    return self._get(path)
                return self._post(path, json or {})
            except requests.HTTPError as error:
                response = error.response
                if response is None or response.status_code not in {404, 405}:
                    raise
                errors.append({"path": path, "statusCode": response.status_code})

        raise RuntimeError(f"No Test Manager endpoint candidate succeeded: {errors}")

    def _refresh_access_token(self) -> None:
        self.diagnostics.tokenRefreshAttempted = True
        refresh_token = self.asset_config.get("TEST_MANAGER_REFRESH_TOKEN", "").strip()
        client_id = self.asset_config.get("TEST_MANAGER_CLIENT_ID", "").strip()
        client_secret = self.asset_config.get("TEST_MANAGER_CLIENT_SECRET", "").strip()
        response = requests.post(
            urljoin(_identity_url(self.base_url), "connect/token"),
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=60,
        )
        data = _parse_response(response)
        access_token = data.get("access_token")
        if not access_token:
            raise RuntimeError("Token refresh response did not include access_token")
        normalized_access_token = _normalize_bearer_token(access_token)
        self.session.headers["Authorization"] = f"Bearer {normalized_access_token}"
        self.diagnostics.tokenRefreshSucceeded = True
        _diagnostics_for_token(normalized_access_token, self.diagnostics)


def _parse_response(response: requests.Response) -> dict[str, Any]:
    if not response.ok:
        response.raise_for_status()
    if not response.content:
        return {}
    try:
        data = response.json()
    except ValueError:
        return {"raw": response.text}
    return data if isinstance(data, dict) else {"items": data}


def _blocked_defect_response(blocked_reason: str, next_action: str) -> dict[str, Any]:
    return {
        "status": "Blocked",
        "defectCreationStatus": "Blocked",
        "blockedReason": blocked_reason,
        "nextAction": next_action,
    }


def _azure_devops_base_url(org: str) -> str:
    org = str(org or "").strip().strip("/")
    return f"https://dev.azure.com/{org}"


def _azure_devops_basic_auth_header(pat: str) -> str:
    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("ascii")
    return f"Basic {token}"


def _bug_title(test_case_name: str | None, classification: str | None) -> str:
    name = _bug_field_text(test_case_name or "Test case").strip() or "Test case"
    triage = _bug_field_text(classification or "Needs Review").strip() or "Needs Review"
    return f"[QualityOps] {name} - {triage}"


def _bug_field_text(value: Any) -> str:
    return str(_redact(value) or "")


def _bug_description(input_data: Input) -> str:
    classification = html.escape(_bug_field_text(input_data.classification or "Needs Review"))
    recommended_action = html.escape(_bug_field_text(input_data.recommendedAction))
    test_case_name = html.escape(_bug_field_text(input_data.testCaseName))
    evidence = html.escape(_bug_field_text(input_data.evidence))
    test_execution_id = html.escape(_bug_field_text(input_data.testExecutionId))
    test_case_id = html.escape(_bug_field_text(input_data.testCaseId))
    link = _bug_field_text(input_data.linkToTestCaseLog).strip()
    escaped_link = html.escape(link, quote=True)
    evidence_link = (
        f'<a href="{escaped_link}">Open Test Manager Evidence</a>'
        if link
        else "Not provided"
    )
    return (
        "<h2>QualityOps Automated Test Failure</h2>"
        f"<p><b>Classification:</b> {classification}</p>"
        f"<p><b>Recommended Action:</b><br/>{recommended_action}</p>"
        f"<p><b>Test Case:</b><br/>{test_case_name}</p>"
        f"<p><b>Test Manager Evidence:</b><br/>{evidence_link}</p>"
        "<h3>Failure Evidence</h3>"
        f"<pre>{evidence}</pre>"
        "<h3>Execution Details</h3>"
        "<ul>"
        f"<li><b>Test Execution ID:</b> {test_execution_id}</li>"
        f"<li><b>Test Case ID:</b> {test_case_id}</li>"
        f"<li><b>Classification:</b> {classification}</li>"
        "<li><b>Generated By:</b> QualityOps Test Result Triage Agent</li>"
        "</ul>"
    )


def _bug_repro_steps(input_data: Input) -> str:
    return (
        "<ol>"
        "<li>Open the Test Manager Evidence link.</li>"
        "<li>Review the failed automated test case.</li>"
        "<li>Check the failure evidence and robot logs.</li>"
        "<li>Validate the impacted application behavior or automation/environment issue.</li>"
        "</ol>"
    )


def _bug_system_info(input_data: Input) -> str:
    classification = _bug_field_text(input_data.classification or "Needs Review")
    lines = [
        "Generated by: QualityOps Test Result Triage Agent",
        "Source: UiPath Test Manager",
        "Execution Type: Automated",
        f"Classification: {classification}",
        f"Test Execution ID: {_bug_field_text(input_data.testExecutionId)}",
        f"Test Case ID: {_bug_field_text(input_data.testCaseId)}",
        f"Test Manager Evidence: {_bug_field_text(input_data.linkToTestCaseLog)}",
    ]
    return "<br/>".join(
        html.escape(line, quote=False)
        for line in lines
    )


def _build_azure_devops_bug_payload(
    input_data: Input,
    org: str,
    project: str,
    include_optional_template_fields: bool = True,
) -> list[dict[str, Any]]:
    parent_id = str(input_data.adoParentId or "").strip()
    encoded_project = quote(project, safe="")
    parent_url = f"{_azure_devops_base_url(org)}/{encoded_project}/_apis/wit/workItems/{quote(parent_id, safe='')}"
    classification = str(input_data.classification or "Needs Review").strip() or "Needs Review"
    payload = [
        {
            "op": "add",
            "path": "/fields/System.Title",
            "value": _bug_title(input_data.testCaseName, classification),
        },
        {
            "op": "add",
            "path": "/fields/System.Description",
            "value": _bug_description(input_data),
        },
        {
            "op": "add",
            "path": "/fields/System.Tags",
            "value": f"QualityOps; Automated Triage; {classification}; UiPath Test Manager",
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Common.Priority",
            "value": 2,
        },
        {
            "op": "add",
            "path": "/fields/Microsoft.VSTS.Common.Severity",
            "value": "3 - Medium",
        },
        {
            "op": "add",
            "path": "/relations/-",
            "value": {
                "rel": "System.LinkTypes.Hierarchy-Reverse",
                "url": parent_url,
                "attributes": {
                    "comment": "Linked by QualityOps automated test result triage",
                },
            },
        },
    ]
    if include_optional_template_fields:
        payload[3:3] = [
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.TCM.ReproSteps",
                "value": _bug_repro_steps(input_data),
            },
            {
                "op": "add",
                "path": "/fields/Microsoft.VSTS.TCM.SystemInfo",
                "value": _bug_system_info(input_data),
            },
        ]
    return payload


def _post_azure_devops_bug(request_url: str, headers: dict[str, str], payload: list[dict[str, Any]]) -> requests.Response:
    return requests.post(
        request_url,
        headers=headers,
        json=payload,
        timeout=60,
    )


def _create_azure_devops_bug(input_data: Input) -> dict[str, Any]:
    parent_id = str(input_data.adoParentId or "").strip()
    if not parent_id:
        return _blocked_defect_response(
            "adoParentId is required to link the Azure DevOps Bug to a parent work item.",
            "Provide adoParentId with the PBI or User Story work item ID.",
        )

    config = _read_azure_devops_asset_config()
    org = config.get("AzureDevOps_Org", "").strip()
    project = config.get("AzureDevOps_Project", "").strip()
    pat = config.get("AzureDevOps_PAT", "").strip()

    if not pat:
        return _blocked_defect_response(
            "AzureDevOps_PAT asset could not be read from Orchestrator.",
            "Verify the existing AzureDevOps_PAT asset is available to this agent.",
        )
    if not org:
        return _blocked_defect_response(
            "AzureDevOps_Org asset could not be read from Orchestrator.",
            "Verify the existing AzureDevOps_Org asset is available to this agent.",
        )
    if not project:
        return _blocked_defect_response(
            "AzureDevOps_Project asset could not be read from Orchestrator.",
            "Verify the existing AzureDevOps_Project asset is available to this agent.",
        )

    encoded_project = quote(project, safe="")
    base_url = _azure_devops_base_url(org)
    request_url = f"{base_url}/{encoded_project}/_apis/wit/workitems/$Bug?api-version=7.1-preview.3"
    headers = {
        "Content-Type": "application/json-patch+json",
        "Authorization": _azure_devops_basic_auth_header(pat),
    }
    payload = _build_azure_devops_bug_payload(input_data, org, project, include_optional_template_fields=True)
    response = _post_azure_devops_bug(request_url, headers, payload)
    if response.status_code in {401, 403}:
        return _blocked_defect_response(
            "Azure DevOps bug creation failed due to PAT permission. PAT requires Work Items Read & Write.",
            "Update AzureDevOps_PAT permissions and retry createDefect.",
        )
    optional_template_fields_added = True
    if response.status_code == 400:
        payload = _build_azure_devops_bug_payload(input_data, org, project, include_optional_template_fields=False)
        response = _post_azure_devops_bug(request_url, headers, payload)
        optional_template_fields_added = False
        if response.status_code in {401, 403}:
            return _blocked_defect_response(
                "Azure DevOps bug creation failed due to PAT permission. PAT requires Work Items Read & Write.",
                "Update AzureDevOps_PAT permissions and retry createDefect.",
            )

    data = _parse_response(response)
    bug_id = str(data.get("id") or "")
    bug_url = f"{base_url}/{encoded_project}/_workitems/edit/{quote(bug_id, safe='')}"
    return {
        "status": "Completed",
        "defectCreationStatus": "Created",
        "defectSystem": "Azure DevOps",
        "adoBugId": bug_id,
        "adoParentId": parent_id,
        "adoBugUrl": bug_url,
        "classification": input_data.classification or "",
        "evidenceAdded": True,
        "optionalTemplateFieldsAdded": optional_template_fields_added,
        "testCaseName": input_data.testCaseName or "",
        "ui": {
            "message": "Azure DevOps Bug created successfully",
            "bugId": bug_id,
            "parentId": parent_id,
            "classification": input_data.classification or "",
            "testCaseName": input_data.testCaseName or "",
            "actions": [
                {"label": "Open ADO Bug", "url": bug_url},
                {"label": "Open Test Manager Evidence", "url": input_data.linkToTestCaseLog or ""},
            ],
        },
        "nextAction": "Review the created bug in Azure DevOps.",
    }


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _safe_parse_json_string(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped:
        return value
    if not ((stripped.startswith("{") and stripped.endswith("}")) or (stripped.startswith("[") and stripped.endswith("]"))):
        return value
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        return value


def _result_rows(response: dict[str, Any]) -> list[dict[str, Any]]:
    rows = response.get("data", [])
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def _is_failed_result_row(row: dict[str, Any]) -> bool:
    return row.get("result") == "Failed" or row.get("businessResult") == "Failed"


def _execution_summary(response: dict[str, Any], test_execution_id: str) -> dict[str, Any]:
    passed = _safe_int(response.get("passed"))
    failed = _safe_int(response.get("failed"))
    skipped = _safe_int(response.get("none"))
    return {
        "testExecutionId": response.get("id") or test_execution_id,
        "executionName": response.get("name"),
        "testManagerStatus": response.get("status"),
        "executionType": response.get("executionType"),
        "runtimeType": response.get("runtimeType"),
        "totalTests": passed + failed + skipped,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
    }


def _data_or_items(response: dict[str, Any]) -> list[Any]:
    for key in ("data", "items"):
        value = response.get(key)
        if isinstance(value, list):
            return value
    return []


def _robot_log_message(log: Any) -> str:
    if not isinstance(log, dict):
        return str(log) if log else ""
    level = log.get("level") or log.get("Level") or log.get("logLevel") or log.get("LogLevel") or ""
    message = (
        log.get("message")
        or log.get("Message")
        or log.get("rawMessage")
        or log.get("RawMessage")
        or log.get("details")
        or log.get("Details")
        or ""
    )
    if isinstance(message, dict | list):
        message = json.dumps(message, ensure_ascii=False)
    return f"{level}: {message}".strip(": ") if message else ""


def _is_failed_or_warning_log(log: Any) -> bool:
    if not isinstance(log, dict):
        return bool(log)
    level = str(log.get("level") or log.get("Level") or log.get("logLevel") or log.get("LogLevel") or "").lower()
    message = str(log.get("message") or log.get("Message") or log.get("rawMessage") or log.get("RawMessage") or "")
    return level in {"error", "fatal", "warn", "warning"} or any(
        token in message.lower() for token in ("failed", "failure", "warning", "exception", "error")
    )


def _assertion_evidence(assertions_response: dict[str, Any]) -> list[str]:
    evidence: list[str] = []
    for assertion in _data_or_items(assertions_response):
        if not isinstance(assertion, dict):
            if assertion:
                evidence.append(str(assertion))
            continue
        status = str(assertion.get("result") or assertion.get("status") or assertion.get("businessResult") or "").lower()
        text = _collect_failure_text(assertion)
        if "fail" in status or text:
            evidence.append(text or json.dumps(assertion, ensure_ascii=False))
    return evidence


def _format_evidence(parts: list[tuple[str, Any]]) -> str:
    lines: list[str] = []
    for label, value in parts:
        parsed = _safe_parse_json_string(value)
        text = _collect_failure_text(parsed) if isinstance(parsed, dict | list) else str(parsed or "")
        text = text.strip()
        if text:
            lines.append(f"{label}: {text}")
    return "\n".join(lines)


def _test_case_log_link(test_execution_id: str, test_case_id: str) -> str:
    return _join_url(_base_url(), f"/QQTP/testexecution-results/{test_execution_id}/{test_case_id}")


@traced(name="list_test_manager_executions", span_type="tool")
def list_executions(project_id: str) -> dict[str, Any]:
    client = TestManagerClient()
    return _with_diagnostics(client.list_executions(project_id), client.diagnostics)


@traced(name="analyze_test_manager_execution", span_type="tool")
def analyze_execution(project_id: str, test_execution_id: str) -> dict[str, Any]:
    client = TestManagerClient()
    summary_response = client.execution_summary(project_id, test_execution_id)
    execution_summary_url = client.diagnostics.requestUrlUsed
    execution_summary_status = client.diagnostics.responseStatusCode
    execution_summary = _execution_summary(summary_response, test_execution_id)

    test_case_logs_response = client.test_case_logs(project_id, test_execution_id)
    test_case_logs_url = client.diagnostics.requestUrlUsed
    test_case_logs_status = client.diagnostics.responseStatusCode
    rows = _result_rows(test_case_logs_response)
    failed_rows = [row for row in rows if _is_failed_result_row(row)]

    triage_results: list[dict[str, Any]] = []
    robot_logs_fetched_count = 0
    assertions_fetched_count = 0

    for row in failed_rows:
        test_case_log_id = str(row.get("id") or "")
        test_case_id = str(row.get("testCaseId") or "")
        test_case = row.get("testCase") if isinstance(row.get("testCase"), dict) else {}
        test_case_name = str(test_case.get("name") or "")
        package_entry_point_name = str(test_case.get("packageEntryPointName") or "")
        automation_test_case_name = str(row.get("automationTestCaseName") or "")
        result_status = str(row.get("result") or row.get("businessResult") or row.get("status") or "Failed")

        robot_logs_response = client.robot_logs(project_id, test_execution_id, test_case_id)
        robot_logs_fetched_count += 1
        robot_log_messages = [
            _robot_log_message(log)
            for log in _data_or_items(robot_logs_response)
            if _is_failed_or_warning_log(log)
        ]

        assertions_response = client.assertions(project_id, test_case_log_id)
        assertions_fetched_count += 1
        failed_assertions = _assertion_evidence(assertions_response)

        evidence = _format_evidence(
            [
                ("Info", row.get("info")),
                ("Robot logs", "\n".join(message for message in robot_log_messages if message)),
                ("Assertions", "\n".join(failed_assertions)),
                ("Automation test case", automation_test_case_name),
                ("Package entry point", package_entry_point_name),
            ]
        )
        classification = classify_failure(evidence)
        triage_results.append(
            {
                "testCaseId": test_case_id,
                "testCaseLogId": test_case_log_id,
                "testCaseName": test_case_name,
                "resultStatus": result_status,
                "classification": classification["classification"],
                "matchedTerms": classification["matchedTerms"],
                "evidence": evidence,
                "recommendedAction": classification["recommendedAction"],
                "linkToTestCaseLog": _test_case_log_link(test_execution_id, test_case_id),
                "variationId": str(row.get("variationId") or ""),
                "robotName": str(row.get("robotName") or ""),
                "hostMachineName": str(row.get("hostMachineName") or ""),
                "automationTestCaseName": automation_test_case_name,
            }
        )

    result = {
        "status": "Completed",
        "executionSummary": execution_summary,
        "triageResults": triage_results,
        "overallRecommendation": f"{len(triage_results)} failed test results found and classified.",
        "diagnostics": {
            "executionSummaryUrlUsed": execution_summary_url,
            "executionSummaryResponseStatusCode": execution_summary_status,
            "testCaseLogsUrlUsed": test_case_logs_url,
            "testCaseLogsResponseStatusCode": test_case_logs_status,
            "totalResultRows": len(rows),
            "failedResultRows": len(failed_rows),
            "robotLogsFetchedCount": robot_logs_fetched_count,
            "assertionsFetchedCount": assertions_fetched_count,
            **client.diagnostics.to_dict(),
        },
    }
    return result


@traced(name="create_azure_devops_bug", span_type="tool")
def create_defect(input_data: Input) -> dict[str, Any]:
    return _create_azure_devops_bug(input_data)


@traced()
async def main(input: Input) -> Output:
    resolved_input, failure = _merge_input(input)
    if failure:
        return failure
    assert resolved_input is not None

    try:
        if resolved_input.mode == "listExecutions":
            result = list_executions(_require(resolved_input.projectId, "projectId"))
        elif resolved_input.mode == "analyzeExecution":
            result = analyze_execution(
                _require(resolved_input.projectId, "projectId"),
                _require(resolved_input.testExecutionId, "testExecutionId"),
            )
        elif resolved_input.mode == "createDefect":
            result = create_defect(resolved_input)
        else:
            raise ValueError(f"Unsupported mode: {resolved_input.mode}")
        return _json_response("success", resolved_input.mode, resolved_input.projectId, _redact(result))
    except MissingBearerTokenAssetError:
        return _failed_response(
            "TEST_MANAGER_BEARER_TOKEN asset could not be read from Orchestrator.",
            "Verify asset access in the QualityOpsAgent folder.",
            resolved_input.mode,
            resolved_input.projectId,
        )
    except Exception as error:
        return _json_response(
            "error",
            resolved_input.mode,
            resolved_input.projectId,
            _redact({"message": str(error), "errorType": type(error).__name__}),
        )
