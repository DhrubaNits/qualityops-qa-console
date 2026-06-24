import unittest

from main import (
    _build_raw_search_payloads,
    _build_scenario,
    _parse_uipath_index_chunks,
    _remove_consecutive_duplicate_words,
    build_vector_rag_query,
    build_test_generation_rag_query,
)


class ScenarioTitleTests(unittest.TestCase):
    def test_removes_consecutive_duplicate_words_case_insensitively(self) -> None:
        self.assertEqual(
            _remove_consecutive_duplicate_words("Validate Validate End-to-End Patient Care Workflow happy path"),
            "Validate End-to-End Patient Care Workflow happy path",
        )
        self.assertEqual(
            _remove_consecutive_duplicate_words("Validate validate End-to-End Patient Care Workflow happy path"),
            "Validate End-to-End Patient Care Workflow happy path",
        )

    def test_scenario_title_is_deduplicated_before_return(self) -> None:
        scenario = _build_scenario(
            index=1,
            title="Validate Validate End-to-End Patient Care Workflow happy path",
            priority="High",
            test_type="Functional",
            preconditions=[],
            steps=[],
            expected_result="Workflow is validated.",
        )

        self.assertEqual(
            scenario["scenarioTitle"],
            "Validate End-to-End Patient Care Workflow happy path",
        )


class RagParsingTests(unittest.TestCase):
    def test_parses_nested_semantic_values_response(self) -> None:
        response = {
            "semanticResults": {
                "values": [
                    {
                        "content": "Expected results must mention validation messages.",
                        "source": "qualityops_test_case_standard.md",
                        "score": 0.91,
                    }
                ]
            }
        }

        chunks = _parse_uipath_index_chunks(response)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["text"], "Expected results must mention validation messages.")
        self.assertEqual(chunks[0]["source"], "qualityops_test_case_standard.md")
        self.assertEqual(chunks[0]["score"], 0.91)

    def test_parses_alternate_documents_response_shape(self) -> None:
        response = {
            "documents": [
                {
                    "pageContent": "Audit trail captures patient creation.",
                    "metadata": {"fileName": "healthcare_workflow_test_checklist.md"},
                    "rankScore": 0.82,
                }
            ]
        }

        chunks = _parse_uipath_index_chunks(response)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["source"], "healthcare_workflow_test_checklist.md")

    def test_parses_nested_document_response_shape(self) -> None:
        response = {
            "semanticResults": [
                {
                    "document": {
                        "text": "Eligibility timeout warning is displayed.",
                        "sourceName": "healthcare_workflow_test_checklist.md",
                    },
                    "similarity": 0.77,
                }
            ]
        }

        chunks = _parse_uipath_index_chunks(response)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]["text"], "Eligibility timeout warning is displayed.")
        self.assertEqual(chunks[0]["score"], 0.77)

    def test_short_query_uses_healthcare_fallback_query(self) -> None:
        query = build_test_generation_rag_query({"requirementTitle": "Patient"})

        self.assertIn("ISO 29119", query)
        self.assertIn("duplicate patient", query)

    def test_vector_rag_query_is_focused_and_capped(self) -> None:
        query = build_vector_rag_query(
            {
                "requirementTitle": "Validate patient registration workflow",
                "requirementDescription": "x " * 5000,
                "requirementAnalysis": {
                    "suggestedTestFocus": ["Duplicate patient", "Eligibility timeout"],
                    "testingScope": ["Healthcare", "Integration"],
                },
                "qaLeadReview": {"feedbackText": "Focus on audit trail and expected result specificity."},
            }
        )

        self.assertLessEqual(len(query), 800)
        self.assertIn("patient", query)
        self.assertIn("duplicate", query)

    def test_raw_payloads_include_supported_unified_search_shape(self) -> None:
        payloads = _build_raw_search_payloads("patient eligibility", 8)

        self.assertEqual(payloads[0]["searchMode"], "Semantic")
        self.assertEqual(payloads[0]["query"], "patient eligibility")
        self.assertEqual(payloads[0]["semanticSearchOptions"]["numberOfResults"], 8)
        self.assertEqual(payloads[0]["semanticSearchOptions"]["threshold"], 0.0)


if __name__ == "__main__":
    unittest.main()
