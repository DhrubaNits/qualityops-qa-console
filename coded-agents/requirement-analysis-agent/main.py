from uipath.platform import UiPath
import base64
from collections import Counter
import html
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any, Sequence

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.outputs import ChatResult
from pydantic import BaseModel, ConfigDict, Field

from uipath.agent.react import AGENT_SYSTEM_PROMPT_TEMPLATE
from uipath_langchain.agent.react import create_agent
from uipath_langchain.chat.chat_model_factory import get_chat_model

from utils import interpolate_legacy_message


class LazyUiPathChatModel(BaseChatModel):
    model_name: str = "gpt-5.4"
    temperature: float = 0.0
    max_tokens: int = 128000
    agenthub_config: str = "agentsruntime"
    _model: BaseChatModel | None = None

    @property
    def _llm_type(self) -> str:
        return "lazy-uipath-chat-model"

    def _get_model(self) -> BaseChatModel:
        if self._model is None:
            self._model = get_chat_model(
                model=self.model_name,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                agenthub_config=self.agenthub_config,
            )
        return self._model

    def bind_tools(self, tools: Sequence[Any], **kwargs: Any) -> Any:
        return self._get_model().bind_tools(tools, **kwargs)

    def _generate(self, messages: list, stop: list[str] | None = None, **kwargs: Any) -> ChatResult:
        return self._get_model()._generate(messages, stop=stop, **kwargs)

    async def _agenerate(
        self,
        messages: list,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> ChatResult:
        return await self._get_model()._agenerate(messages, stop=stop, **kwargs)


# -----------------------------
# Input / Output Models
# -----------------------------
class AgentInput(BaseModel):
    model_config = ConfigDict(extra="allow")

    requirementId: str = Field(
        ...,
        description="Azure DevOps work item ID to fetch and analyze.",
    )
    submittedBy: str | None = Field(
        None,
        description="Name or email of the person submitting the request.",
    )
    environment: str | None = Field(
        "SQA",
        description="Target environment selected from the QualityOps QA Console.",
    )


class AgentOutputQaAnalysisSummary(BaseModel):
    model_config = ConfigDict(extra="allow")

    impactedModules: list = Field(..., description="Impacted modules inferred from the requirement.")
    changeType: str = Field(..., description="New Feature, Enhancement, Bug Fix, Configuration Change, Performance Improvement, Security Update, or Unknown.")
    riskLevel: str = Field(..., description="High, Medium, or Low.")
    testingScope: list = Field(..., description="Recommended testing scope.")
    suggestedTestFocus: list = Field(..., description="Suggested test focus areas.")
    humanReviewRequired: bool = Field(..., description="Whether QA Lead or human review is required.")
    nextStep: str = Field(..., description="Recommended next step.")


class AgentOutputRequirementQualityAnalysis(BaseModel):
    model_config = ConfigDict(extra="allow")

    readinessStatus: str = Field(..., description="Ready, Needs Review, or Not Ready.")
    readinessScore: float = Field(..., description="Readiness score from 0 to 100.")
    identifiedGaps: list = Field(..., description="Requirement gaps identified.")
    ragChecklistUsed: list = Field(..., description="QA/RAG checklist used.")
    ragEvidenceUsed: list = Field(..., description="Retrieved RAG source evidence used, with sourceName and reasonUsed.")
    qaLeadActionRequired: bool = Field(..., description="Whether QA Lead action is required.")
    approvalRecommendation: str = Field(..., description="Approve, Needs QA Lead Review, or Reject and request clarification.")
    qaLeadDecisionStatus: str = Field(..., description="QA Lead decision status.")


class AgentOutput(BaseModel):
    model_config = ConfigDict(extra="allow")

    processingStatus: str = Field(..., description="Processing outcome.")
    requirementTitle: str = Field(..., description="Fetched Azure DevOps requirement title.")
    requirementDescription: str = Field(..., description="Fetched Azure DevOps requirement description.")
    acceptanceCriteria: str = Field(..., description="Fetched Azure DevOps acceptance criteria.")
    qaAnalysisSummary: AgentOutputQaAnalysisSummary = Field(..., description="QA analysis summary.")
    requirementQualityAnalysis: AgentOutputRequirementQualityAnalysis = Field(..., description="Requirement quality analysis.")
    qaLeadNotificationRequired: bool = Field(..., description="Whether QA Lead notification is required.")
    adoUpdateStatus: str = Field(..., description="ADO write-back status.")


# -----------------------------
# Azure DevOps Helper Functions
# -----------------------------
def _strip_html(value: str | None) -> str:
    if not value:
        return ""

    value = re.sub(r"<br\s*/?>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"</p\s*>", "\n", value, flags=re.IGNORECASE)
    value = re.sub(r"<[^>]+>", "", value)
    value = html.unescape(value)
    value = re.sub(r"\n\s*\n\s*\n+", "\n\n", value)

    return value.strip()


def _asset_to_text(asset) -> str:
    """
    Safely extract value from UiPath asset response.
    Works for common SDK response shapes and falls back to string conversion.
    """
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
    sdk = UiPath()
    asset = sdk.assets.retrieve(name=asset_name)
    return _asset_to_text(asset)


def _get_ado_config() -> tuple[str, str, str]:
    """
    Priority:
    1. Environment variables - useful for local/debug runs.
    2. Orchestrator Assets - required for published jobs started from the React app.
    """
    org = os.getenv("AZURE_DEVOPS_ORG", "").strip()
    project = os.getenv("AZURE_DEVOPS_PROJECT", "").strip()
    pat = os.getenv("AZURE_DEVOPS_PAT", "").strip()

    if org and project and pat:
        return org, project, pat

    try:
        org = org or _get_asset_value("AzureDevOps_Org")
        project = project or _get_asset_value("AzureDevOps_Project")
        pat = pat or _get_asset_value("AzureDevOps_PAT")
    except Exception as error:
        print(f"Failed to read Azure DevOps assets: {error}")

    return org, project, pat


def fetch_azure_devops_requirement(requirement_id: str) -> dict:
    org, project, pat = _get_ado_config()

    if not org or not project or not pat:
        return {
            "success": False,
            "status": "Azure DevOps configuration is missing. Please configure AZURE_DEVOPS_ORG, AZURE_DEVOPS_PROJECT, and AZURE_DEVOPS_PAT.",
            "httpStatus": None,
            "data": {},
        }

    encoded_project = urllib.parse.quote(project)
    encoded_requirement_id = urllib.parse.quote(str(requirement_id))

    url = (
        f"https://dev.azure.com/{org}/{encoded_project}"
        f"/_apis/wit/workitems/{encoded_requirement_id}"
        f"?api-version=7.1&$expand=all"
    )

    token = base64.b64encode(f":{pat}".encode("utf-8")).decode("utf-8")

    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Basic {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            response_body = response.read().decode("utf-8")
            payload = json.loads(response_body)

            fields = payload.get("fields", {})

            requirement = {
                "id": str(payload.get("id", requirement_id)),
                "title": fields.get("System.Title", ""),
                "description": _strip_html(fields.get("System.Description", "")),
                "acceptanceCriteria": _strip_html(
                    fields.get("Microsoft.VSTS.Common.AcceptanceCriteria", "")
                ),
                "state": fields.get("System.State", ""),
                "areaPath": fields.get("System.AreaPath", ""),
                "tags": fields.get("System.Tags", ""),
                "workItemType": fields.get("System.WorkItemType", ""),
                "url": payload.get("url", ""),
            }

            return {
                "success": True,
                "status": "Requirement fetched successfully from Azure DevOps.",
                "httpStatus": response.status,
                "data": requirement,
            }

    except urllib.error.HTTPError as error:
        error_body = ""
        try:
            error_body = error.read().decode("utf-8")
        except Exception:
            error_body = ""

        if error.code == 401 or error.code == 403:
            status = "Azure DevOps authentication failed. Please verify PAT permissions."
        elif error.code == 404:
            status = f"Requirement not found in Azure DevOps. Work item ID: {requirement_id}"
        else:
            status = f"Failed to fetch requirement from Azure DevOps. Status Code: {error.code}"

        return {
            "success": False,
            "status": status,
            "httpStatus": error.code,
            "data": {
                "errorBody": error_body[:1000],
            },
        }

    except Exception as error:
        return {
            "success": False,
            "status": f"Unexpected error while fetching Azure DevOps requirement: {str(error)}",
            "httpStatus": None,
            "data": {},
        }


# -----------------------------
# Local RAG Helper Functions
# -----------------------------
RAG_KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent / "rag_knowledge_base"

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "into",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "with",
}

HEALTHCARE_BOOST_TERMS = {
    "patient",
    "eligibility",
    "appointment",
    "scheduling",
    "registration",
    "duplicate",
    "audit",
    "validation",
    "provider",
    "workflow",
    "integration",
    "api",
    "timeout",
    "performance",
    "error",
    "negative",
    "edge",
    "regression",
}


def _source_name_from_file(file_path: Path) -> str:
    return file_path.stem.replace("_", " ").title()


def load_rag_documents() -> list[dict]:
    documents = []

    if not RAG_KNOWLEDGE_BASE_DIR.exists():
        return documents

    for file_path in sorted(RAG_KNOWLEDGE_BASE_DIR.glob("*.md")):
        try:
            content = file_path.read_text(encoding="utf-8").strip()
        except OSError:
            continue

        if not content:
            continue

        documents.append(
            {
                "sourceName": _source_name_from_file(file_path),
                "fileName": file_path.name,
                "content": content,
            }
        )

    return documents


def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 200,
    sourceName: str = "",
    fileName: str = "",
) -> list[dict]:
    normalized_text = re.sub(r"\s+", " ", text or "").strip()
    if not normalized_text:
        return []

    if overlap >= chunk_size:
        overlap = max(0, chunk_size // 5)

    chunks = []
    start = 0
    chunk_index = 1

    while start < len(normalized_text):
        end = min(start + chunk_size, len(normalized_text))
        chunk_content = normalized_text[start:end].strip()

        if chunk_content:
            chunks.append(
                {
                    "sourceName": sourceName,
                    "fileName": fileName,
                    "chunkIndex": chunk_index,
                    "content": chunk_content,
                }
            )

        if end >= len(normalized_text):
            break

        start = max(0, end - overlap)
        chunk_index += 1

    return chunks


def build_rag_query(requirement: dict) -> str:
    if not isinstance(requirement, dict):
        return ""

    query_parts = [
        requirement.get("title", ""),
        requirement.get("description", ""),
        requirement.get("acceptanceCriteria", ""),
        requirement.get("tags", ""),
        requirement.get("areaPath", ""),
    ]

    return "\n".join(str(part) for part in query_parts if part)


def _tokenize_for_rag(text: str) -> list[str]:
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{1,}", (text or "").lower())
    return [token for token in tokens if token not in STOP_WORDS and len(token) > 2]


def score_chunk(query: str, chunk: dict) -> int:
    query_terms = Counter(_tokenize_for_rag(query))
    chunk_terms = Counter(_tokenize_for_rag(chunk.get("content", "")))

    if not query_terms or not chunk_terms:
        return 0

    score = 0
    for term, query_count in query_terms.items():
        if term in chunk_terms:
            score += min(query_count, 3) * min(chunk_terms[term], 3)

    query_term_set = set(query_terms)
    chunk_term_set = set(chunk_terms)
    for term in HEALTHCARE_BOOST_TERMS:
        if term in query_term_set and term in chunk_term_set:
            score += 3

    return score


def retrieve_rag_context(requirement: dict, top_k: int = 6) -> dict:
    documents = load_rag_documents()
    query = build_rag_query(requirement)

    scored_chunks = []
    for document in documents:
        for chunk in chunk_text(
            document["content"],
            sourceName=document["sourceName"],
            fileName=document["fileName"],
        ):
            score = score_chunk(query, chunk)
            if score > 0:
                scored_chunks.append((score, chunk))

    scored_chunks.sort(
        key=lambda item: (
            item[0],
            item[1].get("sourceName", ""),
            -item[1].get("chunkIndex", 0),
        ),
        reverse=True,
    )

    selected_chunks = scored_chunks[:top_k]
    rag_sources = [
        {
            "sourceName": chunk["sourceName"],
            "fileName": chunk["fileName"],
            "chunkIndex": chunk["chunkIndex"],
            "score": score,
        }
        for score, chunk in selected_chunks
    ]

    rag_context_parts = []
    for score, chunk in selected_chunks:
        rag_context_parts.append(
            "\n".join(
                [
                    f"Source: {chunk['sourceName']}",
                    f"File: {chunk['fileName']}",
                    f"Chunk: {chunk['chunkIndex']}",
                    f"Score: {score}",
                    "Content:",
                    chunk["content"],
                ]
            )
        )

    print(
        "RAG retrieval completed",
        {
            "chunksReturned": len(rag_sources),
            "sources": [source["sourceName"] for source in rag_sources],
        },
    )

    return {
        "ragContextText": "\n\n---\n\n".join(rag_context_parts),
        "ragSourcesUsed": rag_sources,
    }


# -----------------------------
# Agent Messages
# -----------------------------
def create_messages(state: AgentInput) -> Sequence[SystemMessage | HumanMessage]:
    requirement_id = getattr(state, "requirementId", "") or ""
    submitted_by = getattr(state, "submittedBy", "") or ""
    environment = getattr(state, "environment", "SQA") or "SQA"

    current_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if not requirement_id.strip() or not submitted_by.strip():
        fetched_requirement = {
            "success": False,
            "status": "Missing required input: requirementId and submittedBy are both mandatory.",
            "httpStatus": None,
            "data": {},
        }
    else:
        fetched_requirement = fetch_azure_devops_requirement(requirement_id.strip())

    retrieved_rag_context = retrieve_rag_context(fetched_requirement.get("data", {}))

    system_prompt_content = """
## Role

You are QualityOpsRequirementAgent, a coded QA requirement fetch and analysis agent.

You receive requirementId, submittedBy, and environment.
The requirement content is fetched directly from Azure DevOps by the coded agent before the LLM analysis step.
The coded agent also performs real local RAG retrieval from markdown QA checklist files before the LLM analysis step.

Your job is to analyze the fetched Azure DevOps content using ONLY the retrieved RAG context provided in the user message and return a structured JSON response matching the output schema.

## Important Rules

- Do not fabricate requirement title, description, or acceptance criteria.
- Use only the fetched requirement JSON and retrieved RAG context provided in the user message.
- If fetch failed, return a clear failure response.
- Do not expose PAT, credentials, headers, or internal connection details.
- Do not call external tools.
- Return only valid JSON matching the output schema.
- No markdown.
- No code fences.
- No explanatory text.
- Use the retrieved RAG context to identify requirement gaps.
- Do not claim a RAG source was used unless that source appears in retrievedRagContext.ragSourcesUsed.
- requirementQualityAnalysis.ragChecklistUsed must be derived from retrievedRagContext.ragSourcesUsed sourceName values only.
- requirementQualityAnalysis.ragEvidenceUsed must include only retrieved sourceName values and a short reasonUsed.
- identifiedGaps must be specific to the requirement details. Avoid generic gaps such as "Missing validation rules"; write a concrete gap such as "Duplicate patient warning behavior is present, but the exact message text and user action after warning should be clarified."

## Readiness Scoring Rules

Start with 100 and reduce:
- Missing requirement description: minus 25
- Missing acceptance criteria: minus 30
- Missing validation rules: minus 10
- Missing error messages: minus 10
- Missing negative scenarios or edge cases: minus 10
- Missing non-functional requirements: minus 5
- Missing integration/dependency details: minus 10
- Missing audit/logging expectations for critical workflows: minus 5
- Unclear expected behavior or pass/fail condition: minus 15

Minimum score is 0.

## Readiness Status Rules

- Score 85 or higher and no critical gaps: Ready
- Score 60 to 84: Needs Review
- Score below 60 or critical gaps: Not Ready

Critical gaps:
- Missing acceptance criteria
- Missing requirement description
- Unclear expected behavior
- Unclear pass/fail conditions for a high-risk workflow

## QA Lead Rules

If Ready:
- humanReviewRequired = false
- qaLeadNotificationRequired = false
- qaLeadActionRequired = false
- approvalRecommendation = "Approve"
- qaLeadDecisionStatus = "Auto-approved for scenario generation"
- nextStep = "Generate test scenarios"

If Needs Review:
- humanReviewRequired = true
- qaLeadNotificationRequired = true
- qaLeadActionRequired = true
- approvalRecommendation = "Needs QA Lead Review"
- qaLeadDecisionStatus = "Pending QA Lead Approval"
- nextStep = "Notify QA Lead for approval"

If Not Ready:
- humanReviewRequired = true
- qaLeadNotificationRequired = true
- qaLeadActionRequired = true
- approvalRecommendation = "Reject and request clarification"
- qaLeadDecisionStatus = "Pending QA Lead Approval"
- nextStep = "Request requirement clarification"

## RAG / QA Checklist Used

Use only retrievedRagContext.ragSourcesUsed.
Do not list checklist names that were not retrieved.

## ADO Write-back

For this Phase 1 version, do not write back to Azure DevOps.
Always set adoUpdateStatus to:
"ADO write-back skipped in Phase 1 coded agent fetch validation."
"""

    enhanced_system_prompt = (
        AGENT_SYSTEM_PROMPT_TEMPLATE
        .replace("{{systemPrompt}}", system_prompt_content)
        .replace("{{currentDate}}", current_date)
        .replace("{{agentName}}", "QualityOpsRequirementAgent")
    )

    user_payload = {
        "requirementId": requirement_id,
        "submittedBy": submitted_by,
        "environment": environment,
        "azureDevOpsFetchResult": fetched_requirement,
        "retrievedRagContext": retrieved_rag_context,
    }

    return [
        SystemMessage(content=enhanced_system_prompt),
        HumanMessage(
            content=interpolate_legacy_message(
                """
Analyze the following Azure DevOps requirement fetch result and return only valid JSON matching the output schema.

Input payload:
{{payload}}

Required JSON structure:
{
  "processingStatus": "",
  "requirementTitle": "",
  "requirementDescription": "",
  "acceptanceCriteria": "",
  "qaAnalysisSummary": {
    "impactedModules": [],
    "changeType": "",
    "riskLevel": "",
    "testingScope": [],
    "suggestedTestFocus": [],
    "humanReviewRequired": true,
    "nextStep": ""
  },
  "requirementQualityAnalysis": {
    "readinessStatus": "",
    "readinessScore": 0,
    "identifiedGaps": [],
    "ragChecklistUsed": [],
    "ragEvidenceUsed": [
      {
        "sourceName": "",
        "reasonUsed": ""
      }
    ],
    "qaLeadActionRequired": true,
    "approvalRecommendation": "",
    "qaLeadDecisionStatus": ""
  },
  "qaLeadNotificationRequired": true,
  "adoUpdateStatus": "ADO write-back skipped in Phase 1 coded agent fetch validation."
}
""",
                {"payload": json.dumps(user_payload, ensure_ascii=False)},
            )
        ),
    ]


# -----------------------------
# Create Agent Graph
# -----------------------------
graph = create_agent(
    model=LazyUiPathChatModel(),
    messages=create_messages,
    tools=[],
    input_schema=AgentInput,
    output_schema=AgentOutput,
)
