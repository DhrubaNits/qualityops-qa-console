import asyncio
import json

import main


def run_agent(state: main.GraphState) -> main.GraphOutput:
    return asyncio.run(main.send_final_report_email(state))


def make_message(**overrides) -> main.MailMessage:
    values = {
        "to": "qa@example.com",
        "cc": "",
        "subject": "Final QA Report",
        "html_report": "<h1>Passed</h1>",
        "plain_text_report": "Passed",
        "execution_name": "Execution 42",
        "ado_bug_links": [],
        "test_manager_execution_link": "https://example.testmanager/executions/42",
    }
    values.update(overrides)
    return main.MailMessage(**values)


def test_validation_requires_to_subject_and_report():
    result = run_agent(main.GraphState(to="", subject="", htmlReport="", plainTextReport=""))

    assert result.status == "Failed"
    assert result.emailStatus == "Not Sent"
    assert "to is required." in result.blockedReasons
    assert "subject is required." in result.blockedReasons
    assert "htmlReport or plainTextReport is required." in result.blockedReasons


def test_validation_rejects_unknown_mode():
    result = run_agent(
        main.GraphState(
            mode="other",
            to="qa@example.com",
            subject="Final QA Report",
            plainTextReport="Report",
        )
    )

    assert result.status == "Failed"
    assert result.emailStatus == "Not Sent"
    assert result.blockedReasons == ["mode must be sendFinalReportEmail."]


def test_normalize_input_merges_question_json_with_question_priority():
    result = main.normalize_input(
        {
            "question": json.dumps(
                {
                    "mode": "sendFinalReportEmail",
                    "to": "qa@example.com",
                    "cc": "lead@example.com",
                    "subject": "Final QA Report",
                    "htmlReport": "<h1>Passed</h1>",
                    "plainTextReport": "Passed",
                }
            ),
            "variationId": "",
            "to": "",
            "subject": "",
        }
    )

    assert result["to"] == "qa@example.com"
    assert result["cc"] == "lead@example.com"
    assert result["subject"] == "Final QA Report"
    assert result["htmlReport"] == "<h1>Passed</h1>"


def test_wrapped_question_input_sends_email(monkeypatch):
    calls = []

    def sent(message):
        calls.append(message)
        return main.ProviderResult(True)

    monkeypatch.setattr(main, "_send_with_gmail_integration_service", sent)

    result = run_agent(
        main.GraphState(
            question=json.dumps(
                {
                    "mode": "sendFinalReportEmail",
                    "to": "qa@example.com",
                    "cc": "lead@example.com",
                    "subject": "Final QA Report",
                    "htmlReport": "<h1>Passed</h1>",
                    "plainTextReport": "Passed",
                }
            ),
            variationId="",
        )
    )

    assert result.status == "Completed"
    assert result.emailStatus == "Sent"
    assert result.to == "qa@example.com"
    assert result.cc == "lead@example.com"
    assert result.subject == "Final QA Report"
    assert calls[0].html_report == "<h1>Passed</h1>"


def test_plain_text_report_is_converted_to_html_before_send(monkeypatch):
    calls = []

    def sent(message):
        calls.append(message)
        return main.ProviderResult(True)

    monkeypatch.setattr(main, "_send_with_gmail_integration_service", sent)

    result = run_agent(
        main.GraphState(
            to="qa@example.com",
            subject="Final QA Report",
            plainTextReport="Line 1\nLine 2",
        )
    )

    assert result.status == "Completed"
    assert calls[0].html_report == "Line 1<br/>Line 2"


def test_gmail_activity_input_prefers_html_and_includes_cc():
    payload = main._gmail_activity_input(
        make_message(to="qa@example.com,owner@example.com", cc="lead@example.com")
    )

    assert payload["SaveAsDraft"] is False
    assert payload["To"] == "qa@example.com,owner@example.com"
    assert payload["CC"] == "lead@example.com"
    assert payload["Subject"] == "Final QA Report"
    assert payload["Body"] == "<h1>Passed</h1>"
    assert payload["Importance"] == "normal"


def test_gmail_activity_input_falls_back_to_plain_text_as_html_body():
    payload = main._gmail_activity_input(make_message(html_report="", plain_text_report="Passed"))

    assert payload["Body"] == "Passed"
    assert "CC" not in payload


def test_gmail_send_email_metadata_uses_curated_gmail_send_email_contract():
    metadata = main._gmail_send_email_metadata()

    assert metadata.object_path == "/SendEmail"
    assert metadata.method_name == "POST"
    assert metadata.content_type == "multipart/form-data"
    assert metadata.parameter_location_info.query_params == ["SaveAsDraft"]
    assert metadata.parameter_location_info.body_fields == [
        "BCC",
        "Body",
        "CC",
        "Importance",
        "ReplyTo",
        "Subject",
        "To",
    ]
    assert metadata.parameter_location_info.multipart_params == ["body", "file"]
    assert metadata.json_body_section == "body"


def test_success_response_when_gmail_send_succeeds(monkeypatch):
    calls = []

    def sent(message):
        calls.append(message)
        return main.ProviderResult(True)

    monkeypatch.setattr(main, "_send_with_gmail_integration_service", sent)

    result = run_agent(
        main.GraphState(
            to="qa@example.com",
            cc="lead@example.com",
            subject="Final QA Report",
            htmlReport="<h1>Passed</h1>",
            plainTextReport="Passed",
        )
    )

    assert result.status == "Completed"
    assert result.emailStatus == "Sent"
    assert result.to == "qa@example.com"
    assert result.cc == "lead@example.com"
    assert result.subject == "Final QA Report"
    assert result.nextAction == "Final QA sign-off report email sent successfully."
    assert calls[0].html_report == "<h1>Passed</h1>"


def test_failure_response_when_gmail_send_fails(monkeypatch):
    def failed(message):
        return main.ProviderResult(False, "Gmail Integration Service send failed.")

    monkeypatch.setattr(main, "_send_with_gmail_integration_service", failed)

    result = run_agent(
        main.GraphState(
            to="qa@example.com",
            subject="Final QA Report",
            plainTextReport="Passed",
        )
    )

    assert result.status == "Failed"
    assert result.emailStatus == "Not Sent"
    assert result.to == "qa@example.com"
    assert result.cc == ""
    assert result.subject == "Final QA Report"
    assert result.blockedReasons == ["Gmail Integration Service send failed."]


def test_safe_error_message_does_not_expose_secret_terms():
    result = main._safe_error_message(Exception("Bearer token abc123 was rejected"))

    assert result == "authentication or authorization failed; credentials were not exposed."
    assert "abc123" not in result
