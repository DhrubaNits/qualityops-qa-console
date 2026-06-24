import asyncio
import json

import main as agent
from main import Input, _asset_to_string, classify_failure


class FakeAsset:
    def __init__(self, **values):
        for key, value in values.items():
            setattr(self, key, value)


class FakeAssets:
    def __init__(self, values):
        self.values = values

    def retrieve(self, name=None, *args, **kwargs):
        if name is None:
            name = kwargs.pop("name", None)
        if name not in self.values:
            raise RuntimeError("missing asset")
        return self.values[name]


class FakeUiPath:
    def __init__(self, values):
        self.assets = FakeAssets(values)


class FakeResponse:
    def __init__(self, status_code=200, data=None, text=""):
        self.status_code = status_code
        self._data = data if data is not None else {}
        self.text = text
        self.content = json.dumps(self._data).encode("utf-8") if self._data is not None else b""
        self.ok = 200 <= status_code < 400

    def json(self):
        return self._data

    def raise_for_status(self):
        if not self.ok:
            import requests

            error = requests.HTTPError(f"{self.status_code} error")
            error.response = self
            raise error


class FakeSession:
    def __init__(self):
        self.headers = {}
        self.calls = []

    def get(self, url, timeout):
        self.calls.append({"method": "GET", "url": url, "timeout": timeout, "headers": dict(self.headers)})
        return FakeResponse(data={"items": []})

    def post(self, url, json=None, timeout=None):
        self.calls.append({"method": "POST", "url": url, "json": json, "timeout": timeout, "headers": dict(self.headers)})
        return FakeResponse(data={"id": "defect-id"})


class FakeTestManagerSession(FakeSession):
    def get(self, url, timeout):
        self.calls.append({"method": "GET", "url": url, "timeout": timeout, "headers": dict(self.headers)})
        if url.endswith("/testexecutions/execution-1/withStats"):
            return FakeResponse(
                data={
                    "id": "execution-1",
                    "name": "Nightly regression",
                    "status": "Finished",
                    "executionType": "Automated",
                    "runtimeType": "Unattended",
                    "passed": 1,
                    "failed": 3,
                    "none": 2,
                }
            )
        if "/testcaselogs/testexecution/execution-1/paged" in url:
            return FakeResponse(
                data={
                    "data": [
                        {
                            "id": "log-env",
                            "testCaseId": "tc-env",
                            "testCase": {"name": "Environment test", "packageEntryPointName": "Env.Entry"},
                            "result": "Failed",
                            "businessResult": "Failed",
                            "info": "{\"message\":\"Database connection timeout while calling dependent API\"}",
                            "robotName": "robot-a",
                            "hostMachineName": "host-a",
                            "automationTestCaseName": "EnvAutomation",
                            "variationId": None,
                        },
                        {
                            "id": "log-browser",
                            "testCaseId": "tc-browser",
                            "testCase": {"name": "Browser test", "packageEntryPointName": "Browser.Entry"},
                            "result": "Failed",
                            "businessResult": "Failed",
                            "info": "Cannot communicate with the browser",
                            "robotName": "robot-b",
                            "hostMachineName": "host-b",
                            "automationTestCaseName": "BrowserAutomation",
                            "variationId": "variation-b",
                        },
                        {
                            "id": "log-selector",
                            "testCaseId": "tc-selector",
                            "testCase": {"name": "Selector test", "packageEntryPointName": "Selector.Entry"},
                            "result": "Failed",
                            "businessResult": "Failed",
                            "info": "Strict selector failure. Multiple similar matches found.",
                            "robotName": "robot-c",
                            "hostMachineName": "host-c",
                            "automationTestCaseName": "SelectorAutomation",
                        },
                        {
                            "id": "log-passed",
                            "testCaseId": "tc-passed",
                            "testCase": {"name": "Passing test", "packageEntryPointName": "Pass.Entry"},
                            "result": "Passed",
                            "businessResult": "Passed",
                            "info": "Passed",
                        },
                    ]
                }
            )
        if "/robotlogs/paged" in url and "testcaseid=tc-env" in url:
            return FakeResponse(data={"data": [{"level": "Error", "message": "Database connection timeout"}]})
        if "/robotlogs/paged" in url and "testcaseid=tc-browser" in url:
            return FakeResponse(data={"data": [{"level": "Error", "message": "Cannot communicate with the browser"}]})
        if "/robotlogs/paged" in url and "testcaseid=tc-selector" in url:
            return FakeResponse(data={"data": [{"level": "Warn", "message": "Multiple similar matches"}]})
        if url.endswith("/testcaselogartifacts/log-env/assertions"):
            return FakeResponse(data={"data": []})
        if url.endswith("/testcaselogartifacts/log-browser/assertions"):
            return FakeResponse(data={"data": []})
        if url.endswith("/testcaselogartifacts/log-selector/assertions"):
            return FakeResponse(data={"data": [{"status": "Failed", "message": "Strict selector failure"}]})
        return FakeResponse(status_code=404, data={"message": "not found"})


def configure_assets(monkeypatch, values):
    monkeypatch.setattr(agent, "_create_uipath_client", lambda: FakeUiPath(values))


def configure_required_assets(monkeypatch, token="super-secret-test-token"):
    configure_assets(
        monkeypatch,
        {
            "TEST_MANAGER_BEARER_TOKEN": FakeAsset(value={"secretValue": token}),
            "TEST_MANAGER_REFRESH_TOKEN": FakeAsset(secret_value="refresh-token"),
            "TEST_MANAGER_CLIENT_ID": FakeAsset(value="client-id"),
            "TEST_MANAGER_CLIENT_SECRET": FakeAsset(secret_value="client-secret"),
        },
    )


def configure_azure_devops_assets(monkeypatch, pat="ado-secret-pat", project="Quality Ops Project"):
    configure_assets(
        monkeypatch,
        {
            "AzureDevOps_Org": FakeAsset(value="qualityops"),
            "AzureDevOps_Project": FakeAsset(value=project),
            "AzureDevOps_PAT": FakeAsset(value={"secretValue": pat}),
        },
    )


def create_defect_input(**overrides):
    values = {
        "mode": "createDefect",
        "projectId": "3dae45a4-6fc3-0000-60f6-0b49c244dbb8",
        "adoParentId": "12345",
        "testExecutionId": "execution-1",
        "testCaseId": "case-1",
        "testCaseName": "Checkout calculates tax",
        "runtimeType": "Unattended",
        "robotName": "robot-a",
        "hostMachineName": "host-a",
        "automationTestCaseName": "CheckoutAutomation",
        "classification": "Product Defect",
        "evidence": "Expected total 10.00 but Actual total 11.00\nRobot log: checkout total mismatch",
        "recommendedAction": "Assign to checkout team.",
        "linkToTestCaseLog": "https://example.test/test-manager-log",
    }
    values.update(overrides)
    return Input(**values)


def test_product_defect_classification():
    result = classify_failure("Verification failed. Expected saved status after update operation but Actual did not match.")

    assert result["classification"] == "Product Defect"
    assert "Verification failed" in result["matchedTerms"]


def test_automation_issue_classification():
    result = classify_failure("Strict selector failure. Multiple similar matches for UI element.")

    assert result["classification"] == "Automation Issue"


def test_environment_issue_classification():
    result = classify_failure("HTTP 503 Service Unavailable: dependent API service did not respond.")

    assert result["classification"] == "Environment Issue"


def test_data_issue_classification():
    result = classify_failure("The test data setup has missing data for this account.")

    assert result["classification"] == "Data Issue"


def test_needs_review_default_classification():
    result = classify_failure("Failure requires manual inspection.")

    assert result["classification"] == "Needs Review"


def test_direct_input_with_mode_and_project_id_works(monkeypatch):
    monkeypatch.setattr(agent, "list_executions", lambda project_id: {"projectId": project_id, "items": []})

    output = asyncio.run(
        agent.main(
            Input(
                mode="listExecutions",
                projectId="3dae45a4-6fc3-0000-60f6-0b49c244dbb8",
            )
        )
    )

    assert output.status == "success"
    assert output.mode == "listExecutions"
    assert output.projectId == "3dae45a4-6fc3-0000-60f6-0b49c244dbb8"
    assert output.result["items"] == []


def test_question_json_string_input_works(monkeypatch):
    monkeypatch.setattr(agent, "list_executions", lambda project_id: {"projectId": project_id, "items": []})

    output = asyncio.run(
        agent.main(
            Input(
                question=json.dumps(
                    {
                        "mode": "listExecutions",
                        "projectId": "3dae45a4-6fc3-0000-60f6-0b49c244dbb8",
                    }
                ),
                variationId="",
            )
        )
    )

    assert output.status == "success"
    assert output.mode == "listExecutions"
    assert output.projectId == "3dae45a4-6fc3-0000-60f6-0b49c244dbb8"


def test_direct_fields_override_question_json(monkeypatch):
    monkeypatch.setattr(agent, "list_executions", lambda project_id: {"projectId": project_id})

    output = asyncio.run(
        agent.main(
            Input(
                question=json.dumps(
                    {
                        "mode": "analyzeExecution",
                        "projectId": "question-project",
                        "testExecutionId": "question-execution",
                    }
                ),
                mode="listExecutions",
                projectId="direct-project",
            )
        )
    )

    assert output.status == "success"
    assert output.mode == "listExecutions"
    assert output.projectId == "direct-project"
    assert output.result["projectId"] == "direct-project"


def test_invalid_question_json_returns_clear_failed_response():
    output = asyncio.run(agent.main(Input(question="{not-json", variationId="")))

    assert output.status == "Failed"
    assert output.blockedReasons == ["question must contain valid JSON."]
    assert output.nextAction == "Provide question as a valid JSON string or pass mode and projectId directly."


def test_missing_mode_project_id_returns_clear_failed_response():
    output = asyncio.run(agent.main(Input(variationId="")))

    assert output.status == "Failed"
    assert output.blockedReasons == ["mode and projectId are required."]
    assert output.nextAction == "Provide mode and projectId."


def test_no_token_or_secret_leakage(monkeypatch):
    def fail(_project_id):
        raise RuntimeError(
            "Authorization: Bearer abc.def.ghi access_token=plain refresh_token=refresh client_secret=secret"
        )

    monkeypatch.setattr(agent, "list_executions", fail)

    output = asyncio.run(agent.main(Input(mode="listExecutions", projectId="project")))
    serialized = output.model_dump_json()

    assert output.status == "error"
    assert "abc.def.ghi" not in serialized
    assert "refresh" not in serialized
    assert "secret" not in serialized
    assert "***REDACTED***" in serialized


def test_secret_asset_nested_value_is_read():
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


def test_bearer_token_asset_read_uses_secret_value_and_returns_safe_diagnostics(monkeypatch):
    token = "super-secret-test-token"
    configure_required_assets(monkeypatch, token)
    monkeypatch.setattr(agent, "_base_url", lambda: "https://example.test/")
    monkeypatch.setattr(agent.TestManagerClient, "_get", lambda self, path: {"items": []})

    output = asyncio.run(agent.main(Input(mode="listExecutions", projectId="project")))
    serialized = output.model_dump_json()
    diagnostics = output.result["diagnostics"]

    assert output.status == "success"
    assert diagnostics["bearerTokenPresent"] is True
    assert diagnostics["bearerTokenSource"] == "asset"
    assert diagnostics["tokenRefreshAttempted"] is False
    assert diagnostics["tokenRefreshSucceeded"] is False
    assert diagnostics["tokenLength"] == len(token)
    assert diagnostics["tokenFingerprint"] == "402c827b"
    assert token not in serialized
    assert "refresh-token" not in serialized
    assert "client-secret" not in serialized


def test_missing_bearer_token_asset_returns_required_failed_response(monkeypatch):
    configure_assets(
        monkeypatch,
        {
            "TEST_MANAGER_REFRESH_TOKEN": FakeAsset(secret_value="refresh-token"),
            "TEST_MANAGER_CLIENT_ID": FakeAsset(value="client-id"),
            "TEST_MANAGER_CLIENT_SECRET": FakeAsset(secret_value="client-secret"),
        },
    )
    monkeypatch.setattr(agent, "_base_url", lambda: "https://example.test/")

    output = asyncio.run(agent.main(Input(mode="listExecutions", projectId="project")))

    assert output.status == "Failed"
    assert output.blockedReasons == ["TEST_MANAGER_BEARER_TOKEN asset could not be read from Orchestrator."]
    assert output.nextAction == "Verify asset access in the QualityOpsAgent folder."
    assert output.result == {}


def test_list_executions_builds_expected_staging_test_manager_v2_url(monkeypatch):
    project_id = "3dae45a4-6fc3-0000-60f6-0b49c244dbb8"
    fake_session = FakeSession()
    configure_required_assets(monkeypatch)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    output = asyncio.run(agent.main(Input(mode="listExecutions", projectId=project_id)))

    expected_url = (
        "https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_"
        f"/api/v2/{project_id}/testexecutions"
    )
    assert output.status == "success"
    assert fake_session.calls[0]["url"] == expected_url
    assert output.result["diagnostics"]["baseUrlUsed"] == (
        "https://staging.uipath.com/hackathon26_182/DefaultTenant/testmanager_"
    )
    assert output.result["diagnostics"]["requestUrlUsed"] == expected_url


def test_test_manager_url_does_not_contain_org_or_tenant_guid_path(monkeypatch):
    project_id = "3dae45a4-6fc3-0000-60f6-0b49c244dbb8"
    fake_session = FakeSession()
    configure_required_assets(monkeypatch)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    asyncio.run(agent.main(Input(mode="listExecutions", projectId=project_id)))

    request_url = fake_session.calls[0]["url"]
    assert "e8f45f66-ee1a-44b1-a7a0-fa2fd5d6938f" not in request_url
    assert "03d2d617-56fa-4b37-bd59-4ef6935b6f58" not in request_url
    assert "/hackathon26_182/DefaultTenant/testmanager_/api/v2/" in request_url


def test_no_token_secret_or_authorization_leakage_from_url_diagnostics(monkeypatch):
    token = "super-secret-test-token"
    fake_session = FakeSession()
    configure_required_assets(monkeypatch, token)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    output = asyncio.run(agent.main(Input(mode="listExecutions", projectId="project")))
    serialized = output.model_dump_json()

    assert token not in serialized
    assert "refresh-token" not in serialized
    assert "client-secret" not in serialized
    assert "Authorization" not in serialized
    assert "Bearer" not in serialized


def test_analyze_execution_fetches_summary_and_test_case_logs(monkeypatch):
    fake_session = FakeTestManagerSession()
    configure_required_assets(monkeypatch)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    output = asyncio.run(agent.main(Input(mode="analyzeExecution", projectId="project", testExecutionId="execution-1")))

    urls = [call["url"] for call in fake_session.calls]
    assert output.status == "success"
    assert output.result["status"] == "Completed"
    assert any(url.endswith("/api/v2/project/testexecutions/execution-1/withStats") for url in urls)
    assert any("/api/v2/project/testcaselogs/testexecution/execution-1/paged" in url for url in urls)
    assert output.result["diagnostics"]["executionSummaryResponseStatusCode"] == 200
    assert output.result["diagnostics"]["testCaseLogsResponseStatusCode"] == 200


def test_analyze_execution_parses_failed_rows_from_data_and_excludes_passed(monkeypatch):
    fake_session = FakeTestManagerSession()
    configure_required_assets(monkeypatch)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    output = asyncio.run(agent.main(Input(mode="analyzeExecution", projectId="project", testExecutionId="execution-1")))
    triage_results = output.result["triageResults"]

    assert [item["testCaseId"] for item in triage_results] == ["tc-env", "tc-browser", "tc-selector"]
    assert "tc-passed" not in [item["testCaseId"] for item in triage_results]
    assert output.result["diagnostics"]["totalResultRows"] == 4
    assert output.result["diagnostics"]["failedResultRows"] == 3
    assert output.result["diagnostics"]["robotLogsFetchedCount"] == 3
    assert output.result["diagnostics"]["assertionsFetchedCount"] == 3


def test_analyze_execution_parses_info_json_and_classifies_environment_issue(monkeypatch):
    fake_session = FakeTestManagerSession()
    configure_required_assets(monkeypatch)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    output = asyncio.run(agent.main(Input(mode="analyzeExecution", projectId="project", testExecutionId="execution-1")))
    env_result = output.result["triageResults"][0]

    assert env_result["classification"] == "Environment Issue"
    assert "database connection timeout" in env_result["matchedTerms"]
    assert "Database connection timeout while calling dependent API" in env_result["evidence"]
    assert env_result["variationId"] == ""


def test_analyze_execution_classifies_browser_and_selector_automation_issues(monkeypatch):
    fake_session = FakeTestManagerSession()
    configure_required_assets(monkeypatch)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    output = asyncio.run(agent.main(Input(mode="analyzeExecution", projectId="project", testExecutionId="execution-1")))
    results_by_id = {item["testCaseId"]: item for item in output.result["triageResults"]}

    assert results_by_id["tc-browser"]["classification"] == "Automation Issue"
    assert "Cannot communicate with the browser" in results_by_id["tc-browser"]["matchedTerms"]
    assert results_by_id["tc-selector"]["classification"] == "Automation Issue"
    assert "Strict selector failure" in results_by_id["tc-selector"]["matchedTerms"]
    assert "Multiple similar matches" in results_by_id["tc-selector"]["matchedTerms"]


def test_analyze_execution_summary_counts_are_correct(monkeypatch):
    fake_session = FakeTestManagerSession()
    configure_required_assets(monkeypatch)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    output = asyncio.run(agent.main(Input(mode="analyzeExecution", projectId="project", testExecutionId="execution-1")))
    summary = output.result["executionSummary"]

    assert summary == {
        "testExecutionId": "execution-1",
        "executionName": "Nightly regression",
        "testManagerStatus": "Finished",
        "executionType": "Automated",
        "runtimeType": "Unattended",
        "totalTests": 6,
        "passed": 1,
        "failed": 3,
        "skipped": 2,
    }


def test_analyze_execution_does_not_leak_tokens_secrets_or_authorization(monkeypatch):
    token = "super-secret-test-token"
    fake_session = FakeTestManagerSession()
    configure_required_assets(monkeypatch, token)
    monkeypatch.setattr(agent.requests, "Session", lambda: fake_session)

    output = asyncio.run(agent.main(Input(mode="analyzeExecution", projectId="project", testExecutionId="execution-1")))
    serialized = output.model_dump_json()

    assert token not in serialized
    assert "refresh-token" not in serialized
    assert "client-secret" not in serialized
    assert "Authorization" not in serialized
    assert "Bearer" not in serialized


def test_create_defect_reads_existing_azure_devops_assets(monkeypatch):
    calls = []
    configure_azure_devops_assets(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(data={"id": 9876})

    monkeypatch.setattr(agent.requests, "post", fake_post)

    output = asyncio.run(agent.main(create_defect_input()))

    assert output.status == "success"
    assert output.result["status"] == "Completed"
    assert output.result["defectSystem"] == "Azure DevOps"
    assert output.result["adoBugId"] == "9876"
    assert output.result["adoParentId"] == "12345"
    assert output.result["evidenceAdded"] is True
    assert output.result["testCaseName"] == "Checkout calculates tax"
    assert output.result["ui"] == {
        "message": "Azure DevOps Bug created successfully",
        "bugId": "9876",
        "parentId": "12345",
        "classification": "Product Defect",
        "testCaseName": "Checkout calculates tax",
        "actions": [
            {"label": "Open ADO Bug", "url": "https://dev.azure.com/qualityops/Quality%20Ops%20Project/_workitems/edit/9876"},
            {"label": "Open Test Manager Evidence", "url": "https://example.test/test-manager-log"},
        ],
    }
    assert len(calls) == 1


def test_create_defect_creates_bug_payload_and_links_parent(monkeypatch):
    calls = []
    configure_azure_devops_assets(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(data={"id": 9876})

    monkeypatch.setattr(agent.requests, "post", fake_post)

    output = asyncio.run(agent.main(create_defect_input()))
    payload = calls[0]["json"]

    assert output.result["defectCreationStatus"] == "Created"
    assert calls[0]["headers"]["Content-Type"] == "application/json-patch+json"
    assert payload[0] == {
        "op": "add",
        "path": "/fields/System.Title",
        "value": "[QualityOps] Checkout calculates tax - Product Defect",
    }
    assert payload[1]["path"] == "/fields/System.Description"
    description = payload[1]["value"]
    assert "<h2>QualityOps Automated Test Failure</h2>" in description
    assert "<p><b>Classification:</b> Product Defect</p>" in description
    assert "<p><b>Recommended Action:</b><br/>Assign to checkout team.</p>" in description
    assert "<p><b>Test Case:</b><br/>Checkout calculates tax</p>" in description
    assert "<p><b>Test Manager Evidence:</b><br/>" in description
    assert "<h3>Failure Evidence</h3>" in description
    assert "<pre>Expected total 10.00 but Actual total 11.00\nRobot log: checkout total mismatch</pre>" in description
    assert "<h3>Execution Details</h3>" in description
    assert "<li><b>Test Execution ID:</b> execution-1</li>" in description
    assert "<li><b>Test Case ID:</b> case-1</li>" in description
    assert "<li><b>Classification:</b> Product Defect</li>" in description
    assert "<li><b>Generated By:</b> QualityOps Test Result Triage Agent</li>" in description
    assert '<a href="https://example.test/test-manager-log">Open Test Manager Evidence</a>' in description
    assert payload[2] == {
        "op": "add",
        "path": "/fields/System.Tags",
        "value": "QualityOps; Automated Triage; Product Defect; UiPath Test Manager",
    }
    assert payload[3]["path"] == "/fields/Microsoft.VSTS.TCM.ReproSteps"
    assert "Open the Test Manager Evidence link." in payload[3]["value"]
    assert "Review the failed automated test case." in payload[3]["value"]
    assert "Check the failure evidence and robot logs." in payload[3]["value"]
    assert "Validate the impacted application behavior or automation/environment issue." in payload[3]["value"]
    assert payload[4]["path"] == "/fields/Microsoft.VSTS.TCM.SystemInfo"
    assert payload[4]["value"] == (
        "Generated by: QualityOps Test Result Triage Agent<br/>"
        "Source: UiPath Test Manager<br/>"
        "Execution Type: Automated<br/>"
        "Classification: Product Defect<br/>"
        "Test Execution ID: execution-1<br/>"
        "Test Case ID: case-1<br/>"
        "Test Manager Evidence: https://example.test/test-manager-log"
    )
    assert payload[5] == {
        "op": "add",
        "path": "/fields/Microsoft.VSTS.Common.Priority",
        "value": 2,
    }
    assert payload[6] == {
        "op": "add",
        "path": "/fields/Microsoft.VSTS.Common.Severity",
        "value": "3 - Medium",
    }
    assert payload[7]["path"] == "/relations/-"
    assert payload[7]["value"]["rel"] == "System.LinkTypes.Hierarchy-Reverse"
    assert payload[7]["value"]["url"] == "https://dev.azure.com/qualityops/Quality%20Ops%20Project/_apis/wit/workItems/12345"
    assert payload[7]["value"]["attributes"]["comment"] == "Linked by QualityOps automated test result triage"


def test_create_defect_url_encodes_project_name(monkeypatch):
    calls = []
    configure_azure_devops_assets(monkeypatch, project="Quality Ops / Web")

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(data={"id": 9876})

    monkeypatch.setattr(agent.requests, "post", fake_post)

    output = asyncio.run(agent.main(create_defect_input()))

    assert calls[0]["url"] == (
        "https://dev.azure.com/qualityops/Quality%20Ops%20%2F%20Web"
        "/_apis/wit/workitems/$Bug?api-version=7.1-preview.3"
    )
    assert output.result["adoBugUrl"] == "https://dev.azure.com/qualityops/Quality%20Ops%20%2F%20Web/_workitems/edit/9876"


def test_create_defect_retries_without_optional_template_fields_when_unavailable(monkeypatch):
    calls = []
    configure_azure_devops_assets(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        if len(calls) == 1:
            return FakeResponse(status_code=400, data={"message": "Field does not exist"})
        return FakeResponse(data={"id": 9876})

    monkeypatch.setattr(agent.requests, "post", fake_post)

    output = asyncio.run(agent.main(create_defect_input()))

    assert output.result["status"] == "Completed"
    assert output.result["evidenceAdded"] is True
    assert output.result["optionalTemplateFieldsAdded"] is False
    assert len(calls) == 2
    first_paths = [operation["path"] for operation in calls[0]["json"]]
    retry_paths = [operation["path"] for operation in calls[1]["json"]]
    assert "/fields/Microsoft.VSTS.TCM.ReproSteps" in first_paths
    assert "/fields/Microsoft.VSTS.TCM.SystemInfo" in first_paths
    assert "/fields/Microsoft.VSTS.TCM.ReproSteps" not in retry_paths
    assert "/fields/Microsoft.VSTS.TCM.SystemInfo" not in retry_paths
    assert "/fields/System.Description" in retry_paths
    assert "/relations/-" in retry_paths


def test_create_defect_missing_ado_parent_id_returns_clear_validation(monkeypatch):
    configure_azure_devops_assets(monkeypatch)

    output = asyncio.run(agent.main(create_defect_input(adoParentId="")))

    assert output.status == "success"
    assert output.result["status"] == "Blocked"
    assert output.result["defectCreationStatus"] == "Blocked"
    assert output.result["blockedReason"] == "adoParentId is required to link the Azure DevOps Bug to a parent work item."
    assert output.result["nextAction"] == "Provide adoParentId with the PBI or User Story work item ID."


def test_create_defect_missing_azure_devops_pat_returns_clear_blocked_reason(monkeypatch):
    configure_assets(
        monkeypatch,
        {
            "AzureDevOps_Org": FakeAsset(value="qualityops"),
            "AzureDevOps_Project": FakeAsset(value="Quality Ops Project"),
        },
    )

    output = asyncio.run(agent.main(create_defect_input()))

    assert output.result["status"] == "Blocked"
    assert output.result["blockedReason"] == "AzureDevOps_PAT asset could not be read from Orchestrator."
    assert output.result["nextAction"] == "Verify the existing AzureDevOps_PAT asset is available to this agent."


def test_create_defect_pat_permission_error_returns_required_message(monkeypatch):
    configure_azure_devops_assets(monkeypatch)

    def fake_post(url, headers=None, json=None, timeout=None):
        return FakeResponse(status_code=403, data={"message": "forbidden"})

    monkeypatch.setattr(agent.requests, "post", fake_post)

    output = asyncio.run(agent.main(create_defect_input()))

    assert output.result["status"] == "Blocked"
    assert output.result["blockedReason"] == (
        "Azure DevOps bug creation failed due to PAT permission. PAT requires Work Items Read & Write."
    )


def test_create_defect_does_not_leak_pat_or_authorization(monkeypatch):
    pat = "ado-secret-pat"
    calls = []
    configure_azure_devops_assets(monkeypatch, pat=pat)

    def fake_post(url, headers=None, json=None, timeout=None):
        calls.append({"url": url, "headers": headers, "json": json, "timeout": timeout})
        return FakeResponse(data={"id": 9876})

    monkeypatch.setattr(agent.requests, "post", fake_post)

    output = asyncio.run(
        agent.main(
            create_defect_input(
                evidence="Failure details access_token=payload-token refresh_token=refresh-value",
                recommendedAction="Review client_secret=payload-secret",
                linkToTestCaseLog="https://example.test/log?access_token=link-token",
            )
        )
    )
    serialized = output.model_dump_json()
    payload_serialized = json.dumps(calls[0]["json"])

    assert pat not in serialized
    assert "Authorization" not in serialized
    assert "Basic " not in serialized
    assert "payload-token" not in payload_serialized
    assert "refresh-value" not in payload_serialized
    assert "payload-secret" not in payload_serialized
    assert "link-token" not in payload_serialized
