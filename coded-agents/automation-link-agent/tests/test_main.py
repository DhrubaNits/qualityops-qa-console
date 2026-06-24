import json
from asyncio import run
from typing import Any

from main import (
    DEFAULT_PACKAGE_IDENTIFIER,
    Input,
    SIMULATOR_PROFILE_ORDER,
    build_entry_point_lookup,
    main,
)


class FakeAsset:
    def __init__(self, **values: Any) -> None:
        for key, value in values.items():
            setattr(self, key, value)


class FakeAssets:
    def __init__(self, values: dict[str, FakeAsset]) -> None:
        self.values = values

    def retrieve(self, name: str | None = None, *args: Any, **kwargs: Any) -> FakeAsset:
        if name is None:
            name = kwargs.pop("name", None)
        if name not in self.values:
            raise RuntimeError("missing asset")
        return self.values[name]


class FakeUiPath:
    def __init__(self, values: dict[str, FakeAsset]) -> None:
        self.assets = FakeAssets(values)


class FakeResponse:
    headers = {"Content-Type": "application/json"}

    def __init__(self, status_code: int, payload: dict[str, Any] | list[Any]) -> None:
        self.status_code = status_code
        self.payload = payload
        self.ok = 200 <= status_code < 300
        self.text = json.dumps(payload)

    def json(self):
        return self.payload


def question(**overrides: Any) -> str:
    payload = {
        "projectId": "3dae45a4-6fc3-0000-60f6-0b49c244dbb8",
        "createdTestCaseIds": [f"tc-{index}" for index in range(1, 9)],
        "packageIdentifier": DEFAULT_PACKAGE_IDENTIFIER,
    }
    payload.update(overrides)
    return json.dumps(payload)


def call_agent(payload: str):
    return run(main(Input(question=payload)))


def configure_assets(monkeypatch, token: str = "super-secret-test-token", **overrides: str):
    values = {
        "TEST_MANAGER_BEARER_TOKEN": FakeAsset(secret_value=token),
        "TEST_MANAGER_BASE_URL": FakeAsset(value="https://example.testmanager"),
        "TEST_MANAGER_PROJECT_PREFIX": FakeAsset(value="QQTP"),
    }
    for key, value in overrides.items():
        values[key] = FakeAsset(secret_value=value if "SECRET" in key or "TOKEN" in key else None, value=value)
    monkeypatch.setattr("main._create_uipath_client", lambda: FakeUiPath(values))


def entry_point_items(package_identifier: str = DEFAULT_PACKAGE_IDENTIFIER, trailing_dot: bool = False):
    items = []
    for index, profile in enumerate(SIMULATOR_PROFILE_ORDER):
        name = profile
        if trailing_dot and profile.endswith("SIM_ENVIRONMENT_FAILURE_001"):
            name = f"{profile}."
        items.append(
            {
                "packageName": package_identifier,
                "packageEntryPointName": name,
                "packageEntryPointId": f"entry-{index}",
            }
        )
    items.append(
        {
            "packageName": "OtherPackage",
            "packageEntryPointName": SIMULATOR_PROFILE_ORDER[0],
            "packageEntryPointId": "other-entry",
        }
    )
    return items


def install_successful_http(monkeypatch, package_items=None):
    calls: list[dict[str, Any]] = []
    package_items = package_items if package_items is not None else entry_point_items()

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        calls.append({"method": "GET", "url": url, "headers": headers, "body": None})
        assert timeout == 30
        assert headers["Authorization"] == "Bearer super-secret-test-token"
        assert url.endswith(
            "/api/v2/3dae45a4-6fc3-0000-60f6-0b49c244dbb8/orchestrator/packageentrypoints"
            "?Top=100&Skip=0&Search=&DistinctByPackageEntryPointIdAndPackageName=true"
        )
        return FakeResponse(200, {"value": package_items})

    def fake_post(url: str, headers: dict[str, str], json=None, timeout: int = 30):
        calls.append({"method": "POST", "url": url, "headers": headers, "body": json})
        assert timeout == 30
        assert headers["Authorization"] == "Bearer super-secret-test-token"
        assert headers["Content-Type"] == "application/json"
        assert url.endswith("/updatepackageautomation")
        return FakeResponse(200, {})

    monkeypatch.setattr("main.requests.get", fake_get)
    monkeypatch.setattr("main.requests.post", fake_post)
    return calls


def test_package_entry_points_fetched_successfully(monkeypatch):
    configure_assets(monkeypatch)
    calls = install_successful_http(monkeypatch)

    result = call_agent(question(createdTestCaseIds=["tc-1"]))

    assert result.automationLinkStatus == "Completed"
    assert result.packageEntryPointFetchAttempted is True
    assert result.packageEntryPointFetchSucceeded is True
    assert calls[0]["method"] == "GET"


def test_links_first_8_created_test_cases_to_first_8_simulator_profiles(monkeypatch):
    configure_assets(monkeypatch)
    calls = install_successful_http(monkeypatch)

    result = call_agent(question())

    assert result.automationLinkStatus == "Completed"
    assert result.linkedCount == 8
    assert [mapping.simulatorProfile for mapping in result.linkedMappings] == SIMULATOR_PROFILE_ORDER[:8]
    assert [call["body"]["packageEntryPointUniqueId"] for call in calls[1:]] == [
        f"entry-{index}" for index in range(8)
    ]


def test_supports_trailing_dot_for_environment_failure_001(monkeypatch):
    configure_assets(monkeypatch)
    calls = install_successful_http(monkeypatch, entry_point_items(trailing_dot=True))

    result = call_agent(question(createdTestCaseIds=[f"tc-{index}" for index in range(1, 7)]))

    assert result.automationLinkStatus == "Completed"
    assert result.linkedMappings[5].simulatorProfile == r"Test Case UI\SIM_ENVIRONMENT_FAILURE_001"
    assert calls[6]["body"]["packageEntryPointName"] == r"Test Case UI\SIM_ENVIRONMENT_FAILURE_001."


def test_cycles_mapping_if_more_test_cases_than_profiles(monkeypatch):
    configure_assets(monkeypatch)
    calls = install_successful_http(monkeypatch)
    ids = [f"tc-{index}" for index in range(1, 13)]

    result = call_agent(question(createdTestCaseIds=ids))

    assert result.automationLinkStatus == "Completed"
    assert result.linkedCount == 12
    assert result.linkedMappings[10].simulatorProfile == SIMULATOR_PROFILE_ORDER[0]
    assert result.linkedMappings[11].simulatorProfile == SIMULATOR_PROFILE_ORDER[1]
    assert calls[10]["body"]["packageEntryPointUniqueId"] == "entry-9"
    assert calls[11]["body"]["packageEntryPointUniqueId"] == "entry-0"
    assert calls[12]["body"]["packageEntryPointUniqueId"] == "entry-1"


def test_returns_failed_when_created_test_case_ids_empty(monkeypatch):
    monkeypatch.setattr(
        "main._create_uipath_client",
        lambda: (_ for _ in ()).throw(AssertionError("validation failure should not read assets")),
    )

    result = call_agent(question(createdTestCaseIds=[]))

    assert result.automationLinkStatus == "Failed"
    assert result.linkedCount == 0
    assert result.failedCount == 0
    assert result.packageEntryPointFetchAttempted is False
    assert result.blockedReasons == [
        "Invalid input: createdTestCaseIds is required and cannot be empty."
    ]


def test_token_refresh_retry_works(monkeypatch):
    old_token = "expired-access-token"
    new_token = "fresh-access-token"
    refresh_token = "refresh-token"
    client_secret = "super-secret-client-secret"
    token_url = "https://example.identity/connect/token"
    configure_assets(
        monkeypatch,
        token=old_token,
        TEST_MANAGER_REFRESH_TOKEN=refresh_token,
        TEST_MANAGER_CLIENT_ID="client-id",
        TEST_MANAGER_CLIENT_SECRET=client_secret,
        TEST_MANAGER_TOKEN_URL=token_url,
    )
    calls: list[dict[str, Any]] = []

    def fake_get(url: str, headers: dict[str, str], timeout: int):
        calls.append({"method": "GET", "url": url, "headers": headers, "body": None})
        if len([call for call in calls if call["method"] == "GET"]) == 1:
            return FakeResponse(401, {"error": "invalid_token"})
        assert headers["Authorization"] == f"Bearer {new_token}"
        return FakeResponse(200, {"value": entry_point_items()})

    def fake_post(url: str, headers: dict[str, str], json=None, data=None, timeout: int = 30):
        calls.append({"method": "POST", "url": url, "headers": headers, "body": json, "data": data})
        if url == token_url:
            assert data == {
                "grant_type": "refresh_token",
                "client_id": "client-id",
                "client_secret": client_secret,
                "refresh_token": refresh_token,
            }
            return FakeResponse(200, {"access_token": new_token, "token_type": "Bearer"})
        assert headers["Authorization"] == f"Bearer {new_token}"
        return FakeResponse(200, {})

    monkeypatch.setattr("main.requests.get", fake_get)
    monkeypatch.setattr("main.requests.post", fake_post)

    result = call_agent(question(createdTestCaseIds=["tc-1"]))

    assert result.automationLinkStatus == "Completed"
    assert result.tokenRefreshAttempted is True
    assert result.tokenRefreshSucceeded is True
    assert [call["method"] for call in calls] == ["GET", "POST", "GET", "POST"]


def test_no_token_values_appear_in_output(monkeypatch):
    token = "super-secret-test-token"
    refresh_token = "refresh-token"
    client_secret = "super-secret-client-secret"
    configure_assets(
        monkeypatch,
        token=token,
        TEST_MANAGER_REFRESH_TOKEN=refresh_token,
        TEST_MANAGER_CLIENT_ID="client-id",
        TEST_MANAGER_CLIENT_SECRET=client_secret,
        TEST_MANAGER_TOKEN_URL="https://example.identity/connect/token",
    )
    install_successful_http(monkeypatch)

    result = call_agent(question(createdTestCaseIds=["tc-1"]))
    serialized = result.model_dump_json()

    assert token not in serialized
    assert refresh_token not in serialized
    assert client_secret not in serialized
    assert "Authorization" not in serialized


def test_build_entry_point_lookup_filters_package_name():
    lookup = build_entry_point_lookup(
        {"value": entry_point_items() + entry_point_items("AnotherPackage")},
        DEFAULT_PACKAGE_IDENTIFIER,
    )

    assert lookup["test case ui\\sim_pass_001"]["packageEntryPointId"] == "entry-0"
    assert len(lookup) == len(SIMULATOR_PROFILE_ORDER)
