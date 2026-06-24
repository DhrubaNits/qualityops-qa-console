import asyncio
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Literal, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, ConfigDict, Field


LOGGER = logging.getLogger(__name__)
FAST_DEMO_MODE = True
ENABLE_CONTEXT_GROUNDING_SEARCH = False
LLM_TIMEOUT_SECONDS = 60
MAX_RAG_CONTEXT_CHARS = 3000
MAX_SCENARIOS_FOR_LLM = 6
LLM_MAX_TOKENS = 4000
MAX_STEPS_PER_SCENARIO = 5
UIPATH_INDEX_NAME = "QualityOps_TestDesign_Knowledge_Index"
RAG_KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parent / "rag_knowledge_base"
RAG_DOCUMENTS = {
    "iso29119_test_design_standard.md": "ISO 29119 Test Design Standard",
    "istqb_testing_principles.md": "ISTQB Testing Principles",
    "qualityops_test_case_standard.md": "QualityOps Test Case Standard",
    "healthcare_workflow_test_checklist.md": "Healthcare Workflow Test Checklist",
    "signed_off_requirement_context.md": "Signed-off Requirement Context",
}
DISPLAY_RAG_SOURCES = [
    "ISO 29119 Test Design Standard",
    "ISTQB Testing Principles",
    "QualityOps Test Case Standard",
    "Healthcare Workflow Test Checklist",
]
BOOST_TERMS = {
    "acceptance criteria",
    "expected result",
    "precondition",
    "test data",
    "traceability",
    "positive",
    "negative",
    "boundary",
    "integration",
    "regression",
    "audit",
    "performance",
    "healthcare",
    "patient",
    "eligibility",
    "appointment",
    "duplicate",
    "provider",
    "location",
    "timeout",
    "api",
    "warning",
    "confirmation",
    "pass/fail",
}
BLOCKED_QA_DECISIONS = {"needs changes", "need changes", "reject", "rejected"}
GENERIC_EXPECTED_RESULT_PATTERNS = (
    "feature behaves as expected",
    "works correctly",
    "requirement is satisfied",
    "all acceptance criteria pass",
    "feature behaves as described",
    "existing behavior remains stable",
)

SYSTEM_PROMPT = """
You are a senior QA test design agent. Generate test scenarios using:
* signed-off requirement
* QA Lead review feedback
* retrieved vector RAG context from UiPath Index
* ISO 29119 test design guidance
* ISTQB testing principles
* QualityOps test case standard
* healthcare workflow checklist
* signed-off requirement context

Do not generate generic expected results.

Every test scenario must include:
* testCaseId
* title
* objective
* testType
* priority
* risk
* traceability
* preconditions
* testData
* steps
* expectedResult
* coverageReason
* automationCandidate
* negativeScenario flag where applicable

Expected result rules:
* Must be specific and measurable.
* Must mention exact system behavior.
* Must mention validation/warning/confirmation behavior where relevant.
* Must mention data persistence or audit behavior where relevant.
* Must not say "feature behaves as expected", "works correctly", "requirement is satisfied", or "all acceptance criteria pass".
""".strip()


class AgentInput(BaseModel):
    question: str = Field(
        ...,
        description="JSON string containing requirement analysis output.",
    )


class RagSource(BaseModel):
    sourceName: str = Field(..., description="Human-readable RAG source name.")
    fileName: str = Field(..., description="Source file name from the UiPath Index or local fallback.")
    score: float = Field(..., description="Relevance score returned by vector search or normalized local fallback.")


class RetrievedRagContext(BaseModel):
    ragContextText: str = Field(default="", description="Retrieved RAG context used for generation.")
    ragSourcesUsed: list[RagSource] = Field(default_factory=list, description="Knowledge-base sources used.")


class TestScenario(BaseModel):
    scenarioId: str = Field(..., description="Scenario identifier such as TS-001.")
    scenarioTitle: str = Field(..., description="Short scenario title.")
    id: str = Field(..., description="UI-compatible scenario identifier.")
    testCaseId: str = Field(..., description="Test case identifier.")
    title: str = Field(..., description="Concise scenario-specific title.")
    objective: str = Field(..., description="One clear objective for the test case.")
    priority: Literal["High", "Medium", "Low"] = Field(..., description="Scenario priority.")
    type: str = Field(..., description="UI-compatible test type.")
    testType: str = Field(..., description="Functional, Negative, Integration, Regression, Audit, or Performance.")
    risk: str = Field(..., description="Risk addressed by the scenario.")
    traceability: dict[str, Any] = Field(default_factory=dict, description="Requirement and acceptance criteria traceability.")
    preconditions: list[str] = Field(default_factory=list, description="Required preconditions.")
    testData: dict[str, Any] = Field(default_factory=dict, description="Specific test data.")
    steps: list[str] = Field(default_factory=list, description="Test execution steps.")
    expectedResult: str = Field(..., description="Specific measurable expected outcome.")
    coverageReason: str = Field(..., description="Why this scenario is included.")
    automationCandidate: bool = Field(..., description="Whether this scenario is suitable for automation.")
    negativeScenario: bool = Field(default=False, description="Whether this is a negative scenario.")


class AgentOutput(BaseModel):
    generationStatus: str = Field(..., description="Completed, Blocked, or Failed.")
    testScenarios: list[TestScenario] = Field(default_factory=list, description="Generated QA test scenarios.")
    generationMode: str = Field(default="", description="llm_rag, deterministic_fallback, or blank when blocked.")
    llmGenerationUsed: bool = Field(default=False, description="Whether LLM RAG generation produced the returned scenarios.")
    ragSourcesUsed: list[str] = Field(default_factory=list, description="RAG sources used by generation.")
    retrievedRagContext: RetrievedRagContext = Field(default_factory=RetrievedRagContext)
    vectorRagStatus: str = Field(default="Failed", description="Used, No semantic results returned, or Failed.")
    vectorChunksReturned: int = Field(default=0, description="Number of chunks returned by UiPath Index vector RAG.")
    vectorQueriesTried: list[str] = Field(default_factory=list, description="Short vector RAG queries attempted.")
    fallbackRagUsed: bool = Field(default=False, description="Whether local RAG fallback was used.")
    missingInformation: list[str] = Field(default_factory=list, description="Information required when generation is blocked.")
    blockedReason: str = Field(default="", description="Reason final executable scenarios were not generated.")


class GraphState(TypedDict, total=False):
    question: str
    generationStatus: str
    testScenarios: list[dict[str, Any]]
    generationMode: str
    llmGenerationUsed: bool
    ragSourcesUsed: list[str]
    retrievedRagContext: dict[str, Any]
    vectorRagStatus: str
    vectorChunksReturned: int
    vectorQueriesTried: list[str]
    fallbackRagUsed: bool
    missingInformation: list[str]
    blockedReason: str


class RequirementPayload(BaseModel):
    model_config = ConfigDict(extra="allow")

    requirementId: str = ""
    submittedBy: str = ""
    environment: str = ""
    requirementTitle: str = ""
    requirementDescription: str = ""
    acceptanceCriteria: Any = ""
    riskLevel: str = "Medium"
    testingScope: list[str] = Field(default_factory=list)
    suggestedTestFocus: list[str] = Field(default_factory=list)
    identifiedGaps: list[str] = Field(default_factory=list)
    requirementAnalysis: dict[str, Any] = Field(default_factory=dict)
    qaLeadReview: dict[str, Any] = Field(default_factory=dict)
    readinessStatus: str = ""
    status: str = ""


def _clean_text(value: Any, fallback: str = "the requirement") -> str:
    if value is None:
        return fallback

    if isinstance(value, (dict, list)):
        text = json.dumps(value, ensure_ascii=True)
    else:
        text = str(value)

    text = text.strip()
    return text or fallback


def _clean_list(values: Any) -> list[str]:
    if isinstance(values, str):
        values = [item.strip() for item in re.split(r"\n|;", values) if item.strip()]
    if not isinstance(values, list):
        return []

    cleaned = []
    for value in values:
        text = _clean_text(value, "").strip()
        if text:
            cleaned.append(text)

    return cleaned


def _tokenize(value: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", value.casefold())


def _get_nested_text(data: dict[str, Any], paths: list[tuple[str, ...]]) -> list[str]:
    values: list[str] = []
    for path in paths:
        current: Any = data
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if current not in (None, "", [], {}):
            values.append(_clean_text(current, ""))
    return values


def load_rag_documents() -> list[dict[str, str]]:
    documents = []
    for file_name, source_name in RAG_DOCUMENTS.items():
        path = RAG_KNOWLEDGE_BASE_DIR / file_name
        if path.exists():
            documents.append(
                {
                    "source": source_name,
                    "fileName": file_name,
                    "text": path.read_text(encoding="utf-8"),
                }
            )
    return documents


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 200) -> list[str]:
    if not text:
        return []

    normalized = re.sub(r"\s+", " ", text).strip()
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks = []
    start = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            boundary = normalized.rfind(" ", start, end)
            if boundary > start + (chunk_size // 2):
                end = boundary
        chunks.append(normalized[start:end].strip())
        if end >= len(normalized):
            break
        start = max(end - overlap, start + 1)

    return [chunk for chunk in chunks if chunk]


def build_test_generation_rag_query(input_payload: dict[str, Any]) -> str:
    requirement_analysis = input_payload.get("requirementAnalysis")
    qa_lead_review = input_payload.get("qaLeadReview")
    requirement_analysis = requirement_analysis if isinstance(requirement_analysis, dict) else {}
    qa_lead_review = qa_lead_review if isinstance(qa_lead_review, dict) else {}

    fields = [
        input_payload.get("requirementTitle"),
        input_payload.get("requirementDescription"),
        input_payload.get("acceptanceCriteria"),
        requirement_analysis.get("suggestedTestFocus"),
        requirement_analysis.get("testingScope"),
        qa_lead_review.get("feedbackText"),
        input_payload.get("requirementAnalysis"),
        input_payload.get("qaLeadReview"),
        input_payload.get("requirementId"),
        input_payload.get("testingScope"),
        input_payload.get("suggestedTestFocus"),
        input_payload.get("identifiedGaps"),
    ]
    query = "\n".join(_clean_text(field, "") for field in fields if field not in (None, "", [], {}))
    if len(query.strip()) < 80:
        return (
            "ISO 29119 ISTQB healthcare workflow patient registration eligibility appointment "
            "scheduling validation expected result audit API timeout duplicate patient"
        )
    return query


def _keywords_from_value(value: Any, max_terms: int = 18) -> list[str]:
    text = _clean_text(value, "")
    tokens = _tokenize(text)
    stop_words = {
        "the",
        "and",
        "or",
        "to",
        "of",
        "a",
        "an",
        "in",
        "for",
        "with",
        "is",
        "are",
        "be",
        "as",
        "by",
        "on",
        "this",
        "that",
        "should",
        "must",
        "will",
        "user",
        "system",
    }
    keywords: list[str] = []
    for token in tokens:
        if len(token) < 3 or token in stop_words:
            continue
        if token not in keywords:
            keywords.append(token)
        if len(keywords) >= max_terms:
            break
    return keywords


def build_vector_rag_query(input_payload: dict[str, Any]) -> str:
    requirement_analysis = input_payload.get("requirementAnalysis")
    qa_lead_review = input_payload.get("qaLeadReview")
    requirement_analysis = requirement_analysis if isinstance(requirement_analysis, dict) else {}
    qa_lead_review = qa_lead_review if isinstance(qa_lead_review, dict) else {}

    source_values = [
        input_payload.get("requirementTitle"),
        input_payload.get("requirementDomain"),
        input_payload.get("domain"),
        input_payload.get("impactedModules"),
        input_payload.get("testingScope"),
        input_payload.get("suggestedTestFocus"),
        requirement_analysis.get("requirementDomain"),
        requirement_analysis.get("domain"),
        requirement_analysis.get("impactedModules"),
        requirement_analysis.get("testingScope"),
        requirement_analysis.get("suggestedTestFocus"),
        qa_lead_review.get("feedbackText"),
        qa_lead_review.get("feedback"),
        qa_lead_review.get("comments"),
    ]
    keywords: list[str] = []
    for value in source_values:
        for keyword in _keywords_from_value(value):
            if keyword not in keywords:
                keywords.append(keyword)

    if not keywords:
        query = (
            "healthcare patient registration eligibility appointment scheduling mandatory field validation "
            "duplicate patient warning audit trail API timeout integration failure expected result ISO 29119 "
            "ISTQB test case design"
        )
    else:
        query = " ".join(keywords)

    if len(query) > 800:
        query = query[:800]
    if len(query.strip()) < 40:
        query = (
            "healthcare patient registration eligibility appointment scheduling mandatory field validation "
            "duplicate patient warning audit trail API timeout integration failure expected result ISO 29119 "
            "ISTQB test case design"
        )
    return query[:800]


def score_chunk(query: str, chunk: str) -> float:
    query_tokens = set(_tokenize(query))
    chunk_tokens = set(_tokenize(chunk))
    if not query_tokens or not chunk_tokens:
        return 0.0

    score = float(len(query_tokens & chunk_tokens))
    query_lower = query.casefold()
    chunk_lower = chunk.casefold()
    for term in BOOST_TERMS:
        if term in query_lower and term in chunk_lower:
            score += 5.0
        elif term in chunk_lower:
            score += 1.5

    return score


def _source_file_name(source: Any) -> str:
    source_text = _clean_text(source, "")
    if not source_text:
        return "unknown"

    normalized = source_text.replace("\\", "/").split("/")[-1].strip()
    return normalized or source_text


def _source_display_name(file_name: str) -> str:
    normalized = file_name.casefold()
    for known_file_name, source_name in RAG_DOCUMENTS.items():
        if known_file_name.casefold() in normalized:
            return source_name

    stem = Path(file_name).stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() if stem else "UiPath Index Source"


def _rag_source_record(source: Any, score: Any = None) -> dict[str, Any]:
    file_name = _source_file_name(source)
    try:
        numeric_score = round(float(score), 4) if score is not None else 0.0
    except (TypeError, ValueError):
        numeric_score = 0.0

    return {
        "sourceName": _source_display_name(file_name),
        "fileName": file_name,
        "score": numeric_score,
    }


def _dedupe_rag_sources(sources: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for source in sources:
        key = (
            _clean_text(source.get("sourceName"), ""),
            _clean_text(source.get("fileName"), ""),
        )
        existing = deduped.get(key)
        if existing is None or float(source.get("score", 0.0)) > float(existing.get("score", 0.0)):
            deduped[key] = source

    return list(deduped.values())


def _rag_source_names(sources: list[dict[str, Any]]) -> list[str]:
    return list(dict.fromkeys(_clean_text(source.get("sourceName"), "") for source in sources if source.get("sourceName")))


RESULT_ARRAY_KEYS = {
    "value",
    "values",
    "data",
    "results",
    "documents",
    "hits",
    "items",
    "records",
    "chunks",
}
TEXT_FIELD_KEYS = (
    "text",
    "content",
    "chunk",
    "pageContent",
    "documentText",
    "matchedText",
    "value",
    "snippet",
)
SOURCE_FIELD_KEYS = (
    "fileName",
    "source",
    "sourceName",
    "documentName",
    "title",
)
SCORE_FIELD_KEYS = ("score", "relevance", "similarity", "rankScore")


def _is_debug_rag_enabled() -> bool:
    return os.environ.get("QUALITYOPS_RAG_DEBUG", "").strip().casefold() in {"1", "true", "yes", "on"}


def _redact_sensitive_text(value: str) -> str:
    redacted = re.sub(r"(?i)(authorization\s*[:=]\s*)[^\s,}]+", r"\1<redacted>", value)
    redacted = re.sub(r"(?i)(bearer\s+)[a-z0-9._\-]+", r"\1<redacted>", redacted)
    redacted = re.sub(r"(?i)((pat|token|client_secret|secret|password)\s*[:=]\s*)[^,\s}]+", r"\1<redacted>", redacted)
    return redacted


def _safe_response_preview(data: Any) -> str:
    try:
        preview = json.dumps(data, ensure_ascii=True, default=str)[:500]
    except TypeError:
        preview = str(data)[:500]
    return _redact_sensitive_text(preview)


def _dict_keys(value: Any) -> list[str]:
    return list(value.keys()) if isinstance(value, dict) else []


def _find_result_arrays(value: Any) -> list[list[Any]]:
    arrays: list[list[Any]] = []
    if isinstance(value, dict):
        for key, nested in value.items():
            if key == "semanticResults" and isinstance(nested, list):
                arrays.append(nested)
            elif key == "semanticResults" and isinstance(nested, dict):
                arrays.extend(_find_result_arrays(nested))
            if key in RESULT_ARRAY_KEYS and isinstance(nested, list):
                arrays.append(nested)
            elif key in RESULT_ARRAY_KEYS and isinstance(nested, dict):
                arrays.extend(_find_result_arrays(nested))
            elif isinstance(nested, (dict, list)):
                arrays.extend(_find_result_arrays(nested))
    elif isinstance(value, list):
        if value and all(isinstance(item, (dict, str)) for item in value):
            arrays.append(value)
        for item in value:
            if isinstance(item, (dict, list)):
                arrays.extend(_find_result_arrays(item))
    return arrays


def _first_text_from_item(item: Any) -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return ""

    for key in TEXT_FIELD_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in TEXT_FIELD_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for nested_key in ("document", "data"):
        nested = item.get(nested_key)
        if isinstance(nested, dict):
            for key in TEXT_FIELD_KEYS:
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    return ""


def _first_source_from_item(item: Any) -> str:
    if not isinstance(item, dict):
        return "uipath_index_result"

    for key in SOURCE_FIELD_KEYS:
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in SOURCE_FIELD_KEYS:
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()

    for nested_key in ("document", "data"):
        nested = item.get(nested_key)
        if isinstance(nested, dict):
            for key in SOURCE_FIELD_KEYS:
                value = nested.get(key)
                if isinstance(value, str) and value.strip():
                    return value.strip()

    return "uipath_index_result"


def _first_score_from_item(item: Any) -> float:
    if not isinstance(item, dict):
        return 0.0

    for key in SCORE_FIELD_KEYS:
        value = item.get(key)
        try:
            return float(value)
        except (TypeError, ValueError):
            pass

    metadata = item.get("metadata")
    if isinstance(metadata, dict):
        for key in SCORE_FIELD_KEYS:
            value = metadata.get(key)
            try:
                return float(value)
            except (TypeError, ValueError):
                pass

    for nested_key in ("document", "data"):
        nested = item.get(nested_key)
        if isinstance(nested, dict):
            for key in SCORE_FIELD_KEYS:
                value = nested.get(key)
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass

    return 0.0


def _semantic_results_items(response_json: Any) -> list[Any]:
    if not isinstance(response_json, dict):
        return []

    semantic_results = response_json.get("semanticResults")
    if isinstance(semantic_results, list):
        return semantic_results
    if isinstance(semantic_results, dict):
        for key in ("values", "value", "results", "documents", "hits", "items", "records", "chunks", "data"):
            value = semantic_results.get(key)
            if isinstance(value, list):
                return value
    return []


def _parse_uipath_index_chunks(response_json: Any) -> list[dict[str, Any]]:
    parsed: list[dict[str, Any]] = []
    for result_array in _find_result_arrays(response_json):
        for item in result_array:
            text = _first_text_from_item(item)
            if not text:
                continue
            parsed.append(
                {
                    "text": text,
                    "source": _first_source_from_item(item),
                    "score": _first_score_from_item(item),
                    "rawKeys": _dict_keys(item),
                }
            )

    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    for chunk in parsed:
        key = (chunk["source"], chunk["text"][:200])
        deduped.setdefault(key, chunk)
    return list(deduped.values())


def _safe_payload_keys(payload: dict[str, Any]) -> list[str]:
    return list(payload.keys())


def _result_to_response_json(result: Any) -> dict[str, Any]:
    if hasattr(result, "model_dump"):
        return result.model_dump(by_alias=True, mode="json")
    return result if isinstance(result, dict) else {}


def _legacy_search_results_to_response_json(results: Any) -> dict[str, Any]:
    values = []
    for item in results or []:
        if hasattr(item, "model_dump"):
            values.append(item.model_dump(by_alias=True, mode="json"))
        elif isinstance(item, dict):
            values.append(item)
    return {"semanticResults": values}


def _build_raw_search_payloads(query: str, top_k: int) -> list[dict[str, Any]]:
    return [
        {
            "searchMode": "Semantic",
            "query": query,
            "semanticSearchOptions": {
                "numberOfResults": top_k,
                "threshold": 0.0,
            },
        },
        {"query": query, "topK": top_k, "threshold": 0},
        {"query": query, "numberOfResults": top_k, "queryThreshold": 0},
        {"searchQuery": query, "numberOfResults": top_k, "queryThreshold": 0},
        {"text": query, "top": top_k, "threshold": 0},
    ]


def _log_vector_attempt(
    *,
    index_id: str,
    query: str,
    status_code: Any,
    response_json: Any,
    chunks: list[dict[str, Any]],
    payload: dict[str, Any] | None = None,
    method: str = "",
) -> None:
    semantic_items = _semantic_results_items(response_json)
    first_result_keys = _dict_keys(semantic_items[0]) if semantic_items and isinstance(semantic_items[0], dict) else []
    source_names = _rag_source_names(
        [_rag_source_record(chunk["source"], chunk["score"]) for chunk in chunks]
    )
    threshold = None
    if payload:
        threshold = payload.get("threshold", payload.get("queryThreshold"))
        semantic_options = payload.get("semanticSearchOptions")
        if threshold is None and isinstance(semantic_options, dict):
            threshold = semantic_options.get("threshold")

    print(
        "Vector RAG retrieval completed",
        {
            "method": method,
            "indexId": index_id,
            "payloadKeys": _safe_payload_keys(payload or {}),
            "queryLength": len(query),
            "queryPreview": query[:200],
            "threshold": threshold,
            "searchResponseStatusCode": status_code,
            "topLevelResponseJsonKeys": _dict_keys(response_json),
            "semanticResultsCount": len(semantic_items),
            "firstResultKeys": first_result_keys,
            "chunksReturned": len(chunks),
            "sources": source_names,
        },
    )
    if _is_debug_rag_enabled():
        print("Vector RAG safe response preview", _safe_response_preview(response_json))


def _vector_success(chunks: list[dict[str, Any]], queries_to_try: list[str], current_query: str) -> dict[str, Any]:
    rag_sources = _dedupe_rag_sources([_rag_source_record(chunk["source"], chunk["score"]) for chunk in chunks])
    rag_context_text = "\n\n".join(
        f"[{_source_display_name(_source_file_name(chunk['source']))}]\n{chunk['text']}"
        for chunk in chunks
    )
    return {
        "ragContextText": rag_context_text,
        "ragSourcesUsed": rag_sources,
        "chunkCount": len(chunks),
        "retrievalMode": "uipath_index",
        "vectorRagStatus": "Used",
        "fallbackRagUsed": False,
        "vectorQueriesTried": queries_to_try[: queries_to_try.index(current_query) + 1],
    }


def query_uipath_index(query: str, top_k: int = 8) -> dict[str, Any]:
    # Uses UiPath Context Grounding / Index search when runtime credentials are available.
    # TODO: If the SDK contract changes, update this wrapper and keep local RAG fallback intact.
    status_code: int | None = None
    index_id = ""
    queries_to_try = [query[:800]]
    if not FAST_DEMO_MODE:
        queries_to_try.extend(
            [
                "healthcare patient registration eligibility appointment scheduling duplicate patient audit trail API timeout expected result",
                "ISO 29119 test case expected result preconditions test data traceability ISTQB healthcare workflow",
            ]
        )
    queries_to_try = list(dict.fromkeys(item for item in queries_to_try if item.strip()))

    try:
        from uipath.platform import UiPath
        from uipath.platform.context_grounding import SearchMode

        sdk = UiPath()
        index = sdk.context_grounding.retrieve(UIPATH_INDEX_NAME)
        index_id = _clean_text(getattr(index, "id", ""), "")
        folder_key = getattr(index, "folder_key", None)

        for current_query in queries_to_try:
            current_query = current_query[:800]
            vector_top_k = 5 if FAST_DEMO_MODE else top_k
            sdk_payload = {
                "query": current_query,
                "numberOfResults": vector_top_k,
                "threshold": 0.0,
                "searchMode": "Semantic",
            }
            result = sdk.context_grounding.unified_search(
                name=UIPATH_INDEX_NAME,
                query=current_query,
                search_mode=SearchMode.SEMANTIC,
                number_of_results=vector_top_k,
                threshold=0.0,
                folder_key=folder_key,
            )
            response_json = _result_to_response_json(result)
            chunks = _parse_uipath_index_chunks(response_json)
            _log_vector_attempt(
                index_id=index_id,
                query=current_query,
                status_code="SDK",
                response_json=response_json,
                chunks=chunks,
                payload=sdk_payload,
                method="sdk.unified_search",
            )
            if chunks:
                return _vector_success(chunks, queries_to_try, current_query)

            if FAST_DEMO_MODE:
                print("UiPath Index fast demo search returned no parseable chunks; using local RAG fallback.")
                return {
                    "ragContextText": "",
                    "ragSourcesUsed": [],
                    "chunkCount": 0,
                    "retrievalMode": "uipath_index",
                    "vectorRagStatus": "No semantic results returned",
                    "fallbackRagUsed": False,
                    "vectorQueriesTried": queries_to_try,
                }

            try:
                legacy_payload = {
                    "query": current_query,
                    "numberOfResults": top_k,
                    "threshold": 0.0,
                }
                legacy_results = sdk.context_grounding.search(
                    name=UIPATH_INDEX_NAME,
                    query=current_query,
                    number_of_results=top_k,
                    threshold=0.0,
                    folder_key=folder_key,
                )
                response_json = _legacy_search_results_to_response_json(legacy_results)
                chunks = _parse_uipath_index_chunks(response_json)
                _log_vector_attempt(
                    index_id=index_id,
                    query=current_query,
                    status_code="SDK",
                    response_json=response_json,
                    chunks=chunks,
                    payload=legacy_payload,
                    method="sdk.search",
                )
                if chunks:
                    return _vector_success(chunks, queries_to_try, current_query)
            except Exception as legacy_exc:
                print(
                    "Vector RAG retrieval attempt failed",
                    {
                        "method": "sdk.search",
                        "indexId": index_id,
                        "payloadKeys": ["query", "numberOfResults", "threshold"],
                        "queryLength": len(current_query),
                        "queryPreview": current_query[:200],
                        "threshold": 0.0,
                        "errorType": type(legacy_exc).__name__,
                    },
                )

            spec = sdk.context_grounding._unified_search_spec(
                index_id=index_id,
                query=current_query,
                search_mode=SearchMode.SEMANTIC,
                number_of_results=top_k,
                threshold=0.0,
                folder_key=folder_key,
            )
            for raw_payload in _build_raw_search_payloads(current_query, top_k):
                try:
                    response = sdk.context_grounding.request(
                        spec.method,
                        spec.endpoint,
                        json=raw_payload,
                        headers=spec.headers,
                    )
                    status_code = response.status_code
                    response_json = response.json()
                    chunks = _parse_uipath_index_chunks(response_json)
                    _log_vector_attempt(
                        index_id=index_id,
                        query=current_query,
                        status_code=status_code,
                        response_json=response_json,
                        chunks=chunks,
                        payload=raw_payload,
                        method="raw.v1.2.search",
                    )
                    if chunks:
                        return _vector_success(chunks, queries_to_try, current_query)
                except Exception as raw_exc:
                    print(
                        "Vector RAG retrieval attempt failed",
                        {
                            "method": "raw.v1.2.search",
                            "indexId": index_id,
                            "payloadKeys": _safe_payload_keys(raw_payload),
                            "queryLength": len(current_query),
                            "queryPreview": current_query[:200],
                            "threshold": raw_payload.get("threshold", raw_payload.get("queryThreshold")),
                            "errorType": type(raw_exc).__name__,
                        },
                    )
    except Exception as exc:
        print(
            "Vector RAG retrieval failed",
            {
                "indexId": index_id,
                "queryLength": len(queries_to_try[0]) if queries_to_try else 0,
                "queryPreview": queries_to_try[0][:200] if queries_to_try else "",
                "searchResponseStatusCode": status_code,
                "errorType": type(exc).__name__,
            },
        )
        return {
            "ragContextText": "",
            "ragSourcesUsed": [],
            "chunkCount": 0,
            "retrievalMode": "uipath_index",
            "vectorRagStatus": "Failed",
            "fallbackRagUsed": False,
            "vectorQueriesTried": queries_to_try,
        }

    print("UiPath Index search returned 200 but no parseable chunks. Check response schema.")

    return {
        "ragContextText": "",
        "ragSourcesUsed": [],
        "chunkCount": 0,
        "retrievalMode": "uipath_index",
        "vectorRagStatus": "No semantic results returned",
        "fallbackRagUsed": False,
        "vectorQueriesTried": queries_to_try,
    }


def _retrieve_local_rag_context(query: str, top_k: int = 8) -> dict[str, Any]:
    scored_chunks: list[dict[str, Any]] = []

    for document in load_rag_documents():
        for index, chunk in enumerate(chunk_text(document["text"])):
            scored_chunks.append(
                {
                    "source": document["source"],
                    "fileName": document["fileName"],
                    "chunkIndex": index,
                    "chunk": chunk,
                    "score": score_chunk(query, chunk),
                }
            )

    selected = sorted(scored_chunks, key=lambda item: item["score"], reverse=True)[:top_k]
    selected = [item for item in selected if item["score"] > 0]
    max_score = max((float(item["score"]) for item in selected), default=1.0)
    sources = _dedupe_rag_sources(
        [
            _rag_source_record(item.get("fileName") or item["source"], float(item["score"]) / max_score)
            for item in selected
        ]
    )
    rag_context_text = "\n\n".join(
        f"[{item['source']}]\n{item['chunk']}" for item in selected
    )

    return {
        "ragContextText": rag_context_text,
        "ragSourcesUsed": sources,
        "chunkCount": len(selected),
        "retrievalMode": "local_fallback",
        "vectorRagStatus": "Failed",
        "vectorChunksReturned": 0,
        "vectorQueriesTried": [],
        "fallbackRagUsed": True,
    }


def retrieve_test_generation_rag_context(input_payload: dict[str, Any], top_k: int = 8) -> dict[str, Any]:
    if FAST_DEMO_MODE and not ENABLE_CONTEXT_GROUNDING_SEARCH:
        fallback_query = build_test_generation_rag_query(input_payload)
        fallback_context = _retrieve_local_rag_context(fallback_query, top_k=top_k)
        fallback_context["vectorRagStatus"] = "Skipped in fast demo mode"
        fallback_context["vectorChunksReturned"] = 0
        fallback_context["vectorQueriesTried"] = []
        fallback_context["fallbackRagUsed"] = True
        fallback_context["retrievalMode"] = "local_fallback"
        rag_context_text = fallback_context.get("ragContextText", "")
        if len(rag_context_text) > MAX_RAG_CONTEXT_CHARS:
            fallback_context["ragContextText"] = rag_context_text[:MAX_RAG_CONTEXT_CHARS]
        return fallback_context

    vector_query = build_vector_rag_query(input_payload)
    vector_context = query_uipath_index(vector_query, top_k=top_k)
    if vector_context.get("ragContextText"):
        rag_context_text = vector_context.get("ragContextText", "")
        if len(rag_context_text) > MAX_RAG_CONTEXT_CHARS:
            vector_context["ragContextText"] = rag_context_text[:MAX_RAG_CONTEXT_CHARS]
        vector_context["vectorChunksReturned"] = int(vector_context.get("chunkCount", 0))
        return vector_context

    fallback_query = build_test_generation_rag_query(input_payload)
    fallback_context = _retrieve_local_rag_context(fallback_query, top_k=top_k)
    rag_context_text = fallback_context.get("ragContextText", "")
    if len(rag_context_text) > MAX_RAG_CONTEXT_CHARS:
        fallback_context["ragContextText"] = rag_context_text[:MAX_RAG_CONTEXT_CHARS]
    fallback_context["vectorRagStatus"] = vector_context.get("vectorRagStatus", "No semantic results returned")
    fallback_context["vectorChunksReturned"] = int(vector_context.get("chunkCount", 0))
    fallback_context["vectorQueriesTried"] = vector_context.get("vectorQueriesTried", [])
    fallback_context["fallbackRagUsed"] = True
    return fallback_context


def _remove_consecutive_duplicate_words(value: str) -> str:
    words = value.split()
    if not words:
        return value

    deduplicated = [words[0]]
    for word in words[1:]:
        if word.casefold() != deduplicated[-1].casefold():
            deduplicated.append(word)

    return " ".join(deduplicated)


def _normalize_title(value: str, requirement_title: str = "") -> str:
    title = re.sub(r"\s+", " ", value).strip(" -")
    title = re.sub(r"^(validate|verify|confirm)\s+\1\b", r"\1", title, flags=re.IGNORECASE)
    title = _remove_consecutive_duplicate_words(title)

    if requirement_title:
        req = re.escape(_remove_consecutive_duplicate_words(requirement_title).strip())
        title = re.sub(rf"^(validate|verify|confirm)\s+{req}\s*[-:]\s*", "", title, flags=re.IGNORECASE)
        title = re.sub(rf"^{req}\s*[-:]\s*", "", title, flags=re.IGNORECASE)

    return title[:1].upper() + title[1:] if title else "Test scenario"


def _priority_for(risk_level: str, index: int, test_type: str) -> Literal["High", "Medium", "Low"]:
    normalized = risk_level.strip().lower()

    if normalized in {"high", "critical"}:
        return "High" if index <= 7 else "Medium"

    if normalized == "low":
        return "Medium" if test_type in {"Functional", "Regression", "Integration"} else "Low"

    return "High" if test_type in {"Functional", "Negative"} and index <= 3 else "Medium"


def _acceptance_criteria_list(payload: RequirementPayload) -> list[str]:
    criteria = _clean_list(payload.acceptanceCriteria)
    if criteria:
        return criteria

    text = _clean_text(payload.acceptanceCriteria, "")
    if not text:
        return []

    parts = re.split(r"\n|;|\.\s+", text)
    return [part.strip(" .") for part in parts if part.strip(" .")]


def _is_generation_blocked(raw_payload: dict[str, Any], payload: RequirementPayload) -> tuple[bool, list[str], str]:
    readiness_values = [
        payload.readinessStatus,
        payload.status,
        payload.requirementAnalysis.get("readinessStatus"),
        payload.requirementAnalysis.get("requirementReadiness"),
        payload.requirementAnalysis.get("status"),
    ]
    qa_decision_values = [
        payload.qaLeadReview.get("decision"),
        payload.qaLeadReview.get("reviewDecision"),
        payload.qaLeadReview.get("approvalStatus"),
        raw_payload.get("qaLeadDecision"),
    ]

    readiness = " ".join(_clean_text(value, "") for value in readiness_values).casefold()
    qa_decision = " ".join(_clean_text(value, "") for value in qa_decision_values).casefold()

    blocked = "not ready" in readiness or any(decision in qa_decision for decision in BLOCKED_QA_DECISIONS)
    if not blocked:
        return False, [], ""

    gaps = _clean_list(payload.identifiedGaps)
    gaps.extend(_clean_list(payload.requirementAnalysis.get("identifiedGaps")))
    gaps.extend(_clean_list(payload.requirementAnalysis.get("gaps")))
    gaps.extend(_clean_list(payload.qaLeadReview.get("missingInformation")))
    gaps.extend(_clean_list(payload.qaLeadReview.get("requiredChanges")))

    missing = list(dict.fromkeys(gaps))
    if not missing:
        missing = [
            "Signed-off requirement marked Ready for QA test design.",
            "QA Lead decision of Approve.",
            "Complete acceptance criteria and expected business rules.",
        ]

    return True, missing, "Requirement is not approved for final executable test-case generation."


def _build_llm_input_payload(raw_payload: dict[str, Any], rag_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "systemPrompt": SYSTEM_PROMPT,
        "requirementId": raw_payload.get("requirementId", ""),
        "signedOffRequirement": {
            "requirementId": raw_payload.get("requirementId", ""),
            "requirementTitle": raw_payload.get("requirementTitle", ""),
            "requirementDescription": raw_payload.get("requirementDescription", ""),
            "acceptanceCriteria": raw_payload.get("acceptanceCriteria", ""),
            "testingScope": raw_payload.get("testingScope", []),
            "suggestedTestFocus": raw_payload.get("suggestedTestFocus", []),
        },
        "requirementAnalysis": raw_payload.get("requirementAnalysis", {}),
        "qaLeadReview": raw_payload.get("qaLeadReview", {}),
        "retrievedRagContext": {
            "ragContextText": rag_context.get("ragContextText", ""),
            "ragSourcesUsed": rag_context.get("ragSourcesUsed", []),
        },
    }


def _build_scenario(
    index: int,
    title: str,
    priority: Literal["High", "Medium", "Low"],
    test_type: str,
    preconditions: list[str],
    steps: list[str],
    expected_result: str,
    objective: str = "",
    risk: str = "",
    traceability: dict[str, Any] | None = None,
    test_data: dict[str, Any] | None = None,
    coverage_reason: str = "",
    automation_candidate: bool = True,
    negative_scenario: bool = False,
    requirement_title: str = "",
) -> dict[str, Any]:
    test_case_id = f"TS-{index:03d}"
    normalized_title = _normalize_title(title, requirement_title)
    if any(pattern in expected_result.casefold() for pattern in GENERIC_EXPECTED_RESULT_PATTERNS):
        raise ValueError(f"Generic expected result is not allowed for {test_case_id}.")

    return {
        "scenarioId": test_case_id,
        "scenarioTitle": normalized_title,
        "id": test_case_id,
        "testCaseId": test_case_id,
        "title": normalized_title,
        "objective": objective or normalized_title,
        "priority": priority,
        "type": test_type,
        "testType": test_type,
        "risk": risk or "Requirement behavior may not be validated against signed-off acceptance criteria.",
        "traceability": traceability or {},
        "preconditions": preconditions,
        "testData": test_data or {},
        "steps": steps,
        "expectedResult": expected_result,
        "coverageReason": coverage_reason or "Covers signed-off requirement and acceptance criteria.",
        "automationCandidate": automation_candidate,
        "negativeScenario": negative_scenario,
    }


def _standard_traceability(payload: RequirementPayload, criteria: list[str], coverage: str) -> dict[str, Any]:
    return {
        "requirementId": _clean_text(payload.requirementId, "N/A"),
        "acceptanceCriteria": criteria[:4],
        "coverage": coverage,
    }


def _standard_steps(include_eligibility: bool = True, include_scheduler: bool = True) -> list[str]:
    steps = [
        "Login as clinic staff user.",
        "Navigate to Patient Registration.",
        "Enter First Name, Last Name, DOB, Gender, Phone, and Address.",
        "Save patient record.",
    ]
    if include_eligibility:
        steps.append("Run eligibility verification.")
    if include_scheduler:
        steps.extend(
            [
                "Navigate to Scheduler.",
                "Select provider, location, appointment date/time, and appointment type.",
                "Save appointment.",
            ]
        )
    return steps


def _generate_fallback_scenarios(payload: RequirementPayload, llm_payload: dict[str, Any]) -> list[dict[str, Any]]:
    requirement_id = _clean_text(payload.requirementId, "the requirement")
    requirement_title = _clean_text(payload.requirementTitle, "Patient registration and scheduling")
    environment = _clean_text(payload.environment, "target test environment")
    risk_level = _clean_text(payload.riskLevel, "Medium")
    criteria = _acceptance_criteria_list(payload)
    focus = _clean_list(payload.suggestedTestFocus)
    traceability_base = _standard_traceability(payload, criteria, "Signed-off healthcare workflow requirement")

    common_preconditions = [
        f"Requirement {requirement_id} is signed off and approved by QA Lead.",
        f"{environment} is available with clinic staff role access.",
        "Patient registration, eligibility verification, scheduler, and audit modules are enabled.",
    ]

    scenarios = [
        {
            "title": "Create patient and appointment successfully with active eligibility",
            "test_type": "Functional",
            "preconditions": common_preconditions + ["Eligibility service returns Active for the patient test data."],
            "steps": _standard_steps(),
            "expected_result": (
                "Patient record is created successfully with the entered demographic details. Eligibility status is "
                "displayed as Active. Appointment is saved for the selected provider, date, time, type, and location. "
                "A confirmation message is displayed, and audit history captures patient creation and appointment creation events."
            ),
            "objective": "Verify the approved end-to-end happy path from patient registration through appointment creation.",
            "risk": "A patient may be registered or scheduled incorrectly when the primary clinical workflow is used.",
            "coverage_reason": "Covers positive flow, persistence, confirmation, eligibility, appointment, and audit expectations.",
            "test_data": {
                "patient": "New patient with unique First Name, Last Name, DOB, Gender, Phone, and Address",
                "eligibilityStatus": "Active",
                "appointment": "Valid provider, location, future date/time, and appointment type",
            },
            "negative": False,
        },
        {
            "title": "Validate mandatory patient demographic fields during registration",
            "test_type": "Negative",
            "preconditions": common_preconditions,
            "steps": [
                "Login as clinic staff user.",
                "Navigate to Patient Registration.",
                "Leave First Name, Last Name, DOB, and Gender blank.",
                "Enter optional contact details only.",
                "Select Save patient record.",
            ],
            "expected_result": (
                "Patient record is not saved. Field-level validation messages are displayed for First Name, Last Name, DOB, "
                "and Gender. The Save action keeps the user on Patient Registration, no patient identifier is created, "
                "and no patient creation audit event is recorded."
            ),
            "objective": "Verify mandatory demographic fields are enforced before patient creation.",
            "risk": "Incomplete patient demographics may create unsafe or unusable patient records.",
            "coverage_reason": "Covers mandatory field validation and prevention of invalid persistence.",
            "test_data": {"missingFields": ["First Name", "Last Name", "DOB", "Gender"]},
            "negative": True,
        },
        {
            "title": "Validate contact and address field rules during registration",
            "test_type": "Negative",
            "preconditions": common_preconditions,
            "steps": [
                "Login as clinic staff user.",
                "Navigate to Patient Registration.",
                "Enter valid First Name, Last Name, DOB, and Gender.",
                "Enter phone number with alphabetic characters and an incomplete address.",
                "Select Save patient record.",
            ],
            "expected_result": (
                "Patient record is not saved until the phone and address values satisfy configured validation rules. "
                "The system highlights the invalid Phone and Address fields, displays clear correction messages, "
                "and preserves the entered valid demographic values for correction."
            ),
            "objective": "Verify secondary mandatory or format-controlled patient fields produce actionable validation.",
            "risk": "Invalid contact data may prevent patient follow-up or downstream eligibility matching.",
            "coverage_reason": "Covers additional mandatory/format validations requested by QualityOps standards.",
            "test_data": {"phone": "ABC-123", "address": "Incomplete"},
            "negative": True,
        },
        {
            "title": "Display duplicate patient warning for matching name and DOB",
            "test_type": "Negative",
            "preconditions": common_preconditions + ["An existing patient record has the same First Name, Last Name, and DOB."],
            "steps": [
                "Login as clinic staff user.",
                "Navigate to Patient Registration.",
                "Enter First Name, Last Name, and DOB matching an existing patient.",
                "Enter Gender, Phone, and Address.",
                "Select Save patient record.",
                "Review the duplicate patient warning.",
                "Select Continue Anyway only when the workflow explicitly allows override.",
            ],
            "expected_result": (
                "The system detects the matching First Name, Last Name, and DOB before final save and displays a duplicate "
                "patient warning with enough matching details for review. If Continue Anyway is selected, the new patient is "
                "saved only after confirmation and the audit trail records the duplicate warning and override decision."
            ),
            "objective": "Verify duplicate patient detection, warning, optional override, and auditability.",
            "risk": "Duplicate patient records may fragment clinical history or cause scheduling and billing errors.",
            "coverage_reason": "Covers healthcare duplicate-patient rule and confirmation behavior.",
            "test_data": {"duplicateMatchFields": ["First Name", "Last Name", "DOB"], "overrideAction": "Continue Anyway"},
            "negative": True,
        },
        {
            "title": "Show eligibility timeout warning and prevent unsafe continuation",
            "test_type": "Integration",
            "preconditions": common_preconditions + ["Eligibility service is configured to timeout or be unavailable."],
            "steps": [
                "Login as clinic staff user.",
                "Navigate to Patient Registration.",
                "Enter complete valid patient demographic details.",
                "Save patient record.",
                "Run eligibility verification.",
                "Wait until the eligibility service timeout condition is reached.",
                "Attempt to continue to appointment scheduling.",
            ],
            "expected_result": (
                "Eligibility status is shown as Unavailable or Timeout with a user-facing warning. The system does not show "
                "Active eligibility, does not silently continue as eligible, and requires the configured confirmation or retry "
                "path before scheduling can proceed. The timeout response is captured in operational logs without exposing sensitive data."
            ),
            "objective": "Verify safe behavior when eligibility verification is unavailable or times out.",
            "risk": "Scheduling may proceed using unknown eligibility, causing clinical or billing downstream issues.",
            "coverage_reason": "Covers eligibility unavailable/timeout behavior and warning requirements.",
            "test_data": {"eligibilityServiceResponse": "Timeout", "expectedStatus": "Unavailable"},
            "negative": True,
        },
        {
            "title": "Prevent appointment save when provider or location is missing",
            "test_type": "Negative",
            "preconditions": common_preconditions + ["A valid patient record exists with eligibility verified."],
            "steps": [
                "Login as clinic staff user.",
                "Navigate to Scheduler for the registered patient.",
                "Select appointment type and future date/time.",
                "Leave Provider blank.",
                "Leave Location blank.",
                "Select Save appointment.",
            ],
            "expected_result": (
                "Appointment is not saved. The scheduler displays validation messages for Provider and Location, keeps the selected "
                "date/time and appointment type available for correction, and does not create appointment, notification, or audit "
                "creation records until required scheduling fields are completed."
            ),
            "objective": "Verify appointment provider/location validation before schedule persistence.",
            "risk": "Appointments without provider or location cannot be fulfilled operationally.",
            "coverage_reason": "Covers appointment creation/update validation and required scheduling fields.",
            "test_data": {"provider": "", "location": "", "dateTime": "Future available slot"},
            "negative": True,
        },
        {
            "title": "Handle downstream API failure during patient or appointment save",
            "test_type": "Integration",
            "preconditions": common_preconditions + ["Downstream patient or scheduling API is configured to return a controlled failure."],
            "steps": [
                "Login as clinic staff user.",
                "Navigate to Patient Registration.",
                "Enter complete valid patient demographic details.",
                "Save patient record while the downstream API returns an error.",
                "If patient save succeeds, navigate to Scheduler and save a valid appointment while scheduling API returns an error.",
                "Review user-facing message and persisted records.",
            ],
            "expected_result": (
                "The system displays a clear failure message identifying that the save could not be completed and does not create "
                "partial duplicate patient or appointment records. Retry or recovery guidance is presented where configured, "
                "and technical API details are captured only in logs/audit entries appropriate for support review."
            ),
            "objective": "Verify controlled failure handling for downstream patient or scheduling API errors.",
            "risk": "API failures may create duplicate, partial, or inconsistent healthcare workflow data.",
            "coverage_reason": "Covers integration/API failure handling, user warning, and data consistency.",
            "test_data": {"apiResponse": "HTTP 500 or controlled connector error", "retryPolicy": "Configured retry/recovery path"},
            "negative": True,
        },
        {
            "title": "Verify audit trail after patient and appointment creation",
            "test_type": "Audit",
            "preconditions": common_preconditions + ["Audit history viewer or audit export is available to authorized user."],
            "steps": [
                "Login as clinic staff user.",
                "Create a new patient with complete demographic details.",
                "Run eligibility verification and confirm Active status.",
                "Create an appointment with provider, location, future date/time, and appointment type.",
                "Login as an authorized audit reviewer.",
                "Open audit history for the patient and appointment records.",
            ],
            "expected_result": (
                "Audit history contains separate entries for patient creation, eligibility verification, and appointment creation. "
                "Each entry includes timestamp, acting user, action name, record identifier, and outcome. Unauthorized users cannot "
                "view audit details, and audit records do not expose secrets or raw authorization headers."
            ),
            "objective": "Verify auditability and access control for the generated healthcare workflow records.",
            "risk": "Missing audit records may prevent compliance review and root-cause investigation.",
            "coverage_reason": "Covers audit trail, role/access validation, and sensitive-data logging rules.",
            "test_data": {"auditActions": ["Patient Created", "Eligibility Verified", "Appointment Created"]},
            "negative": False,
        },
        {
            "title": "Regression check for existing patient search and appointment reschedule",
            "test_type": "Regression",
            "preconditions": common_preconditions + ["Existing patient search and appointment reschedule regression data is available."],
            "steps": [
                "Login as clinic staff user.",
                "Search for an existing patient by name and DOB.",
                "Open the existing patient profile.",
                "Navigate to Scheduler.",
                "Reschedule an existing appointment to another valid provider, location, date/time, and appointment type.",
                "Save the rescheduled appointment.",
            ],
            "expected_result": (
                "Existing patient search returns the correct patient without duplicate creation. Appointment reschedule saves the new "
                "provider, location, date/time, and appointment type while retaining prior appointment history. Confirmation is shown, "
                "and audit history records the reschedule event without changing unrelated patient demographics."
            ),
            "objective": "Verify existing patient and scheduling behavior remains correct after the new requirement.",
            "risk": "New registration changes may regress patient search or appointment rescheduling workflows.",
            "coverage_reason": "Covers regression impact on adjacent patient and scheduler workflows.",
            "test_data": {"existingPatient": "Patient with scheduled appointment", "newSlot": "Different valid future slot"},
            "negative": False,
        },
    ]

    if "performance" in " ".join(focus).casefold() or "response" in _clean_text(payload.acceptanceCriteria, "").casefold():
        scenarios.append(
            {
                "title": "Verify patient save response time remains within expected limit",
                "test_type": "Performance",
                "preconditions": common_preconditions + ["Performance timing capture is enabled."],
                "steps": [
                    "Login as clinic staff user.",
                    "Navigate to Patient Registration.",
                    "Enter complete valid patient demographic details.",
                    "Start response-time capture.",
                    "Save patient record.",
                    "Stop response-time capture when confirmation message is displayed.",
                ],
                "expected_result": (
                    "Patient save confirmation is displayed within the response-time threshold defined by the signed-off acceptance "
                    "criteria. The patient record is persisted once, no duplicate save occurs from repeated clicks, and timing evidence "
                    "is available for test reporting."
                ),
                "objective": "Verify response-time expectation for patient save where the requirement defines performance behavior.",
                "risk": "Slow response or repeated save attempts may create poor user experience or duplicate records.",
                "coverage_reason": "Covers performance expectation from acceptance criteria.",
                "test_data": {"responseTimeThreshold": "Use threshold from signed-off acceptance criteria"},
                "negative": False,
            }
        )

    output = []
    for index, spec in enumerate(scenarios, start=1):
        test_type = spec["test_type"]
        output.append(
            _build_scenario(
                index=index,
                title=spec["title"],
                priority=_priority_for(risk_level, index, test_type),
                test_type=test_type,
                preconditions=spec["preconditions"],
                steps=spec["steps"],
                expected_result=spec["expected_result"],
                objective=spec["objective"],
                risk=spec["risk"],
                traceability=traceability_base,
                test_data=spec["test_data"],
                coverage_reason=spec["coverage_reason"],
                automation_candidate=test_type not in {"Performance"},
                negative_scenario=bool(spec["negative"]),
                requirement_title=requirement_title,
            )
        )

    # Keep the constructed LLM input live so fallback remains signature-compatible with LLM generation.
    _ = llm_payload
    return output


def _get_uipath_chat_model() -> Any:
    from uipath_langchain.chat.chat_model_factory import get_chat_model

    return get_chat_model(
        model="gpt-5.4",
        temperature=0.0,
        max_tokens=LLM_MAX_TOKENS,
        agenthub_config="agentsruntime",
    )


def _build_scenario_generation_prompt(llm_payload: dict[str, Any]) -> str:
    output_shape = {
        "testScenarios": [
            {
                "scenarioId": "TS-001",
                "scenarioTitle": "...",
                "id": "TS-001",
                "testCaseId": "TS-001",
                "title": "...",
                "objective": "...",
                "priority": "High",
                "type": "Functional",
                "testType": "Functional",
                "risk": "...",
                "traceability": {
                    "requirementId": "...",
                    "acceptanceCriteria": [],
                    "coverage": "...",
                },
                "preconditions": [],
                "testData": {},
                "steps": [],
                "expectedResult": "...",
                "coverageReason": "...",
                "automationCandidate": True,
                "negativeScenario": False,
            }
        ]
    }
    signed_off_requirement = llm_payload.get("signedOffRequirement", {})
    qa_lead_review = llm_payload.get("qaLeadReview", {})
    retrieved_rag_context = llm_payload.get("retrievedRagContext", {})
    concise_payload = {
        "requirementId": _clean_text(llm_payload.get("requirementId"), ""),
        "requirementTitle": _clean_text(signed_off_requirement.get("requirementTitle"), "")[:300],
        "requirementDescription": _clean_text(signed_off_requirement.get("requirementDescription"), "")[:800],
        "acceptanceCriteria": signed_off_requirement.get("acceptanceCriteria", ""),
        "qaLeadReviewFeedbackText": _clean_text(
            qa_lead_review.get("feedbackText")
            or qa_lead_review.get("comments")
            or qa_lead_review.get("reviewComments"),
            "",
        )[:600],
        "suggestedTestFocus": signed_off_requirement.get("suggestedTestFocus", []),
        "retrievedRagContext": {
            "ragContextText": _clean_text(retrieved_rag_context.get("ragContextText"), "")[:MAX_RAG_CONTEXT_CHARS],
        },
    }
    return (
        "Return JSON only. Do not include markdown, commentary, or code fences.\n"
        "Generate strict JSON matching this exact top-level shape:\n"
        f"{json.dumps(output_shape, ensure_ascii=True, indent=2)}\n\n"
        "Generation rules:\n"
        f"- Generate exactly {MAX_SCENARIOS_FOR_LLM} test scenarios only.\n"
        "- Required scenarios in order: 1. Happy path patient registration and appointment creation; "
        "2. Mandatory patient demographic validation; 3. Duplicate patient validation; "
        "4. Eligibility inactive/unavailable/timeout handling; 5. Appointment provider/location/date validation; "
        "6. Audit trail and regression validation.\n"
        "- Use the retrieved local RAG context.\n"
        "- Do not generate generic expected results.\n"
        "- Expected result must mention specific observable behavior: validation message, warning, confirmation, "
        "saved data/status, eligibility result, appointment result, audit event, API timeout/failure handling, "
        "or blocked/allowed behavior.\n"
        "- Keep JSON concise. Scenario-level expectedResult must be maximum 2 sentences.\n"
        f"- Each test case must have maximum 3 preconditions and maximum {MAX_STEPS_PER_SCENARIO} steps.\n"
        "- Each step string must include both 'Action:' and 'Expected result:'.\n"
        "- Keep objective, risk, and coverageReason to one short sentence each.\n"
        "- Titles must be scenario-specific and must not contain duplicate words such as 'Validate Validate'.\n"
        "- Include traceability to requirementId and acceptanceCriteria.\n"
        "- If acceptanceCriteria is missing, generate only when QA Lead approved and set traceability.coverage to "
        "signed-off requirement context.\n\n"
        "Concise input payload for generation:\n"
        f"{json.dumps(concise_payload, ensure_ascii=True, indent=2)}"
    )


def _extract_json_object(value: Any) -> dict[str, Any]:
    text = value.content if hasattr(value, "content") else value
    if isinstance(text, list):
        text = "".join(
            item.get("text", "") if isinstance(item, dict) else str(item)
            for item in text
        )
    if not isinstance(text, str):
        text = str(text)

    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped, flags=re.IGNORECASE)
        stripped = re.sub(r"\s*```$", "", stripped).strip()

    try:
        from langchain_core.output_parsers import JsonOutputParser

        parsed = JsonOutputParser().parse(stripped)
    except Exception:
        parsed = json.loads(stripped)

    if isinstance(parsed, dict):
        return parsed
    raise ValueError("LLM response JSON root must be an object.")


def _as_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [_clean_text(item, "") for item in value if _clean_text(item, "")]
    if isinstance(value, str) and value.strip():
        return _clean_list(value)
    return []


def _normalize_priority(value: Any) -> Literal["High", "Medium", "Low"]:
    normalized = _clean_text(value, "Medium").casefold()
    if normalized == "high":
        return "High"
    if normalized == "low":
        return "Low"
    return "Medium"


def _limit_sentences(value: str, max_sentences: int = 3) -> str:
    sentences = re.split(r"(?<=[.!?])\s+", value.strip())
    limited = " ".join(sentence.strip() for sentence in sentences[:max_sentences] if sentence.strip())
    return limited or value


def _limit_text(value: str, max_chars: int = 220) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    return text if len(text) <= max_chars else text[: max_chars - 3].rstrip() + "..."


def _normalize_llm_steps(value: Any) -> list[str]:
    steps = _as_string_list(value)[:MAX_STEPS_PER_SCENARIO]
    normalized = []
    for step in steps:
        if "action:" in step.casefold() and "expected result:" in step.casefold():
            normalized.append(step)
        else:
            normalized.append(f"Action: {step} Expected result: The system shows the configured result for this step.")
    return normalized


def _normalize_llm_scenario(
    raw_scenario: dict[str, Any],
    index: int,
    payload: RequirementPayload,
) -> dict[str, Any]:
    scenario_id = _clean_text(
        raw_scenario.get("scenarioId") or raw_scenario.get("id") or raw_scenario.get("testCaseId"),
        f"TS-{index:03d}",
    )
    title = _normalize_title(
        _clean_text(raw_scenario.get("title") or raw_scenario.get("scenarioTitle"), f"Test scenario {index}"),
        _clean_text(payload.requirementTitle, ""),
    )
    test_type = _clean_text(raw_scenario.get("testType") or raw_scenario.get("type"), "Functional")
    expected_result = _limit_sentences(_clean_text(raw_scenario.get("expectedResult"), ""), 2)
    if not expected_result:
        raise ValueError(f"LLM scenario {scenario_id} is missing expectedResult.")
    if any(pattern in expected_result.casefold() for pattern in GENERIC_EXPECTED_RESULT_PATTERNS):
        raise ValueError(f"LLM scenario {scenario_id} has a generic expectedResult.")

    traceability = raw_scenario.get("traceability")
    if not isinstance(traceability, dict):
        traceability = {}
    criteria = _acceptance_criteria_list(payload)
    traceability.setdefault("requirementId", _clean_text(payload.requirementId, "N/A"))
    traceability["acceptanceCriteria"] = _as_string_list(traceability.get("acceptanceCriteria")) or criteria
    traceability.setdefault(
        "coverage",
        "Signed-off requirement context" if not criteria else "Signed-off acceptance criteria",
    )

    test_data = raw_scenario.get("testData")
    if not isinstance(test_data, dict):
        test_data = {}

    scenario = {
        "scenarioId": scenario_id,
        "scenarioTitle": _normalize_title(
            _clean_text(raw_scenario.get("scenarioTitle") or title, title),
            _clean_text(payload.requirementTitle, ""),
        ),
        "id": _clean_text(raw_scenario.get("id") or scenario_id, scenario_id),
        "testCaseId": _clean_text(raw_scenario.get("testCaseId") or scenario_id, scenario_id),
        "title": title,
        "objective": _limit_text(_clean_text(raw_scenario.get("objective"), title)),
        "priority": _normalize_priority(raw_scenario.get("priority")),
        "type": _clean_text(raw_scenario.get("type") or test_type, test_type),
        "testType": test_type,
        "risk": _limit_text(_clean_text(raw_scenario.get("risk"), "Requirement behavior may not be validated correctly.")),
        "traceability": traceability,
        "preconditions": _as_string_list(raw_scenario.get("preconditions"))[:3],
        "testData": test_data,
        "steps": _normalize_llm_steps(raw_scenario.get("steps")),
        "expectedResult": expected_result,
        "coverageReason": _limit_text(
            _clean_text(
                raw_scenario.get("coverageReason"),
                "Covers signed-off requirement and retrieved RAG guidance.",
            )
        ),
        "automationCandidate": bool(raw_scenario.get("automationCandidate", True)),
        "negativeScenario": bool(raw_scenario.get("negativeScenario", False)),
    }
    return TestScenario.model_validate(scenario).model_dump()


def _validate_llm_scenarios(model_output: dict[str, Any], payload: RequirementPayload) -> list[dict[str, Any]]:
    scenarios = model_output.get("testScenarios")
    if not isinstance(scenarios, list) or not scenarios:
        raise ValueError("LLM response did not include testScenarios.")
    if len(scenarios) != MAX_SCENARIOS_FOR_LLM:
        raise ValueError(f"LLM response must include exactly {MAX_SCENARIOS_FOR_LLM} scenarios.")

    validated = []
    for index, item in enumerate(scenarios, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"LLM scenario {index} must be an object.")
        validated.append(_normalize_llm_scenario(item, index, payload))

    return validated


async def _invoke_llm_with_timeout(prompt: str) -> Any:
    llm = _get_uipath_chat_model()
    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ]
    return await asyncio.wait_for(
        asyncio.to_thread(llm.invoke, messages),
        timeout=LLM_TIMEOUT_SECONDS,
    )


async def _generate_scenarios(payload: RequirementPayload, llm_payload: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        prompt = _build_scenario_generation_prompt(llm_payload)
        print("LLM generation started")
        response = await _invoke_llm_with_timeout(prompt)
        scenarios = _validate_llm_scenarios(_extract_json_object(response), payload)
        llm_payload["_generationMode"] = "llm_rag"
        llm_payload["_llmGenerationUsed"] = True
        print("LLM generation completed", {"scenarioCount": len(scenarios)})
        return scenarios
    except asyncio.TimeoutError:
        print("LLM generation timed out; using deterministic fallback")
        llm_payload["_generationMode"] = "deterministic_fallback"
        llm_payload["_llmGenerationUsed"] = False
        return _generate_fallback_scenarios(payload, llm_payload)
    except Exception:
        print("LLM scenario generation failed; using deterministic fallback")
        llm_payload["_generationMode"] = "deterministic_fallback"
        llm_payload["_llmGenerationUsed"] = False
        return _generate_fallback_scenarios(payload, llm_payload)


async def generate_test_scenarios(state: GraphState) -> dict[str, Any]:
    print("Test generation started")
    question = state.get("question")
    if not question or not isinstance(question, str):
        return {
            "generationStatus": "Failed",
            "testScenarios": [],
            "generationMode": "deterministic_fallback",
            "llmGenerationUsed": False,
        }

    try:
        raw_payload = json.loads(question)
        if not isinstance(raw_payload, dict):
            return {
                "generationStatus": "Failed",
                "testScenarios": [],
                "generationMode": "deterministic_fallback",
                "llmGenerationUsed": False,
            }

        payload = RequirementPayload.model_validate(raw_payload)
    except (json.JSONDecodeError, ValueError, TypeError):
        return {
            "generationStatus": "Failed",
            "testScenarios": [],
            "generationMode": "deterministic_fallback",
            "llmGenerationUsed": False,
        }

    print("RAG retrieval started")
    rag_context = retrieve_test_generation_rag_context(raw_payload)
    print(
        "RAG retrieval completed",
        {
            "retrievalMode": _clean_text(rag_context.get("retrievalMode"), ""),
            "ragContextLength": len(_clean_text(rag_context.get("ragContextText"), "")),
        },
    )
    llm_payload = _build_llm_input_payload(raw_payload, rag_context)
    blocked, missing_information, blocked_reason = _is_generation_blocked(raw_payload, payload)
    retrieved_rag_context = {
        "ragContextText": rag_context.get("ragContextText", ""),
        "ragSourcesUsed": rag_context.get("ragSourcesUsed", []),
    }
    rag_source_names = _rag_source_names(rag_context.get("ragSourcesUsed", []))
    vector_rag_status = _clean_text(rag_context.get("vectorRagStatus"), "Failed")
    vector_chunks_returned = int(rag_context.get("vectorChunksReturned", rag_context.get("chunkCount", 0)) or 0)
    vector_queries_tried = [str(query)[:800] for query in rag_context.get("vectorQueriesTried", []) if str(query).strip()]
    fallback_rag_used = bool(rag_context.get("fallbackRagUsed", False))

    if blocked:
        return {
            "generationStatus": "Blocked",
            "testScenarios": [],
            "generationMode": "",
            "llmGenerationUsed": False,
            "ragSourcesUsed": rag_source_names,
            "retrievedRagContext": retrieved_rag_context,
            "vectorRagStatus": vector_rag_status,
            "vectorChunksReturned": vector_chunks_returned,
            "vectorQueriesTried": vector_queries_tried,
            "fallbackRagUsed": fallback_rag_used,
            "missingInformation": missing_information,
            "blockedReason": blocked_reason,
        }

    test_scenarios = await _generate_scenarios(payload, llm_payload)
    generation_mode = _clean_text(llm_payload.get("_generationMode"), "deterministic_fallback")
    print(
        "Test generation completed",
        {"generationMode": generation_mode, "scenarioCount": len(test_scenarios)},
    )
    return {
        "generationStatus": "Completed",
        "testScenarios": test_scenarios,
        "generationMode": generation_mode,
        "llmGenerationUsed": bool(llm_payload.get("_llmGenerationUsed", False)),
        "ragSourcesUsed": rag_source_names,
        "retrievedRagContext": retrieved_rag_context,
        "vectorRagStatus": vector_rag_status,
        "vectorChunksReturned": vector_chunks_returned,
        "vectorQueriesTried": vector_queries_tried,
        "fallbackRagUsed": fallback_rag_used,
        "missingInformation": [],
        "blockedReason": "",
    }


builder = StateGraph(GraphState, input_schema=AgentInput, output_schema=AgentOutput)
builder.add_node("generate_test_scenarios", generate_test_scenarios)
builder.add_edge(START, "generate_test_scenarios")
builder.add_edge("generate_test_scenarios", END)

graph = builder.compile()
