import json
from asyncio import run
from typing import Any
from urllib import parse

from main import (
    Input,
    TmApiError,
    _asset_to_string,
    _http_json,
    _join_url,
    clean_duplicate_consecutive_words,
    main,
    lookup_test_manager_project_by_prefix,
)


class FakeAsset:
    def __init__(self, **values: Any) -> None:
        for key, value in values.items():
            setattr(self, key, value)


class FakeAssets:
    def __init__(self, values: dict[str, FakeAsset]) -> None:
        self.values = values

    def retrieve(self, name: str | None = None, *args: Any, **kwargs: Any) -> FakeAsset:
        assert args == ()
        if name is None:
            name = kwargs.pop("name", None)
        else:
            assert kwargs == {}
        assert kwargs == {}
        if name not in self.values:
            raise RuntimeError("missing asset")
        return self.values[name]


class FakeUiPath:
    def __init__(self, values: dict[str, FakeAsset]) -> None:
        self.assets = FakeAssets(values)


def base_question(**overrides):
    payload = {
        "requirementId": "26",
        "submittedBy": "Dhruba",
        "environment": "SQA",
        "testManagerProjectId": "3dae45a4-6fc3-0000-60f6-0b49c244dbb8",
        "testManagerProjectKey": "QQTP",
        "testManagerProjectName": "QualityOps QA Test Project",
        "requirementTitle": "Validate End-to-End Patient Care Workflow",
        "requirementDescription": "Validate complete patient care workflow.",
        "riskLevel": "High",
        "testScenarios": [
            {
                "scenarioId": "TS-001",
                "scenarioTitle": "Validate End-to-End Patient Care Workflow happy path",
                "priority": "High",
                "testType": "Functional",
                "steps": [
                    "Create a patient with mandatory fields",
                    "Search for the created patient",
                ],
                "expectedResult": "Patient workflow is completed successfully.",
            }
        ],
        "syncMode": "DryRun",
    }
    payload.update(overrides)
    return json.dumps(payload)


def call_agent(question: str):
    return run(main(Input(question=question)))


def clear_test_manager_env(monkeypatch):
    for name in (
        "TEST_MANAGER_BEARER_TOKEN",
        "TEST_MANAGER_BASE_URL",
        "TEST_MANAGER_PROJECT_PREFIX",
        "TEST_MANAGER_REFRESH_TOKEN",
        "TEST_MANAGER_CLIENT_ID",
        "TEST_MANAGER_CLIENT_SECRET",
        "TEST_MANAGER_TOKEN_URL",
    ):
        monkeypatch.delenv(name, raising=False)


def configure_realsync_assets(
    monkeypatch,
    *,
    token: str | None = "super-secret-test-token",
    token_asset: FakeAsset | dict[str, Any] | None = None,
    base_url: str = "https://example.testmanager",
    project_prefix: str = "QQTP",
    refresh_token: str | None = None,
    client_id: str | None = None,
    client_secret: str | None = None,
    token_url: str | None = None,
):
    values = {
        "TEST_MANAGER_BASE_URL": FakeAsset(value=base_url),
        "TEST_MANAGER_PROJECT_PREFIX": FakeAsset(value=project_prefix),
    }
    if token_asset is not None:
        values["TEST_MANAGER_BEARER_TOKEN"] = token_asset
    elif token:
        values["TEST_MANAGER_BEARER_TOKEN"] = FakeAsset(secret_value=token)
    if refresh_token is not None:
        values["TEST_MANAGER_REFRESH_TOKEN"] = FakeAsset(secret_value=refresh_token)
    if client_id is not None:
        values["TEST_MANAGER_CLIENT_ID"] = FakeAsset(value=client_id)
    if client_secret is not None:
        values["TEST_MANAGER_CLIENT_SECRET"] = FakeAsset(secret_value=client_secret)
    if token_url is not None:
        values["TEST_MANAGER_TOKEN_URL"] = FakeAsset(value=token_url)

    monkeypatch.setattr("main._create_uipath_client", lambda: FakeUiPath(values))


def install_successful_http_mock(monkeypatch):
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def __init__(self, payload: dict[str, Any]) -> None:
            self.payload = payload
            self.text = json.dumps(payload)

        def json(self):
            return self.payload

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        calls.append({"method": "GET", "url": url, "headers": headers, "body": None})
        assert timeout == 30
        assert headers == {
            "Authorization": "Bearer super-secret-test-token",
            "Accept": "application/json",
        }
        if url.endswith("/api/v2/projects/prefix/QQTP"):
            return FakeResponse({"id": "project-from-prefix"})
        if "/api/v2/project-from-prefix/testcases?" in url:
            return FakeResponse({"value": []})
        raise AssertionError(f"Unexpected API call: GET {url}")

    def fake_post(url: str, headers: dict[str, str], json=None, timeout: int = 30):
        calls.append({"method": "POST", "url": url, "headers": headers, "body": json})
        assert timeout == 30
        assert headers == {
            "Authorization": "Bearer super-secret-test-token",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if url.endswith("/project-from-prefix/requirements"):
            return FakeResponse({"id": "created-requirement-id"})
        if url.endswith("/project-from-prefix/testcases"):
            return FakeResponse({"id": "created-testcase-id"})
        if url.endswith("/project-from-prefix/requirements/created-requirement-id/assigntestcases"):
            return FakeResponse({})
        if url.endswith("/project-from-prefix/testsets"):
            return FakeResponse({"id": "created-testset-id"})
        if url.endswith("/project-from-prefix/testsets/created-testset-id/assigntestcases"):
            return FakeResponse({})

        raise AssertionError(f"Unexpected API call: POST {url}")

    monkeypatch.setattr("main.requests.get", fake_get)
    monkeypatch.setattr("main.requests.post", fake_post)
    return calls


def test_successful_dry_run(monkeypatch):
    clear_test_manager_env(monkeypatch)
    monkeypatch.setattr(
        "main._create_uipath_client",
        lambda: (_ for _ in ()).throw(AssertionError("DryRun should not read assets")),
    )

    result = call_agent(base_question())

    assert result.syncStatus == "ReadyToSync"
    assert result.syncMode == "DryRun"
    assert result.realSyncAttempted is False
    assert result.authTokenPresent is False
    assert result.authHeaderPrepared is False
    assert result.testManagerProjectId == "3dae45a4-6fc3-0000-60f6-0b49c244dbb8"
    assert result.requirementPayload == {
        "externalId": "ADO-26",
        "name": "Validate End-to-End Patient Care Workflow",
        "description": "Validate complete patient care workflow.",
    }
    assert result.testCasePayloads[0]["name"] == (
        "TS-001 - Validate End-to-End Patient Care Workflow happy path"
    )
    assert result.testCasePayloads[0]["foreignReference"] == "ADO-26-TS-001"
    assert result.testCasePayloads[0]["steps"][0]["expectedResult"] == ""
    assert result.testCasePayloads[0]["steps"][1]["expectedResult"] == (
        "Patient workflow is completed successfully."
    )
    assert result.summary.testCasesPrepared == 1
    assert result.blockedReasons == []


def test_realsync_without_token_returns_configuration_required(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch, token=None)
    monkeypatch.setattr(
        "main._http_json",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("No API call without token")),
    )

    result = call_agent(base_question(syncMode="RealSync"))

    assert result.syncStatus == "ConfigurationRequired"
    assert result.syncMode == "RealSync"
    assert result.syncStatus != "ReadyToSync"
    assert result.realSyncAttempted is True
    assert result.authTokenPresent is False
    assert result.authHeaderPrepared is False
    assert result.tokenLength == 0
    assert result.tokenFingerprint == ""
    assert result.baseUrlUsed == "https://example.testmanager"
    assert result.firstEndpointPath == "/api/v2/projects/prefix/QQTP"
    assert result.requestUrlUsed == "https://example.testmanager/api/v2/projects/prefix/QQTP"
    assert result.requestHeadersPrepared == {
        "AuthorizationPresent": False,
        "Accept": "application/json",
        "Content-Type": "",
    }
    assert result.requirementId == "26"
    assert result.testManagerProjectId == "3dae45a4-6fc3-0000-60f6-0b49c244dbb8"
    assert result.testManagerProjectKey == "QQTP"
    assert result.testManagerProjectName == "QualityOps QA Test Project"
    assert result.summary.requirementsPrepared == 0
    assert result.summary.testCasesPrepared == 0
    assert result.summary.linksPrepared == 0
    assert result.summary.testSetsPrepared == 0
    assert result.blockedReasons == ["TEST_MANAGER_BEARER_TOKEN is required for RealSync."]
    assert result.nextAction == (
        "Configure TEST_MANAGER_BEARER_TOKEN and Test Manager API settings to perform real sync."
    )


def test_text_asset_token_is_read(monkeypatch):
    clear_test_manager_env(monkeypatch)
    token = "super-secret-test-token"
    configure_realsync_assets(monkeypatch, token_asset=FakeAsset(value=token))
    calls = install_successful_http_mock(monkeypatch)

    result = call_agent(base_question(syncMode="RealSync"))
    serialized = result.model_dump_json()

    assert result.syncStatus == "Completed"
    assert result.syncStatus != "ConfigurationRequired"
    assert result.authTokenPresent is True
    assert result.tokenLength == len(token)
    assert result.tokenFingerprint == "402c827b"
    assert calls[0]["headers"]["Authorization"] == f"Bearer {token}"
    assert token not in serialized


def test_secret_asset_token_nested_value_is_read(monkeypatch):
    clear_test_manager_env(monkeypatch)
    token = "super-secret-test-token"
    configure_realsync_assets(
        monkeypatch,
        token_asset=FakeAsset(value={"secretValue": token}),
    )
    calls = install_successful_http_mock(monkeypatch)

    result = call_agent(base_question(syncMode="RealSync"))
    serialized = result.model_dump_json()

    assert result.syncStatus == "Completed"
    assert result.syncStatus != "ConfigurationRequired"
    assert result.authTokenPresent is True
    assert result.authHeaderPrepared is True
    assert result.tokenLength == len(token)
    assert result.tokenFingerprint == "402c827b"
    assert calls[0]["headers"]["Authorization"] == f"Bearer {token}"
    assert token not in serialized


def test_secret_asset_dict_with_nested_object_is_read():
    token = "super-secret-test-token"

    result = _asset_to_string(
        {
            "name": "TEST_MANAGER_BEARER_TOKEN",
            "value": {
                "type": "Secret",
                "value": {
                    "SecretValue": token,
                },
            },
        }
    )

    assert result == token


def test_realsync_with_mocked_successful_api_calls_returns_completed(monkeypatch):
    clear_test_manager_env(monkeypatch)
    token = "super-secret-test-token"
    configure_realsync_assets(monkeypatch, token=token)
    calls = install_successful_http_mock(monkeypatch)

    result = call_agent(base_question(syncMode="RealSync"))
    serialized = result.model_dump_json()

    assert result.syncStatus == "Completed"
    assert result.syncMode == "RealSync"
    assert result.syncStatus != "ReadyToSync"
    assert result.realSyncAttempted is True
    assert result.authTokenPresent is True
    assert result.authHeaderPrepared is True
    assert result.baseUrlUsed == "https://example.testmanager"
    assert result.firstEndpointPath == "/api/v2/projects/prefix/QQTP"
    assert result.tokenLength == len(token)
    assert result.tokenFingerprint == "402c827b"
    assert result.tokenStartsWithBearerPrefix is False
    assert result.requestUrlUsed == "https://example.testmanager/api/v2/projects/prefix/QQTP"
    assert result.requestHeadersPrepared == {
        "AuthorizationPresent": True,
        "Accept": "application/json",
        "Content-Type": "",
    }
    assert result.responseStatusCode == 200
    assert result.responseContentType == "application/json"
    assert result.createdRequirement == "created-requirement-id"
    assert result.createdTestCases == ["created-testcase-id"]
    assert result.createdTestSet == "created-testset-id"
    assert result.createdTestCaseIds == ["created-testcase-id"]
    assert result.reusedTestCaseIds == []
    assert result.allTestCaseIds == ["created-testcase-id"]
    assert result.createdTestSetId == "created-testset-id"
    assert result.testCaseReuseEnabled is True
    assert result.assignTestSetPayloadShape == "array"
    assert result.summary.requirementsPrepared == 1
    assert result.summary.testCasesPrepared == 1
    assert result.summary.linksPrepared == 1
    assert result.summary.testSetsPrepared == 1
    assert result.blockedReasons == []
    assert token not in serialized
    assert "Bearer super-secret-test-token" not in serialized
    assert [call["method"] for call in calls] == [
        "GET",
        "POST",
        "GET",
        "GET",
        "GET",
        "GET",
        "POST",
        "POST",
        "POST",
        "POST",
    ]
    assert calls[0]["url"].endswith("/api/v2/projects/prefix/QQTP")
    assert calls[1]["url"].endswith("/api/v2/project-from-prefix/requirements")
    assert calls[2]["url"].endswith("/api/v2/project-from-prefix/testcases?search=ADO-26-TS-001")
    assert calls[3]["url"].endswith(
        "/api/v2/project-from-prefix/testcases?search=TS-001"
    )
    assert calls[4]["url"].endswith(
        "/api/v2/project-from-prefix/testcases?search=TS-001+-+Validate+End-to-End+Patient+Care+Workflow+happy+path"
    )
    assert calls[5]["url"].endswith("/api/v2/project-from-prefix/testcases?search=ADO-26")
    assert calls[6]["url"].endswith("/api/v2/project-from-prefix/testcases")
    assert calls[7]["url"].endswith(
        "/api/v2/project-from-prefix/requirements/created-requirement-id/assigntestcases"
    )
    assert calls[8]["url"].endswith("/api/v2/project-from-prefix/testsets")
    assert calls[9]["url"].endswith(
        "/api/v2/project-from-prefix/testsets/created-testset-id/assigntestcases"
    )
    assert calls[9]["body"] == ["created-testcase-id"]
    assert "TS-001" not in calls[9]["body"]


def test_realsync_reuses_existing_test_case_by_foreign_reference(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch)
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def __init__(self, payload: dict[str, Any]) -> None:
            self.payload = payload
            self.text = json.dumps(payload)

        def json(self):
            return self.payload

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        calls.append({"method": "GET", "url": url, "headers": headers, "body": None})
        if url.endswith("/api/v2/projects/prefix/QQTP"):
            return FakeResponse({"id": "project-from-prefix"})
        if url.endswith("/api/v2/project-from-prefix/testcases?search=ADO-26-TS-001"):
            return FakeResponse(
                {
                    "value": [
                        {
                            "id": "existing-testcase-id",
                            "foreignReference": "ADO-26-TS-001",
                            "name": "TS-001 - Validate End-to-End Patient Care Workflow happy path",
                        }
                    ]
                }
            )
        raise AssertionError(f"Unexpected API call: GET {url}")

    def fake_post(url: str, headers: dict[str, str], json=None, timeout: int = 30):
        calls.append({"method": "POST", "url": url, "headers": headers, "body": json})
        if url.endswith("/project-from-prefix/requirements"):
            return FakeResponse({"id": "created-requirement-id"})
        if url.endswith("/project-from-prefix/testcases"):
            raise AssertionError("Existing test case should be reused, not recreated")
        if url.endswith("/project-from-prefix/requirements/created-requirement-id/assigntestcases"):
            return FakeResponse({})
        if url.endswith("/project-from-prefix/testsets"):
            return FakeResponse({"id": "created-testset-id"})
        if url.endswith("/project-from-prefix/testsets/created-testset-id/assigntestcases"):
            return FakeResponse({})
        raise AssertionError(f"Unexpected API call: POST {url}")

    monkeypatch.setattr("main.requests.get", fake_get)
    monkeypatch.setattr("main.requests.post", fake_post)

    result = call_agent(base_question(syncMode="RealSync"))

    assert result.syncStatus == "Completed"
    assert result.createdTestCaseIds == []
    assert result.reusedTestCaseIds == ["existing-testcase-id"]
    assert result.allTestCaseIds == ["existing-testcase-id"]
    assert result.createdTestSetId == "created-testset-id"
    assert result.testCaseReuseEnabled is True
    assert calls[3]["body"] == {"testCaseIds": ["existing-testcase-id"]}
    assert calls[5]["body"] == ["existing-testcase-id"]
    assert all(not call["url"].endswith("/project-from-prefix/testcases") for call in calls)


def install_stateful_test_case_reuse_mock(monkeypatch):
    calls: list[dict[str, Any]] = []
    existing_test_cases: list[dict[str, Any]] = []
    counters = {"requirement": 0, "testcase": 0, "testset": 0}

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"Content-Type": "application/json"}

        def __init__(self, payload: dict[str, Any]) -> None:
            self.payload = payload
            self.text = json.dumps(payload)

        def json(self):
            return self.payload

    def search_value(url: str) -> str:
        parsed = parse.urlparse(url)
        return parse.parse_qs(parsed.query).get("search", [""])[0].casefold()

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        calls.append({"method": "GET", "url": url, "headers": headers, "body": None})
        if url.endswith("/api/v2/projects/prefix/QQTP"):
            return FakeResponse({"id": "project-from-prefix"})
        if "/api/v2/project-from-prefix/testcases?" in url:
            query = search_value(url)
            return FakeResponse(
                {
                    "value": [
                        item
                        for item in existing_test_cases
                        if query in json.dumps(item).casefold()
                    ]
                }
            )
        raise AssertionError(f"Unexpected API call: GET {url}")

    def fake_post(url: str, headers: dict[str, str], json=None, timeout: int = 30):
        calls.append({"method": "POST", "url": url, "headers": headers, "body": json})
        if url.endswith("/project-from-prefix/requirements"):
            counters["requirement"] += 1
            return FakeResponse({"id": f"created-requirement-id-{counters['requirement']}"})
        if url.endswith("/project-from-prefix/testcases"):
            counters["testcase"] += 1
            test_case_id = f"created-testcase-id-{counters['testcase']}"
            existing_test_cases.append(
                {
                    "id": test_case_id,
                    "foreignReference": json.get("foreignReference", ""),
                    "scenarioId": json.get("scenarioId", ""),
                    "name": json.get("name", ""),
                    "description": f"Requirement ADO-26 scenario {json.get('scenarioId', '')}",
                }
            )
            return FakeResponse({"id": test_case_id})
        if "/requirements/" in url and url.endswith("/assigntestcases"):
            return FakeResponse({})
        if url.endswith("/project-from-prefix/testsets"):
            counters["testset"] += 1
            return FakeResponse({"id": f"created-testset-id-{counters['testset']}"})
        if "/testsets/" in url and url.endswith("/assigntestcases"):
            return FakeResponse({})
        raise AssertionError(f"Unexpected API call: POST {url}")

    monkeypatch.setattr("main.requests.get", fake_get)
    monkeypatch.setattr("main.requests.post", fake_post)
    return calls, existing_test_cases


def multi_scenario_question(*, title_suffix: str = "", syncMode: str = "RealSync"):
    scenarios = []
    for index in range(1, 9):
        scenarios.append(
            {
                "scenarioId": f"TS-{index:03d}",
                "scenarioTitle": f"Scenario {index} validates patient workflow{title_suffix}",
                "priority": "High",
                "testType": "Functional",
                "steps": [f"Execute scenario {index}"],
                "expectedResult": f"Scenario {index} succeeds.",
            }
        )
    return base_question(testScenarios=scenarios, syncMode=syncMode)


def test_second_realsync_reuses_all_same_requirement_scenarios(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch)
    calls, _existing_test_cases = install_stateful_test_case_reuse_mock(monkeypatch)

    first = call_agent(multi_scenario_question())
    second = call_agent(multi_scenario_question())

    assert first.syncStatus == "Completed"
    assert first.createdCount == 8
    assert first.reusedCount == 0
    assert first.createdTestCaseIds == [f"created-testcase-id-{index}" for index in range(1, 9)]
    assert first.allTestCaseIds == first.createdTestCaseIds
    assert [detail["syncAction"] for detail in first.testCaseSyncDetails] == ["Created"] * 8
    assert second.syncStatus == "Completed"
    assert second.createdCount == 0
    assert second.reusedCount == 8
    assert second.createdTestCaseIds == []
    assert second.reusedTestCaseIds == [f"created-testcase-id-{index}" for index in range(1, 9)]
    assert second.allTestCaseIds == second.reusedTestCaseIds
    assert second.createdTestSetId == "created-testset-id-2"
    assert second.testCaseReuseEnabled is True
    assert second.reuseSearchAttempted is True
    assert second.reuseSearchSucceeded is True
    assert [detail["scenarioId"] for detail in second.testCaseSyncDetails] == [
        f"TS-{index:03d}" for index in range(1, 9)
    ]
    assert [detail["matchStrategy"] for detail in second.testCaseSyncDetails] == [
        "foreignReference"
    ] * 8
    test_case_posts = [
        call for call in calls if call["method"] == "POST" and call["url"].endswith("/project-from-prefix/testcases")
    ]
    assert len(test_case_posts) == 8


def test_title_change_with_same_scenario_id_reuses_test_case(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch)
    _calls, existing_test_cases = install_stateful_test_case_reuse_mock(monkeypatch)

    first = call_agent(multi_scenario_question())
    for item in existing_test_cases:
        item.pop("foreignReference", None)
        item["name"] = f"Old generated title for {item['scenarioId']}"

    second = call_agent(multi_scenario_question(title_suffix=" with updated wording"))

    assert first.createdCount == 8
    assert second.createdCount == 0
    assert second.reusedCount == 8
    assert second.allTestCaseIds == [f"created-testcase-id-{index}" for index in range(1, 9)]
    assert [detail["matchStrategy"] for detail in second.testCaseSyncDetails] == ["scenarioId"] * 8


def test_realsync_401_refreshes_token_and_retries_failed_call(monkeypatch):
    clear_test_manager_env(monkeypatch)
    old_token = "expired-access-token"
    new_token = "fresh-access-token"
    old_refresh_token = "old-refresh-token"
    new_refresh_token = "new-refresh-token"
    client_secret = "super-secret-client-secret"
    token_url = "https://staging.uipath.com/hackathon26_182/identity_/connect/token"
    configure_realsync_assets(
        monkeypatch,
        token=old_token,
        refresh_token=old_refresh_token,
        client_id="client-id",
        client_secret=client_secret,
        token_url=token_url,
    )
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        headers = {"Content-Type": "application/json"}

        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self.payload = payload
            self.ok = 200 <= status_code < 300
            self.text = json.dumps(payload)

        def json(self):
            return self.payload

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        calls.append({"method": "GET", "url": url, "headers": headers, "body": None})
        if len([call for call in calls if call["method"] == "GET"]) == 1:
            return FakeResponse(401, {"error": "invalid_token"})
        assert headers["Authorization"] == f"Bearer {new_token}"
        return FakeResponse(200, {"id": "project-from-prefix"})

    def fake_post(url: str, headers: dict[str, str], json=None, data=None, timeout: int = 30):
        calls.append(
            {
                "method": "POST",
                "url": url,
                "headers": headers,
                "body": json,
                "data": data,
            }
        )
        if url == token_url:
            assert headers == {"Content-Type": "application/x-www-form-urlencoded"}
            assert data == {
                "grant_type": "refresh_token",
                "client_id": "client-id",
                "client_secret": client_secret,
                "refresh_token": old_refresh_token,
            }
            return FakeResponse(
                200,
                {
                    "access_token": new_token,
                    "refresh_token": new_refresh_token,
                    "expires_in": 3600,
                    "token_type": "Bearer",
                },
            )
        assert headers["Authorization"] == f"Bearer {new_token}"
        if url.endswith("/project-from-prefix/requirements"):
            return FakeResponse(200, {"id": "created-requirement-id"})
        if url.endswith("/project-from-prefix/testcases"):
            return FakeResponse(200, {"id": "created-testcase-id"})
        if url.endswith("/project-from-prefix/requirements/created-requirement-id/assigntestcases"):
            return FakeResponse(200, {})
        if url.endswith("/project-from-prefix/testsets"):
            return FakeResponse(200, {"id": "created-testset-id"})
        if url.endswith("/project-from-prefix/testsets/created-testset-id/assigntestcases"):
            return FakeResponse(200, {})
        raise AssertionError(f"Unexpected API call: POST {url}")

    monkeypatch.setattr("main.requests.get", fake_get)
    monkeypatch.setattr("main.requests.post", fake_post)

    result = call_agent(base_question(syncMode="RealSync"))
    serialized = result.model_dump_json()

    assert result.syncStatus == "Completed"
    assert result.syncStatus != "ReadyToSync"
    assert result.tokenRefreshAttempted is True
    assert result.tokenRefreshSucceeded is True
    assert result.retryAttempted is True
    assert [call["method"] for call in calls] == [
        "GET",
        "POST",
        "GET",
        "POST",
        "GET",
        "GET",
        "GET",
        "GET",
        "POST",
        "POST",
        "POST",
        "POST",
    ]
    assert calls[0]["headers"]["Authorization"] == f"Bearer {old_token}"
    assert calls[2]["headers"]["Authorization"] == f"Bearer {new_token}"
    assert old_token not in serialized
    assert new_token not in serialized
    assert old_refresh_token not in serialized
    assert new_refresh_token not in serialized
    assert client_secret not in serialized
    assert "Authorization" not in result.requestHeadersPrepared


def test_realsync_401_missing_refresh_config_returns_failed(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch, token="expired-access-token")

    class FakeResponse:
        ok = False
        status_code = 401
        headers = {"Content-Type": "application/json"}
        text = '{"error":"invalid_token"}'

        def json(self):
            return {"error": "invalid_token"}

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        return FakeResponse()

    monkeypatch.setattr("main.requests.get", fake_get)

    result = call_agent(base_question(syncMode="RealSync"))
    serialized = result.model_dump_json()

    assert result.syncStatus == "Failed"
    assert result.syncMode == "RealSync"
    assert result.syncStatus != "ReadyToSync"
    assert result.blockedReasons == [
        "Test Manager token expired and refresh configuration is missing."
    ]
    assert result.tokenRefreshAttempted is True
    assert result.tokenRefreshSucceeded is False
    assert result.retryAttempted is False
    assert "expired-access-token" not in serialized


def test_realsync_retry_failure_returns_compact_safe_error(monkeypatch):
    clear_test_manager_env(monkeypatch)
    old_token = "expired-access-token"
    new_token = "fresh-access-token"
    refresh_token = "refresh-token"
    client_secret = "super-secret-client-secret"
    token_url = "https://staging.uipath.com/hackathon26_182/identity_/connect/token"
    configure_realsync_assets(
        monkeypatch,
        token=old_token,
        refresh_token=refresh_token,
        client_id="client-id",
        client_secret=client_secret,
        token_url=token_url,
    )
    get_count = 0

    class FakeResponse:
        headers = {"Content-Type": "application/json"}

        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self.payload = payload
            self.ok = 200 <= status_code < 300
            self.text = json.dumps(payload)

        def json(self):
            return self.payload

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        nonlocal get_count
        get_count += 1
        if get_count == 1:
            return FakeResponse(401, {"error": "invalid_token"})
        assert headers["Authorization"] == f"Bearer {new_token}"
        return FakeResponse(500, {"message": "Still unauthorized downstream"})

    def fake_post(url: str, headers: dict[str, str], data=None, timeout: int = 30):
        assert url == token_url
        return FakeResponse(200, {"access_token": new_token, "token_type": "Bearer"})

    monkeypatch.setattr("main.requests.get", fake_get)
    monkeypatch.setattr("main.requests.post", fake_post)

    result = call_agent(base_question(syncMode="RealSync"))
    serialized = result.model_dump_json()

    assert result.syncStatus == "Failed"
    assert result.syncStatus != "ReadyToSync"
    assert result.blockedReasons == [
        "Test Manager API call failed with status 500 at /api/v2/projects/prefix/QQTP: Still unauthorized downstream"
    ]
    assert result.tokenRefreshAttempted is True
    assert result.tokenRefreshSucceeded is True
    assert result.retryAttempted is True
    assert old_token not in serialized
    assert new_token not in serialized
    assert refresh_token not in serialized
    assert client_secret not in serialized


def test_build_url_joins_testmanager_base_and_api_endpoint():
    base_url = "https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_/"

    assert _join_url(base_url, "/api/v2/projects/prefix/QQTP") == (
        "https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_"
        "/api/v2/projects/prefix/QQTP"
    )


def test_realsync_bearer_prefix_token_is_normalized(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch, token=" Bearer super-secret-test-token\r\n")
    calls = install_successful_http_mock(monkeypatch)

    result = call_agent(base_question(syncMode="RealSync"))

    assert result.syncStatus == "Completed"
    assert result.authTokenPresent is True
    assert result.authHeaderPrepared is True
    assert result.tokenStartsWithBearerPrefix is True
    assert all(call["headers"]["Authorization"] == "Bearer super-secret-test-token" for call in calls)


def test_http_json_uses_requests_post_with_expected_headers(monkeypatch):
    captured_headers: dict[str, str] = {}
    captured_json: dict[str, Any] = {}

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"Content-Type": "application/json"}

        text = '{"ok":true}'

        def json(self):
            return {"ok": True}

    def fake_post(url, headers, json=None, timeout=30):
        captured_headers.update(headers)
        captured_json.update(json or {})
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setattr("main.requests.post", fake_post)

    result = _http_json(
        "POST",
        "https://example.testmanager/api/v2/project/testcases",
        "Bearer super-secret-test-token\n",
        {"name": "case"},
    )

    assert result == {"ok": True}
    assert captured_headers["Authorization"] == "Bearer super-secret-test-token"
    assert captured_headers["Accept"] == "application/json"
    assert captured_headers["Content-Type"] == "application/json"
    assert captured_json == {"name": "case"}


def test_project_lookup_helper_matches_curl_headers(monkeypatch):
    captured_headers: dict[str, str] = {}
    captured_url = ""

    class FakeResponse:
        ok = True
        status_code = 200
        headers = {"Content-Type": "application/json"}
        text = '{"id":"project-from-prefix"}'

        def json(self):
            return {"id": "project-from-prefix"}

    def fake_get(url, headers, timeout=30):
        nonlocal captured_url
        captured_url = url
        captured_headers.update(headers)
        assert timeout == 30
        return FakeResponse()

    monkeypatch.setattr("main.requests.get", fake_get)

    response = lookup_test_manager_project_by_prefix(
        base_url="https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_/",
        project_prefix="QQTP",
        token="Bearer super-secret-test-token",
    )

    assert response == {"id": "project-from-prefix"}
    assert captured_url == (
        "https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_"
        "/api/v2/projects/prefix/QQTP"
    )
    assert captured_headers["Authorization"] == "Bearer super-secret-test-token"
    assert captured_headers["Accept"] == "application/json"
    assert "Content-Type" not in captured_headers


def test_realsync_must_never_return_ready_to_sync(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch)
    calls = install_successful_http_mock(monkeypatch)

    result = call_agent(base_question(syncMode="realsync"))

    assert result.syncMode == "RealSync"
    assert result.syncMode != "DryRun"
    assert result.syncStatus != "ReadyToSync"
    assert calls


def test_realsync_empty_project_id_calls_project_lookup_by_prefix(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch, project_prefix="QQTP")
    calls = install_successful_http_mock(monkeypatch)

    result = call_agent(base_question(syncMode="RealSync", testManagerProjectId=""))

    assert result.syncStatus == "Completed"
    assert calls[0]["method"] == "GET"
    assert calls[0]["url"].endswith("/api/v2/projects/prefix/QQTP")
    assert calls[1]["url"].endswith("/api/v2/project-from-prefix/requirements")


def test_realsync_project_lookup_success_proceeds_to_create_requirement(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(
        monkeypatch,
        base_url="https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_/",
        project_prefix="QQTP",
    )
    calls = install_successful_http_mock(monkeypatch)

    result = call_agent(base_question(syncMode="RealSync", testManagerProjectId=""))

    assert result.syncStatus == "Completed"
    assert calls[0]["url"] == (
        "https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_"
        "/api/v2/projects/prefix/QQTP"
    )
    assert calls[1]["url"].endswith("/api/v2/project-from-prefix/requirements")
    assert result.baseUrlUsed == (
        "https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_"
    )
    assert result.firstEndpointPath == "/api/v2/projects/prefix/QQTP"


def test_realsync_api_failure_returns_failed_with_safe_reason(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch)

    def fail_http_json(method: str, url: str, token: str, body=None, diagnostics=None, auth_state=None):
        raise TmApiError(500, "Internal Server Error")

    monkeypatch.setattr("main._http_json", fail_http_json)

    result = call_agent(base_question(syncMode="RealSync"))
    serialized = result.model_dump_json()

    assert result.syncStatus == "Failed"
    assert result.syncMode == "RealSync"
    assert result.syncStatus != "ReadyToSync"
    assert result.realSyncAttempted is True
    assert result.authTokenPresent is True
    assert result.authHeaderPrepared is True
    assert result.blockedReasons == [
        "Test Manager API call failed with status 500: Internal Server Error"
    ]
    assert "super-secret-test-token" not in serialized
    assert "Bearer super-secret-test-token" not in serialized


def test_realsync_html_403_error_returns_short_safe_reason(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch)

    def fail_http_json(method: str, url: str, token: str, body=None, diagnostics=None, auth_state=None):
        if diagnostics is not None:
            diagnostics.response_status_code = 403
            diagnostics.response_content_type = "text/html"
        raise TmApiError(
            403,
            "<!DOCTYPE html><html><body>Very long forbidden page</body></html>",
            endpoint_path="/api/v2/project/testcases",
            content_type="text/html",
        )

    monkeypatch.setattr("main._http_json", fail_http_json)

    result = call_agent(base_question(syncMode="RealSync"))
    serialized = result.model_dump_json()

    assert result.syncStatus == "Failed"
    assert result.responseStatusCode == 403
    assert result.responseContentType == "text/html"
    assert result.blockedReasons == [
        "Test Manager API call failed with status 403 at /api/v2/project/testcases. "
        "Authentication/session was rejected by UiPath Platform."
    ]
    assert "<!DOCTYPE html>" not in serialized
    assert "Very long forbidden page" not in serialized
    assert "super-secret-test-token" not in serialized
    assert "Bearer super-secret-test-token" not in serialized


def test_realsync_json_error_returns_compact_safe_reason(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch)

    def fail_http_json(method: str, url: str, token: str, body=None, diagnostics=None, auth_state=None):
        raise TmApiError(
            400,
            json.dumps({"error": "invalid_request", "message": "Name is required"}),
            endpoint_path="/api/v2/project/requirements",
            content_type="application/json",
        )

    monkeypatch.setattr("main._http_json", fail_http_json)

    result = call_agent(base_question(syncMode="RealSync"))

    assert result.syncStatus == "Failed"
    assert result.blockedReasons == [
        "Test Manager API call failed with status 400 at /api/v2/project/requirements: Name is required"
    ]


def test_final_test_set_assignment_failure_returns_created_objects(monkeypatch):
    clear_test_manager_env(monkeypatch)
    configure_realsync_assets(monkeypatch)
    calls: list[dict[str, Any]] = []

    class FakeResponse:
        headers = {"Content-Type": "application/json"}

        def __init__(self, status_code: int, payload: dict[str, Any]) -> None:
            self.status_code = status_code
            self.payload = payload
            self.ok = 200 <= status_code < 300
            self.text = json.dumps(payload)

        def json(self):
            return self.payload

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        calls.append({"method": "GET", "url": url, "headers": headers, "body": None})
        return FakeResponse(200, {"id": "project-from-prefix"})

    def fake_post(url: str, headers: dict[str, str], json=None, timeout: int = 30):
        calls.append({"method": "POST", "url": url, "headers": headers, "body": json})
        if url.endswith("/project-from-prefix/requirements"):
            return FakeResponse(200, {"id": "created-requirement-id"})
        if url.endswith("/project-from-prefix/testcases"):
            return FakeResponse(200, {"id": "created-testcase-id"})
        if url.endswith("/project-from-prefix/requirements/created-requirement-id/assigntestcases"):
            return FakeResponse(200, {})
        if url.endswith("/project-from-prefix/testsets"):
            return FakeResponse(200, {"id": "created-testset-id"})
        if url.endswith("/project-from-prefix/testsets/created-testset-id/assigntestcases"):
            return FakeResponse(
                400,
                {
                    "message": "Validation failed",
                    "errors": {
                        "testCaseIds": [
                            "The testCaseIds property is not valid for this endpoint."
                        ]
                    },
                },
            )
        raise AssertionError(f"Unexpected API call: POST {url}")

    monkeypatch.setattr("main.requests.get", fake_get)
    monkeypatch.setattr("main.requests.post", fake_post)

    result = call_agent(base_question(syncMode="RealSync"))

    assert result.syncStatus == "Failed"
    assert result.syncStatus != "ReadyToSync"
    assert result.createdRequirement == "created-requirement-id"
    assert result.createdTestCases == ["created-testcase-id"]
    assert result.createdTestSet == "created-testset-id"
    assert result.createdTestCaseIds == ["created-testcase-id"]
    assert result.createdTestSetId == "created-testset-id"
    assert result.assignTestSetPayloadShape == "ids"
    assert result.failedEndpointPath == (
        "/api/v2/project-from-prefix/testsets/created-testset-id/assigntestcases"
    )
    assert result.responseStatusCode == 400
    assert "Validation failed" in result.blockedReasons[0]
    assert "testCaseIds" in result.blockedReasons[0]
    assert calls[9]["body"] == ["created-testcase-id"]
    assert calls[10]["body"] == {"ids": ["created-testcase-id"]}
    assert "TS-001" not in json.dumps(calls[9]["body"])
    assert "TS-001" not in json.dumps(calls[10]["body"])


def test_missing_requirement_id():
    result = call_agent(base_question(requirementId=""))

    assert result.syncStatus == "Failed"
    assert result.requirementId == ""
    assert "Invalid input: requirementId is required." in result.blockedReasons
    assert result.summary.requirementsPrepared == 0


def test_missing_test_scenarios():
    result = call_agent(base_question(testScenarios=[]))

    assert result.syncStatus == "Failed"
    assert result.testCasePayloads == []
    assert "Invalid input: testScenarios is required and cannot be empty." in result.blockedReasons


def test_duplicate_title_cleanup():
    result = call_agent(
        base_question(
            testScenarios=[
                {
                    "scenarioId": "TS-001",
                    "scenarioTitle": "Validate Validate End-to-End Patient Care Workflow happy path",
                    "priority": "High",
                    "testType": "Functional",
                    "steps": ["Create a patient"],
                    "expectedResult": "Patient is created.",
                }
            ]
        )
    )

    assert clean_duplicate_consecutive_words("Validate Validate End-to-End") == "Validate End-to-End"
    assert result.testCasePayloads[0]["name"] == (
        "TS-001 - Validate End-to-End Patient Care Workflow happy path"
    )


def test_high_risk_test_set_selection():
    result = call_agent(base_question(riskLevel="High"))

    assert result.testSetPayload["name"] == "High Risk Functional + Integration Suite"
    assert result.testSetMembership == [
        {
            "testSetName": "High Risk Functional + Integration Suite",
            "scenarioId": "TS-001",
        }
    ]
