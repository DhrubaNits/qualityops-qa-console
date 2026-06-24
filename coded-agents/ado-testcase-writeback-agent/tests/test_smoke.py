import asyncio
import json
import os
import unittest
from unittest.mock import patch

import main


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return json.dumps(
            {
                "id": 101,
                "url": "https://dev.azure.com/org/project/_apis/wit/workItems/101",
            }
        ).encode("utf-8")


class SmokeTests(unittest.TestCase):
    def test_creates_test_case_payload(self):
        question = {
            "requirementId": "26",
            "submittedBy": "Dhruba",
            "environment": "SQA",
            "testScenarios": [
                {
                    "scenarioId": "TS-001",
                    "scenarioTitle": "Validate Validate patient registration happy path",
                    "priority": "High",
                    "testType": "Functional",
                    "preconditions": ["Requirement 26 is available for testing"],
                    "steps": ["Open <workflow>", "Enter valid data & save"],
                    "expectedResult": "Patient is created successfully & confirmation is shown",
                }
            ],
        }

        with patch(
            "main._read_asset_config",
            return_value={},
        ), patch.dict(
            os.environ,
            {
                "ADO_ORGANIZATION": "org",
                "ADO_PROJECT": "project",
                "ADO_PAT": "pat",
            },
        ), patch("main.urlopen", return_value=FakeResponse()) as urlopen_mock:
            output = asyncio.run(main.main(main.Input(question=json.dumps(question))))

        self.assertEqual(output.writeBackStatus, "Completed")
        self.assertEqual(output.requirementId, "26")
        self.assertEqual(output.createdTestCases[0].testCaseId, 101)

        request = urlopen_mock.call_args.args[0]
        self.assertEqual(request.headers["Content-type"], "application/json-patch+json")
        patch_document = json.loads(request.data.decode("utf-8"))
        title_field = next(item for item in patch_document if item["path"] == "/fields/System.Title")
        self.assertEqual(title_field["value"], "TS-001 - Validate patient registration happy path")

        steps_field = next(item for item in patch_document if item["path"] == "/fields/Microsoft.VSTS.TCM.Steps")
        self.assertIn('<steps id="0" last="2">', steps_field["value"])
        self.assertIn('<step id="1" type="ValidateStep">', steps_field["value"])
        self.assertIn("Open &lt;workflow&gt;", steps_field["value"])
        self.assertIn("Enter valid data &amp; save", steps_field["value"])
        self.assertIn("Patient is created successfully &amp; confirmation is shown", steps_field["value"])

        relation = next(item for item in patch_document if item["path"] == "/relations/-")
        self.assertEqual(relation["value"]["rel"], "System.LinkTypes.Hierarchy-Reverse")
        self.assertTrue(relation["value"]["url"].endswith("/_apis/wit/workItems/26"))

    def test_maps_object_step_expected_result_to_second_parameterized_string(self):
        scenario = main._normalize_scenario(
            {
                "scenarioId": "TS-001",
                "scenarioTitle": "Validate login",
                "steps": [
                    {
                        "action": "Login as clinic staff user.",
                        "expectedResult": "Clinic staff dashboard is displayed.",
                    }
                ],
            },
            1,
        )

        steps_xml = main._test_steps_xml(scenario)

        self.assertIn(
            "<parameterizedString isformatted=\"true\">Login as clinic staff user.</parameterizedString>"
            "<parameterizedString isformatted=\"true\">Clinic staff dashboard is displayed.</parameterizedString>",
            steps_xml,
        )
        self.assertNotIn("Login as clinic staff user. Expected:", steps_xml)
        self.assertNotIn(
            "The system behavior matches the expected outcome described by the generated QualityOps scenario.",
            steps_xml,
        )

    def test_splits_legacy_expected_marker_step(self):
        scenario = main._normalize_scenario(
            {
                "scenarioId": "TS-001",
                "scenarioTitle": "Validate login",
                "steps": [
                    "Login as clinic staff user. Expected: Clinic staff dashboard is displayed.",
                ],
            },
            1,
        )

        steps_xml = main._test_steps_xml(scenario)

        self.assertIn(
            "<parameterizedString isformatted=\"true\">Login as clinic staff user.</parameterizedString>"
            "<parameterizedString isformatted=\"true\">Clinic staff dashboard is displayed.</parameterizedString>",
            steps_xml,
        )
        self.assertNotIn("Login as clinic staff user. Expected:", steps_xml)

    def test_uses_orchestrator_assets_before_environment(self):
        question = {
            "requirementId": "26",
            "submittedBy": "Dhruba",
            "environment": "SQA",
            "testScenarios": [
                {
                    "scenarioId": "TS-001",
                    "scenarioTitle": "Validate patient registration happy path",
                    "priority": "High",
                    "testType": "Functional",
                    "preconditions": ["Requirement 26 is available for testing"],
                    "steps": ["Open workflow", "Enter valid data", "Save"],
                    "expectedResult": "Patient is created successfully",
                }
            ],
        }

        with patch(
            "main._read_asset_config",
            return_value={
                "ADO_ORGANIZATION": "asset-org",
                "ADO_PROJECT": "asset-project",
                "ADO_PAT": "asset-pat",
            },
        ), patch.dict(
            os.environ,
            {
                "ADO_ORGANIZATION": "env-org",
                "ADO_PROJECT": "env-project",
                "ADO_PAT": "env-pat",
            },
        ), patch("main.urlopen", return_value=FakeResponse()) as urlopen_mock:
            output = asyncio.run(main.main(main.Input(question=json.dumps(question))))

        self.assertEqual(output.writeBackStatus, "Completed")
        request = urlopen_mock.call_args.args[0]
        self.assertIn("asset-org/asset-project", request.full_url)

    def test_invalid_json_returns_failed_json_shape(self):
        output = asyncio.run(main.main(main.Input(question="{bad json")))

        self.assertEqual(output.writeBackStatus, "Failed")
        self.assertEqual(output.createdTestCases, [])
        self.assertEqual(output.failedScenarios[0].scenarioId, "")

    def test_missing_config_reports_assets_or_environment(self):
        question = {
            "requirementId": "26",
            "testScenarios": [
                {
                    "scenarioId": "TS-001",
                    "scenarioTitle": "Validate patient registration happy path",
                }
            ],
        }

        with patch("main._read_asset_config", return_value={}), patch.dict(os.environ, {}, clear=True):
            output = asyncio.run(main.main(main.Input(question=json.dumps(question))))

        self.assertEqual(output.writeBackStatus, "Failed")
        self.assertEqual(output.requirementId, "26")
        self.assertIn("UiPath Orchestrator Assets", output.failedScenarios[0].error)


if __name__ == "__main__":
    unittest.main()
