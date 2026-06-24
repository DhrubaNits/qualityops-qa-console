import urllib.parse
import base64
import json
import os
import urllib.error
import urllib.request
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field
from uipath.platform import UiPath


class AgentInput(BaseModel):
    requirementId: str = Field(default="", description="Azure DevOps work item ID")
    decisionType: str = Field(default="", description="QA Lead decision")
    decisionComment: str = Field(default="", description="Comment to write back to Azure DevOps")
    submittedBy: str = Field(default="", description="Name of the user submitting the decision")
    environment: str = Field(default="", description="Target environment")
    adoOrg: str = Field(default="", description="Azure DevOps organization")
    adoProject: str = Field(default="", description="Azure DevOps project")
    adoPat: str = Field(default="", description="Azure DevOps PAT")


class AgentOutput(BaseModel):
    writeBackStatus: str = Field(default="")
    requirementId: str = Field(default="")
    decisionType: str = Field(default="")
    commentText: str = Field(default="")


class AgentState(TypedDict):
    question: str
    output: AgentOutput


def _asset_to_text(asset) -> str:
    if asset is None:
        return ""

    if isinstance(asset, str):
        return asset.strip()

    if isinstance(asset, dict):
        for key in ("value", "Value", "text", "Text"):
            if key in asset and asset[key] is not None:
                return str(asset[key]).strip()

    for attr in ("value", "Value", "text", "Text"):
        if hasattr(asset, attr):
            value = getattr(asset, attr)
            if value is not None:
                return str(value).strip()

    return str(asset).strip()


def _get_asset_value(asset_name: str) -> str:
    try:
        sdk = UiPath()
        asset = sdk.assets.retrieve(name=asset_name)
        return _asset_to_text(asset)
    except Exception:
        return ""


def _get_ado_config(agent_input: AgentInput) -> tuple[str, str, str]:
    org = agent_input.adoOrg.strip()
    project = agent_input.adoProject.strip()
    pat = agent_input.adoPat.strip()

    if org and project and pat:
        return org, project, pat

    org = os.getenv("AZURE_DEVOPS_ORG", "").strip()
    project = os.getenv("AZURE_DEVOPS_PROJECT", "").strip()
    pat = os.getenv("AZURE_DEVOPS_PAT", "").strip()

    if org and project and pat:
        return org, project, pat

    org = _get_asset_value("AzureDevOps_Org")
    project = _get_asset_value("AzureDevOps_Project")
    pat = _get_asset_value("AzureDevOps_PAT")

    return org, project, pat


def _build_ado_comment(agent_input: AgentInput) -> str:
    return f"""## QualityOps QA Lead Decision

**Decision:** {agent_input.decisionType or "N/A"}

**Requirement ID:** {agent_input.requirementId or "N/A"}

**Submitted By:** {agent_input.submittedBy or "N/A"}

**Environment:** {agent_input.environment or "N/A"}

**Comment:** {agent_input.decisionComment or "N/A"}

---
Updated by QualityOps QA Console.
"""


def _post_ado_comment(agent_input: AgentInput, comment_text: str) -> str:
    org, project, pat = _get_ado_config(agent_input)
    requirement_id = agent_input.requirementId

    if not org or not project or not pat:
        return (
            "Failed: Azure DevOps configuration is missing. "
            "Pass adoOrg, adoProject, adoPat in question JSON or create Orchestrator assets."
        )

    encoded_org = urllib.parse.quote(org, safe="")
    encoded_project = urllib.parse.quote(project, safe="")

    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")

    url = (
        f"https://dev.azure.com/{encoded_org}/{encoded_project}"
        f"/_apis/wit/workItems/{requirement_id}/comments?api-version=7.1-preview.4"
    )

    payload = json.dumps({"text": comment_text}).encode("utf-8")

    request = urllib.request.Request(
        url=url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Basic {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            status_code = response.getcode()
            response_body = response.read().decode("utf-8", errors="ignore")

            if status_code in (200, 201):
                return "Success: Azure DevOps comment added successfully."

            return (
                f"Failed: Azure DevOps comment write-back failed. "
                f"Status Code: {status_code}. Response: {response_body[:500]}"
            )

    except urllib.error.HTTPError as error:
        response_body = error.read().decode("utf-8", errors="ignore")
        return (
            f"Failed: Azure DevOps comment write-back failed. "
            f"Status Code: {error.code}. Response: {response_body[:500]}"
        )

    except Exception as error:
        return f"Failed: Azure DevOps comment write-back failed. Error: {str(error)}"

def writeback_node(state: AgentState) -> AgentState:
    question = state.get("question", "")

    try:
        payload = json.loads(question) if question else {}
    except Exception:
        state["output"] = AgentOutput(
            writeBackStatus="Failed: question input must be valid JSON.",
            requirementId="",
            decisionType="",
            commentText=question,
        )
        return state

    agent_input = AgentInput(
        requirementId=str(payload.get("requirementId", "")),
        decisionType=str(payload.get("decisionType", "")),
        decisionComment=str(payload.get("decisionComment", "")),
        submittedBy=str(payload.get("submittedBy", "")),
        environment=str(payload.get("environment", "")),
        adoOrg=str(payload.get("adoOrg", "")),
        adoProject=str(payload.get("adoProject", "")),
        adoPat=str(payload.get("adoPat", "")),
    )

    if not agent_input.requirementId:
        state["output"] = AgentOutput(
            writeBackStatus="Failed: requirementId is mandatory.",
            requirementId="",
            decisionType=agent_input.decisionType,
            commentText="",
        )
        return state

    comment_text = _build_ado_comment(agent_input)
    write_back_status = _post_ado_comment(agent_input, comment_text)

    state["output"] = AgentOutput(
        writeBackStatus=write_back_status,
        requirementId=agent_input.requirementId,
        decisionType=agent_input.decisionType,
        commentText=comment_text,
    )

    return state


builder = StateGraph(AgentState)
builder.add_node("writeback_node", writeback_node)
builder.add_edge(START, "writeback_node")
builder.add_edge("writeback_node", END)

graph = builder.compile()


def agent(
    question: Annotated[
        str,
        "JSON input containing requirementId, decisionType, decisionComment, submittedBy, environment, adoOrg, adoProject, adoPat",
    ] = "",
) -> AgentOutput:
    result = graph.invoke(
        {
            "question": question,
            "output": AgentOutput(),
        }
    )

    return result["output"]