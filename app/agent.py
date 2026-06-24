# ruff: noqa
# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
import json
import os
import re
from typing import Any
from zoneinfo import ZoneInfo
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.apps import App
from google.adk.models import Gemini
from google.adk.workflow import Workflow, node, Edge, START
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.agents.context import Context
from google.adk.tools.mcp_tool import StdioConnectionParams, McpToolset
from mcp import StdioServerParameters
from google.genai import types
from pydantic import BaseModel, Field

# Load local environment configuration from .env
load_dotenv()

# Setup defaults if not explicitly set in the environment
if not os.environ.get("GEMINI_API_KEY"):
    import google.auth

    try:
        _, project_id = google.auth.default()
        if project_id:
            os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
    except Exception:
        pass
    os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
    os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")


def validate_keyword(keyword: Any) -> str:
    """Validates and sanitizes a keyword input for fetch_amazon_brands.
    Raises ValueError with a clear user-facing explanation if validation fails.
    Returns the cleaned (trimmed and normalized) keyword string.
    """
    import re

    if not isinstance(keyword, str):
        raise ValueError("Keyword must be a string.")

    # Whitespace Trimming & Normalization
    cleaned = keyword.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if not cleaned:
        raise ValueError("Keyword cannot be empty.")

    # Length Boundaries
    if len(cleaned) < 2:
        raise ValueError("Keyword is too short (minimum length is 2 characters).")
    if len(cleaned) > 50:
        raise ValueError("Keyword is too long (maximum length is 50 characters).")

    # Security: Illegal Character Rejection
    illegal_chars = ["<", ">", "{", "}", "[", "]", "\\", "/", ";", "=", "*"]
    for char in illegal_chars:
        if char in cleaned:
            raise ValueError(f"Keyword contains illegal character: '{char}'")

    # Security: Anti-Prompt Injection Signatures
    injection_patterns = ["ignore", "instructions", "system prompt", "bypass", "print"]
    cleaned_lower = cleaned.lower()
    for pattern in injection_patterns:
        if pattern in cleaned_lower:
            raise ValueError(f"Keyword contains blocked word signature: '{pattern}'")

    # Domain: ASIN Rejection (10-character alphanumeric starting with B0)
    if re.match(r"(?i)^B0[A-Z0-9]{8}$", cleaned):
        raise ValueError("ASINs (Amazon Standard Identification Numbers) are not allowed as search keywords.")

    # Domain: URL Rejection (containing http, www, or .com)
    url_patterns = ["http", "www", ".com"]
    for pattern in url_patterns:
        if pattern in cleaned_lower:
            raise ValueError("URLs/links are not allowed as search keywords.")

    # Ethical: PII Block (email, phone, SSN)
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    phone_regex = r"\+?\d[\d\-\s\(\)]{8,}\d"
    ssn_regex = r"\d{3}-\d{2}-\d{4}"

    if re.search(email_regex, cleaned):
        raise ValueError("Input contains a pattern formatted like an email address (blocked for PII protection).")
    if re.search(ssn_regex, cleaned):
        raise ValueError("Input contains a pattern formatted like a Social Security Number (blocked for PII protection).")
    if re.search(phone_regex, cleaned):
        raise ValueError("Input contains a pattern formatted like a phone number (blocked for PII protection).")

    # Ethical: NSFW / Harmful Content Filter (Basic blocklist)
    harmful_terms = [
        "porn", "nsfw", "xxx", "sex", "drugs", "weapons", "bomb", "kill", "suicide", "gamble"
    ]
    for term in harmful_terms:
        if term in cleaned_lower:
            raise ValueError(f"Keyword contains restricted term: '{term}'")

    # Security: Character Allowlist (catch-all at the end)
    if not re.match(r"^[\w\s\-\']+$", cleaned):
        raise ValueError("Keyword contains invalid characters. Only alphanumeric, spaces, hyphens, and apostrophes are allowed.")

    return cleaned


def fetch_amazon_brands(keyword: str) -> dict[str, Any]:
    """Queries Amazon's undocumented search suggestion API to extract structured data on private-label brands.

    Args:
        keyword: The search keyword (e.g. 'batteries', 'spicy') to query.

    Returns:
        A dictionary containing the search keyword and brand classification results.
    """
    import requests

    try:
        keyword = validate_keyword(keyword)
    except ValueError as e:
        return {
            "keyword": keyword,
            "error": f"Validation failed: {e}",
            "suggestions": [],
        }

    if keyword == "mock_payload":
        result = {
            "keyword": "mock_payload",
            "suggestions": [
                {"value": "amazon basics batteries", "brand_type": "house_brand"},
                {"value": "energizer aa batteries", "brand_type": "third_party"},
            ],
        }
        return result

    url = "https://completion.amazon.com/api/2017/suggestions"
    params = {
        "mid": "ATVPDKIKX0DER",
        "alias": "aps",
        "prefix": keyword,
        "suggestion-type": "keyword",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        suggestions = []
        for item in data.get("suggestions", []):
            value = item.get("value", "")
            if (
                "amazon" in value.lower()
                or "basics" in value.lower()
                or "solimo" in value.lower()
                or "presto" in value.lower()
            ):
                brand_type = "house_brand"
            else:
                brand_type = "third_party"

            suggestions.append({"value": value, "brand_type": brand_type})

        result = {"keyword": keyword, "suggestions": suggestions}
        return result

    except Exception as e:
        error_result = {
            "keyword": keyword,
            "error": f"Failed to fetch suggestions from Amazon API: {e}",
            "suggestions": [],
        }
        return error_result


def query_dma_rag(query: str) -> dict[str, Any]:
    """Searches indexed Digital Markets Act (DMA) documents via a simulated vector search endpoint.

    Args:
        query: The semantic search query or regulatory concept (e.g. 'self-preferencing', 'Article 6(5)') to look up.

    Returns:
        A dictionary containing the list of matching document chunks, including sources and relevance.
    """
    import os
    
    project_id = os.environ.get("VERTEX_AI_SEARCH_PROJECT_ID")
    location = os.environ.get("VERTEX_AI_SEARCH_LOCATION", "global")
    data_store_id = os.environ.get("VERTEX_AI_SEARCH_DATA_STORE_ID")
    
    def get_simulated_chunks(q: str):
        q_lower = q.lower()
        chunks = []
        if "prefer" in q_lower or "rank" in q_lower:
            chunks.append({
                "content": "Under the DMA, self-preferencing occurs when a gatekeeper treats its own services or products more favorably in ranking and related indexing and crawling than similar third-party services.",
                "source": "Digital Markets Act, Article 6, Paragraph 5",
                "relevance": 0.95
            })
        if "search" in q_lower or "core platform" in q_lower:
            chunks.append({
                "content": "Online search engines are defined as 'core platform services' subject to gatekeeper obligations if they meet the quantitative thresholds.",
                "source": "Digital Markets Act, Article 2, Paragraph 2(b)",
                "relevance": 0.90
            })
        if "gdpr" in q_lower or "article 5" in q_lower or "prejudice" in q_lower:
            chunks.append({
                "content": "This is without prejudice to obligations under Regulation (EU) 2016/679 (GDPR). Under DMA Article 5(2), gatekeepers face specific restrictions, though the text notes this is without prejudice to the GDPR.",
                "source": "Digital Markets Act, Article 5, Paragraph 2",
                "relevance": 0.88
            })
        if "gatekeeper" in q_lower or "threshold" in q_lower:
            chunks.append({
                "content": "A provider of core platform services shall be designated as a gatekeeper if it has a significant impact on the internal market, operates a core platform service which serves as an important gateway for business users to reach end users, and enjoys an established and durable position.",
                "source": "Digital Markets Act, Article 3, Paragraph 1",
                "relevance": 0.85
            })
        return chunks

    if not all([project_id, data_store_id]):
        chunks = get_simulated_chunks(query)
        if not chunks:
            return {
                "status": "no_match",
                "message": f"No relevant definitions or restrictions matching '{query}' were found in the indexed DMA documentation. The system cannot perform a compliance mapping for this specific query.",
                "chunks": []
            }
        return {
            "status": "success",
            "chunks": chunks
        }

    try:
        from google.cloud import discoveryengine_v1 as discoveryengine
        
        client = discoveryengine.SearchServiceClient()
        serving_config = (
            f"projects/{project_id}/locations/{location}"
            f"/collections/default_collection/dataStores/{data_store_id}"
            f"/servingConfigs/default_search"
        )

        extractive_spec = discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
            max_extractive_segment_count=3,
            return_extractive_segment_score=True,
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                extractive_content_spec=extractive_spec,
            ),
        )

        response = client.search(request)
        chunks = []

        for result in response.results:
            doc_data = result.document.derived_struct_data
            segments = doc_data.get("extractive_segments", [])
            title = doc_data.get("title", "Digital Markets Act")
            
            for segment in segments:
                chunks.append({
                    "content": segment.get("content", ""),
                    "source": f"{title}, Segment {segment.get('pageNumber', 'N/A')}",
                    "relevance": segment.get("relevanceScore", 0.0),
                })

        if not chunks:
            return {
                "status": "no_match",
                "message": f"No relevant definitions or restrictions matching '{query}' were found in the indexed DMA documentation.",
                "chunks": []
            }

        chunks.sort(key=lambda x: x["relevance"], reverse=True)
        return {
            "status": "success",
            "chunks": chunks[:5]
        }

    except Exception as e:
        simulated_chunks = get_simulated_chunks(query)
        if simulated_chunks:
            return {
                "status": "success",
                "warning": f"Vertex AI Search failed ({e}). Fell back to simulated local database.",
                "chunks": simulated_chunks
            }
        return {
            "status": "error",
            "message": f"Vertex AI Search failed and no local fallback matches were found: {str(e)}",
            "chunks": []
        }


# Determine tools to use based on environment (local with MCP vs. cloud Agent Runtime)
mcp_server_dir = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "mcp_server")
)
if os.path.exists(mcp_server_dir):
    mcp_toolset = McpToolset(
        connection_params=StdioConnectionParams(
            server_params=StdioServerParameters(
                command="uv",
                args=[
                    "run",
                    "--project",
                    "mcp_server",
                    "python",
                    "mcp_server/server.py",
                ],
            )
        )
    )
    api_inspector_tools = [mcp_toolset]
    regulatory_analyst_tools = [mcp_toolset]
else:
    api_inspector_tools = [fetch_amazon_brands]
    regulatory_analyst_tools = [query_dma_rag]


class SuggestionItem(BaseModel):
    value: str = Field(description="The suggested search term")
    brand_type: str = Field(
        description="Classification of the brand: 'house_brand' or 'third_party'"
    )


class APIInspectorOutput(BaseModel):
    keyword: str = Field(description="The keyword queried")
    raw_results: list[SuggestionItem] = Field(
        description="List of brand suggestions returned by the API"
    )


api_inspector_node = LlmAgent(
    name="api_inspector",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the API Inspector agent. Your sole responsibility is to fetch search suggestions "
        "and private-label brand data for the given keyword query. You must execute this retrieval "
        "strictly through the fetch_amazon_brands tool. "
        "Format the suggestions extracted from the tool exactly according to the output schema. "
        "You must map the suggestions list to the raw_results list as structured JSON objects (not JSON strings), "
        "where each object has 'value' and 'brand_type' as direct keys. For example: "
        '{"value": "aa batteries", "brand_type": "third_party"}. Do NOT output string representations of JSON.'
    ),
    tools=api_inspector_tools,
    output_schema=APIInspectorOutput,
)


def sanitize_text(val: Any) -> Any:
    """Helper to clean HTML tags and potential code signatures recursively."""
    if isinstance(val, str):
        # Strip HTML tags
        sanitized = re.sub(r"<[^>]*>", "", val)
        # Strip common script/code signatures to block prompt injection
        sanitized = re.sub(r"(?i)javascript:|script:|eval\(|exec\(", "", sanitized)
        # Limit individual string length
        return sanitized[:500]
    elif isinstance(val, dict):
        return {k: sanitize_text(v) for k, v in val.items()}
    elif isinstance(val, list):
        return [sanitize_text(item) for item in val]
    return val


@node
def defense_middleware_node(node_input: dict) -> dict:
    """Prompt-injection defense middleware that sanitizes payload and limits token length."""
    # 1. Sanitize payload recursively
    sanitized_payload = sanitize_text(node_input)

    # 2. Enforce maximum token length (character-based ceiling for context window)
    serialized = json.dumps(sanitized_payload)
    max_char_len = 4000  # Approx 1000 tokens limit

    if len(serialized) > max_char_len:
        if "raw_results" in sanitized_payload and isinstance(
            sanitized_payload["raw_results"], list
        ):
            truncated_results = []
            current_len = len(
                json.dumps(
                    {k: v for k, v in sanitized_payload.items() if k != "raw_results"}
                )
            )
            for item in sanitized_payload["raw_results"]:
                item_len = len(json.dumps(item))
                if current_len + item_len + 5 > max_char_len:
                    break
                truncated_results.append(item)
                current_len += item_len + 5
            sanitized_payload["raw_results"] = truncated_results
            sanitized_payload["truncated_by_middleware"] = True

    return sanitized_payload


class RegulatoryReport(BaseModel):
    title: str = Field(description="Title of the regulatory audit report")
    extracted_receipts_summary: str = Field(
        description="Summary of the raw receipts collected by API Inspector"
    )
    dma_compliance_mapping: str = Field(
        description="Detailed mapping of the receipts to DMA articles and potential non-compliance findings"
    )
    risk_assessment: str = Field(
        description="Overall risk level (High, Medium, Low) with explanation"
    )


regulatory_analyst_node = LlmAgent(
    name="regulatory_analyst",
    model=Gemini(
        model="gemini-flash-latest",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a Regulatory Analyst specializing in the Digital Markets Act (DMA). "
        "Your task is to analyze the raw receipts (JSON data) provided in the input, "
        "summarize the findings, map them to relevant DMA articles, and provide an overall risk assessment.\n\n"
        "Crucially, you must cross-reference findings and query definitions of terms (such as self-preferencing or core platform services) "
        "strictly by calling the query_dma_rag tool, ensuring this execution routes through the local Model Context Protocol (MCP) container. "
        "Do not extrapolate or rely on external or pre-trained knowledge of EU antitrust regulation; use only direct quotes from the retrieved chunks. "
        "Cite the specific Article and Paragraph for every legal claim. "
        "Always append the mandatory disclaimer at the end of the report: "
        "'***Disclaimer: This analysis is generated via automated regulatory mapping for research purposes only. It does not constitute binding legal counsel, and findings must be verified by a qualified human legal professional.***'"
    ),
    tools=regulatory_analyst_tools,
    output_schema=RegulatoryReport,
)


def scrub_and_detect(val: Any, redacted_categories: set[str]) -> tuple[Any, bool]:
    """Helper to scrub sensitive PII and identify prompt injection attacks."""
    is_injection = False
    if isinstance(val, str):
        # 1. Scrub SSNs: XXX-XX-XXXX
        ssn_pattern = r"\b\d{3}-\d{2}-\d{4}\b"
        if re.search(ssn_pattern, val):
            redacted_categories.add("SSN")
            val = re.sub(ssn_pattern, "[REDACTED_SSN]", val)

        # 2. Scrub Credit Cards: 13-16 digits with optional dashes/spaces
        cc_pattern = r"\b(?:\d[ -]*?){13,16}\b"
        if re.search(cc_pattern, val):
            redacted_categories.add("Credit Card")
            val = re.sub(cc_pattern, "[REDACTED_CC]", val)

        # 3. Detect Prompt Injection Attempts
        injection_keywords = [
            "ignore previous",
            "ignore instructions",
            "system prompt",
            "developer mode",
            "override rules",
            "bypass rules",
            "auto-approve",
            "force approve",
            "always approve",
            "ignore compliance",
            "bypass compliance",
        ]
        val_lower = val.lower()
        if any(keyword in val_lower for keyword in injection_keywords):
            is_injection = True

        return val, is_injection

    elif isinstance(val, dict):
        new_dict = {}
        for k, v in val.items():
            scrubbed_v, inj = scrub_and_detect(v, redacted_categories)
            if inj:
                is_injection = True
            new_dict[k] = scrubbed_v
        return new_dict, is_injection

    elif isinstance(val, list):
        new_list = []
        for item in val:
            scrubbed_item, inj = scrub_and_detect(item, redacted_categories)
            if inj:
                is_injection = True
            new_list.append(scrubbed_item)
        return new_list, is_injection

    return val, is_injection


@node
def security_checkpoint_node(ctx: Context, node_input: dict):
    """Checks for prompt-injection attacks and scrubs PII from the receipts."""
    redacted_categories = set()
    scrubbed_payload, is_injection = scrub_and_detect(node_input, redacted_categories)

    redacted_list = list(redacted_categories)

    if is_injection:
        # Prompt injection detected: bypass LLM, flag as security event, route directly to HITL pause
        flagged_report = {
            "title": "SECURITY AUDIT ALERT: Prompt Injection Attempt Blocked",
            "extracted_receipts_summary": f"SECURITY EVENT FLAGGED. Raw receipts payload: {json.dumps(scrubbed_payload)}",
            "dma_compliance_mapping": "BLOCKED BY SECURITY CHECKPOINT. Malicious override patterns detected.",
            "risk_assessment": "CRITICAL RISK: Potential prompt injection attack.",
            "security_event": True,
        }
        event = Event(output=flagged_report)
        event.actions.route = "security_flagged"
        event.actions.state_delta = {
            "redacted_categories": redacted_list,
            "security_flagged": True,
        }
        yield event
    else:
        # Safe: route to Regulatory Analyst LLM agent
        event = Event(output=scrubbed_payload)
        event.actions.route = "safe"
        event.actions.state_delta = {
            "redacted_categories": redacted_list,
            "security_flagged": False,
        }
        yield event


@node(rerun_on_resume=True)
def hitl_pause_node(ctx: Context, node_input: dict):
    """Suspends the workflow and pushes the drafted report to the dashboard for review."""
    is_security_event = node_input.get("security_event", False)
    redacted_categories = ctx.state.get("redacted_categories", [])
    redacted_info = (
        f"\n**Redacted PII Categories**: {', '.join(redacted_categories)}"
        if redacted_categories
        else ""
    )

    # Check if we have received a resume input for decision
    if not ctx.resume_inputs or "decision" not in ctx.resume_inputs:
        alert_prefix = (
            "🚨 [SECURITY EVENT FLAGGED] " if is_security_event else "### [DRAFT] "
        )
        yield RequestInput(
            interrupt_id="decision",
            message=(
                f"{alert_prefix}DMA Audit Report Ready for Review\n\n"
                f"**Title**: {node_input.get('title')}\n\n"
                f"**Summary**: {node_input.get('extracted_receipts_summary')}\n\n"
                f"**DMA Mapping**: {node_input.get('dma_compliance_mapping')}\n\n"
                f"**Risk**: {node_input.get('risk_assessment')}\n"
                f"{redacted_info}\n\n"
                f"Please review the drafted report and raw receipts. Approve, reject, or annotate with comments."
            ),
        )
        return

    decision_data = ctx.resume_inputs["decision"]
    # Normalize decision input
    if isinstance(decision_data, str):
        action = decision_data
        notes = ""
    elif isinstance(decision_data, dict):
        action = decision_data.get("action", "approve")
        notes = decision_data.get("notes", "")
    else:
        action = "approve"
        notes = ""

    yield Event(output={"decision": action, "notes": notes, "report": node_input})


@node
def finalize_report_node(ctx: Context, node_input: dict):
    """Finalizes the report, saving approved reports to the database."""
    decision = node_input["decision"]
    notes = node_input["notes"]
    report = node_input["report"]

    db_path = "audit_db.json"

    # Read existing database or create new
    if os.path.exists(db_path):
        try:
            with open(db_path, "r") as f:
                db = json.load(f)
        except Exception:
            db = []
    else:
        db = []

    # Prepare audit record
    audit_record = {
        "id": len(db) + 1,
        "timestamp": datetime.datetime.now(ZoneInfo("UTC")).isoformat(),
        "decision": decision,
        "notes": notes,
        "report": report,
        "redacted_categories": ctx.state.get("redacted_categories", []),
        "security_event": report.get("security_event", False),
    }

    # If approved, save to the database
    if decision.lower() in ("approve", "approved", "yes"):
        db.append(audit_record)
        try:
            with open(db_path, "w") as f:
                json.dump(db, f, indent=2)
            db_status = "Saved to Database successfully."
        except Exception as e:
            db_status = f"Failed to save to database: {e}"

        status_text = "Approved"
    else:
        db_status = "Rejection logged. Report was not saved to the active database."
        status_text = "Rejected"

    final_msg = (
        f"### Audit Finalization Complete\n\n"
        f"**Decision**: {status_text}\n"
        f"**Notes/Annotations**: {notes if notes else 'None'}\n"
        f"**Database Status**: {db_status}\n\n"
        f"Thank you for completing the audit review."
    )

    yield Event(
        content=types.Content(
            role="model", parts=[types.Part.from_text(text=final_msg)]
        )
    )
    yield Event(output=audit_record)


root_agent = Workflow(
    name="lux_audit_graph",
    edges=[
        Edge(from_node=START, to_node=api_inspector_node),
        Edge(from_node=api_inspector_node, to_node=defense_middleware_node),
        Edge(from_node=defense_middleware_node, to_node=security_checkpoint_node),
        Edge(
            from_node=security_checkpoint_node,
            to_node=regulatory_analyst_node,
            route="safe",
        ),
        Edge(
            from_node=security_checkpoint_node,
            to_node=hitl_pause_node,
            route="security_flagged",
        ),
        Edge(from_node=regulatory_analyst_node, to_node=hitl_pause_node),
        Edge(from_node=hitl_pause_node, to_node=finalize_report_node),
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
