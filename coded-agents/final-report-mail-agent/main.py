from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field


SEND_MODE = "sendFinalReportEmail"
GMAIL_CONNECTION_KEY = "qualityopsagent-gmail"
GMAIL_CONNECTOR_KEY = "uipath-google-gmail"
GMAIL_SEND_EMAIL_OBJECT_PATH = "/SendEmail"


class GraphState(BaseModel):
    question: str = ""
    variationId: str = ""
    mode: str = SEND_MODE
    to: str = ""
    cc: str = ""
    subject: str = ""
    htmlReport: str = ""
    plainTextReport: str = ""
    executionName: str = ""
    adoBugLinks: list[str] = Field(default_factory=list)
    testManagerExecutionLink: str = ""


class GraphOutput(BaseModel):
    status: str
    emailStatus: str
    to: str = ""
    cc: str = ""
    subject: str = ""
    sentAt: str = ""
    nextAction: str = ""
    blockedReasons: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class MailMessage:
    to: str
    cc: str
    subject: str
    html_report: str
    plain_text_report: str
    execution_name: str
    ado_bug_links: list[str]
    test_manager_execution_link: str


@dataclass(frozen=True)
class ProviderResult:
    sent: bool
    reason: str = ""


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def normalize_input(raw_input):
    if isinstance(raw_input, BaseModel):
        payload = raw_input.model_dump()
    elif isinstance(raw_input, dict):
        payload = dict(raw_input)
    else:
        payload = {}

    question = payload.get("question")
    if isinstance(question, str) and question.strip():
        try:
            parsed_question = json.loads(question)
        except json.JSONDecodeError:
            parsed_question = None

        if isinstance(parsed_question, dict):
            payload = {**payload, **parsed_question}

    return payload


def _validate_input(state: GraphState) -> list[str]:
    blocked_reasons: list[str] = []

    if state.mode != SEND_MODE:
        blocked_reasons.append(f"mode must be {SEND_MODE}.")
    if not _has_text(state.to):
        blocked_reasons.append("to is required.")
    if not _has_text(state.subject):
        blocked_reasons.append("subject is required.")
    if not (_has_text(state.htmlReport) or _has_text(state.plainTextReport)):
        blocked_reasons.append("htmlReport or plainTextReport is required.")

    return blocked_reasons


def _message_from_state(state: GraphState) -> MailMessage:
    return MailMessage(
        to=state.to.strip(),
        cc=state.cc.strip(),
        subject=state.subject.strip(),
        html_report=state.htmlReport,
        plain_text_report=state.plainTextReport,
        execution_name=state.executionName,
        ado_bug_links=state.adoBugLinks,
        test_manager_execution_link=state.testManagerExecutionLink,
    )


def _split_recipients(value: str) -> list[str]:
    return [part.strip() for part in value.replace(",", ";").split(";") if part.strip()]


def _join_recipients(value: str) -> str:
    return ",".join(_split_recipients(value))


def _gmail_activity_input(message: MailMessage) -> dict[str, Any]:
    body = message.html_report if _has_text(message.html_report) else message.plain_text_report
    payload: dict[str, Any] = {
        "To": _join_recipients(message.to),
        "Subject": message.subject,
        "Body": body,
        "Importance": "normal",
        "SaveAsDraft": False,
    }

    cc = _join_recipients(message.cc)
    if cc:
        payload["CC"] = cc

    return payload


def _gmail_send_email_metadata():
    from uipath.platform.connections import (
        ActivityMetadata,
        ActivityParameterLocationInfo,
    )

    return ActivityMetadata(
        object_path=GMAIL_SEND_EMAIL_OBJECT_PATH,
        method_name="POST",
        content_type="multipart/form-data",
        parameter_location_info=ActivityParameterLocationInfo(
            query_params=["SaveAsDraft"],
            body_fields=[
                "BCC",
                "Body",
                "CC",
                "Importance",
                "ReplyTo",
                "Subject",
                "To",
            ],
            multipart_params=["body", "file"],
        ),
        json_body_section="body",
    )


def _send_with_gmail_integration_service(message: MailMessage) -> ProviderResult:
    try:
        from uipath.platform import UiPath

        sdk = UiPath()
        connection = sdk.connections.retrieve(GMAIL_CONNECTION_KEY)
        sdk.connections.invoke_activity(
            connection_id=connection.id,
            activity_metadata=_gmail_send_email_metadata(),
            activity_input=_gmail_activity_input(message),
        )
        return ProviderResult(True)
    except Exception as exc:
        return ProviderResult(
            False,
            f"Gmail Integration Service send failed: {_safe_error_message(exc)}",
        )


def _safe_error_message(exc: Exception) -> str:
    text = str(exc).strip() or exc.__class__.__name__
    sensitive_terms = (
        "authorization",
        "bearer",
        "token",
        "refresh",
        "client_secret",
        "secret",
        "password",
        "pat",
    )
    if any(term in text.lower() for term in sensitive_terms):
        return "authentication or authorization failed; credentials were not exposed."
    return text[:500]


async def send_final_report_email(state: GraphState) -> GraphOutput:
    payload = normalize_input(state)
    to = payload.get("to", "")
    cc = payload.get("cc", "")
    subject = payload.get("subject", "")
    htmlReport = payload.get("htmlReport", "")
    plainTextReport = payload.get("plainTextReport", "")

    if not _has_text(htmlReport) and _has_text(plainTextReport):
        htmlReport = plainTextReport.replace("\n", "<br/>")
        payload["htmlReport"] = htmlReport

    print(
        "Mail agent normalized input:",
        {
            "has_to": bool(to),
            "has_subject": bool(subject),
            "htmlReportLength": len(htmlReport or ""),
            "plainTextReportLength": len(plainTextReport or ""),
        },
    )

    normalized_state = GraphState(**payload)
    blocked_reasons = _validate_input(normalized_state)
    if blocked_reasons:
        return GraphOutput(
            status="Failed",
            emailStatus="Not Sent",
            to=normalized_state.to.strip(),
            cc=normalized_state.cc.strip(),
            subject=normalized_state.subject.strip(),
            blockedReasons=blocked_reasons,
        )

    message = _message_from_state(normalized_state)
    result = _send_with_gmail_integration_service(message)
    if not result.sent:
        return GraphOutput(
            status="Failed",
            emailStatus="Not Sent",
            to=message.to,
            cc=message.cc,
            subject=message.subject,
            blockedReasons=[result.reason or "No approved email provider is configured."],
        )

    return GraphOutput(
        status="Completed",
        emailStatus="Sent",
        to=message.to,
        cc=message.cc,
        subject=message.subject,
        sentAt=datetime.now(timezone.utc).isoformat(),
        nextAction="Final QA sign-off report email sent successfully.",
    )


builder = StateGraph(GraphState, output=GraphOutput)
builder.add_node("sendFinalReportEmail", send_final_report_email)
builder.add_edge(START, "sendFinalReportEmail")
builder.add_edge("sendFinalReportEmail", END)

graph = builder.compile()
