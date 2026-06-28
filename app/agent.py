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

class RateLimitException(Exception):
    pass


class APIAuthenticationError(Exception):
    pass


class TransientServerError(Exception):
    pass


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

from app.core.config import get_settings, load_settings, Settings
from app.core.persistence import get_audit_repository

from app.core.validation import validate_keyword
from app.tools.amazon_brands import (
    fetch_amazon_brands,
    RateLimitException,
    APIAuthenticationError,
    TransientServerError,
)
from app.tools.dma_rag import query_dma_rag


# Tools are resolved dynamically inside the create_workflow factory function


class SuggestionItem(BaseModel):
    value: str = Field(description="The suggested search term")
    brand_type: str = Field(
        description="Classification of the brand: 'house_brand' or 'third_party'"
    )


@node
def validate_prompt_node(ctx: Context, node_input: Any) -> Any:
    """Entry point node that extracts the target keyword and runs validation.
    This runs before any LLM agents or tool calls are triggered.
    """
    import re

    # Extract raw text prompt from input
    prompt = ""
    if isinstance(node_input, str):
        prompt = node_input
    elif hasattr(node_input, "parts") and node_input.parts:
        prompt = "".join(part.text for part in node_input.parts if part.text)
    elif isinstance(node_input, dict):
        prompt = node_input.get("message", "")
        if not prompt and "keyword" in node_input:
            prompt = node_input["keyword"]

    # Extract keyword from common phrases like "Please audit the keyword: Kindle"
    match = re.search(
        r"(?i)(?:audit the keyword|keyword|audit)\s*[:=]?\s*['\"]?([\w\s\-\'.:@#%^*+=;<>{}|[\]\\/]+)['\"]?",
        prompt,
    )
    if match:
        keyword = match.group(1).strip()
    else:
        # Fallback to cleaning the whole prompt as the keyword
        keyword = prompt.strip()

    # Validate
    validate_keyword(keyword)

    return node_input


class APIInspectorOutput(BaseModel):
    keyword: str = Field(description="The keyword queried")
    raw_results: list[SuggestionItem] = Field(
        description="List of brand suggestions returned by the API"
    )
    error_log: str | None = Field(default=None, description="Any error or exception details from the API inspector")
    status_code: int | None = Field(default=200, description="The HTTP status code returned by the API")


# api_inspector node instantiated dynamically inside create_workflow


from app.core.security import sanitize_text


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


# regulatory_analyst node instantiated dynamically inside create_workflow


from app.core.security import scrub_and_detect


@node
def security_checkpoint_node(ctx: Context, node_input: dict):
    """Checks for prompt-injection attacks and scrubs PII from the receipts."""
    redacted_categories = set()
    scrubbed_payload, is_injection = scrub_and_detect(node_input, redacted_categories)

    redacted_list = list(redacted_categories)

    # Check for RateLimitException or APIAuthenticationError
    error_log_val = str(scrubbed_payload.get("error_log", "")) if scrubbed_payload.get("error_log") else ""
    
    if "RateLimitException" in error_log_val:
        flagged_report = {
            "title": "RATE LIMIT AUDIT ALERT: API Rate Limited",
            "extracted_receipts_summary": "Audit paused due to strict API rate limiting. Manual IP rotation or cooling period required.",
            "dma_compliance_mapping": "BLOCKED BY RATE LIMIT EXCEPTION.",
            "risk_assessment": "HIGH RISK: Incomplete audit due to rate limit.",
            "security_event": False,
            "rate_limit_event": True,
        }
        event = Event(output=flagged_report)
        event.actions.route = "security_flagged"
        event.actions.state_delta = {
            "redacted_categories": redacted_list,
            "security_flagged": False,
            "rate_limit_flagged": True,
        }
        yield event
        return

    if "APIAuthenticationError" in error_log_val:
        flagged_report = {
            "title": "AUTHENTICATION AUDIT ALERT: API Authentication Rejected",
            "extracted_receipts_summary": "API authentication rejected. The undocumented suggestion endpoint may have updated its security posture.",
            "dma_compliance_mapping": "BLOCKED BY AUTHENTICATION FAILURE.",
            "risk_assessment": "HIGH RISK: Incomplete audit due to authentication rejection.",
            "security_event": False,
            "auth_event": True,
        }
        event = Event(output=flagged_report)
        event.actions.route = "security_flagged"
        event.actions.state_delta = {
            "redacted_categories": redacted_list,
            "security_flagged": False,
            "auth_flagged": True,
        }
        yield event
        return

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
def hitl_pause_node(ctx: Context, node_input: dict | None = None):
    """Suspends the workflow and pushes the drafted report to the dashboard for review."""
    if node_input is None:
        node_input = {}
    is_security_event = node_input.get("security_event", False)
    is_rate_limit = node_input.get("rate_limit_event", False)
    is_auth_event = node_input.get("auth_event", False)
    redacted_categories = ctx.state.get("redacted_categories", [])
    redacted_info = (
        f"\n**Redacted PII Categories**: {', '.join(redacted_categories)}"
        if redacted_categories
        else ""
    )

    # Check if we have received a resume input for decision
    if not ctx.resume_inputs or "decision" not in ctx.resume_inputs:
        if is_rate_limit:
            message = "Audit paused due to strict API rate limiting. Manual IP rotation or cooling period required."
        elif is_auth_event:
            message = "API authentication rejected. The undocumented suggestion endpoint may have updated its security posture."
        else:
            alert_prefix = (
                "🚨 [SECURITY EVENT FLAGGED] " if is_security_event else "### [DRAFT] "
            )
            title = node_input.get('title', 'Regulatory Audit Error')
            summary = node_input.get('extracted_receipts_summary', 'An unexpected error occurred in the Regulatory Analyst agent.')
            mapping = node_input.get('dma_compliance_mapping', 'No mapping available due to analysis failure.')
            risk = node_input.get('risk_assessment', 'UNKNOWN')
            message = (
                f"{alert_prefix}DMA Audit Report Ready for Review\n\n"
                f"**Title**: {title}\n\n"
                f"**Summary**: {summary}\n\n"
                f"**DMA Mapping**: {mapping}\n\n"
                f"**Risk**: {risk}\n"
                f"{redacted_info}\n\n"
                f"Please review the drafted report and raw receipts. Approve, reject, or annotate with comments."
            )
        yield RequestInput(
            interrupt_id="decision",
            message=message,
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

    settings = get_settings()
    repo = get_audit_repository(settings)
    next_id = repo.get_next_id()

    # Prepare audit record
    audit_record = {
        "id": next_id,
        "timestamp": datetime.datetime.now(ZoneInfo("UTC")).isoformat(),
        "decision": decision,
        "notes": notes,
        "report": report,
        "redacted_categories": ctx.state.get("redacted_categories", []),
        "security_event": report.get("security_event", False),
    }

    # If approved, save to the database
    if decision.lower() in ("approve", "approved", "yes"):
        db_status = repo.append_record(audit_record)
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


def create_workflow(settings: Settings) -> Workflow:
    """Stateless factory to build the agent workflow graph."""
    if settings.use_mcp:
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
            '{"value": "aa batteries", "brand_type": "third_party"}. '
            "If the tool returns an error_log or status_code, you must copy the error_log and status_code "
            "exactly to the output schema fields. "
            "Do NOT output string representations of JSON."
        ),
        tools=api_inspector_tools,
        output_schema=APIInspectorOutput,
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

    return Workflow(
        name="lux_audit_graph",
        edges=[
            Edge(from_node=START, to_node=validate_prompt_node),
            Edge(from_node=validate_prompt_node, to_node=api_inspector_node),
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


def create_app(settings: Settings) -> App:
    """Stateless factory to build the ADK App."""
    wf = create_workflow(settings)
    return App(root_agent=wf, name="app")


# Fallback default app for import-time command line tool auto-discovery
app = create_app(load_settings())
