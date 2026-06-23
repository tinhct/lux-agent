import json
import logging
import os
from typing import Any

import vertexai
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from google.adk.sessions.vertex_ai_session_service import VertexAiSessionService
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("lux_researcher_portal")

app = FastAPI(
    title="LUX Researcher Portal",
    description="Standalone dashboard for gatekeeper compliance audits and approval workflows",
)

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Retrieve configuration from environment variables with fallbacks
PROJECT_ID = os.environ.get("GOOGLE_CLOUD_PROJECT")
LOCATION = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
AGENT_RUNTIME_ID = os.environ.get("AGENT_RUNTIME_ID")

# Fallback to local deployment_metadata.json if variables are not in env
if not PROJECT_ID or not AGENT_RUNTIME_ID:
    meta_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
    )
    if os.path.exists(meta_path):
        try:
            with open(meta_path) as f:
                meta = json.load(f)
                if not PROJECT_ID:
                    PROJECT_ID = "gen-lang-client-0096535740"
                if not AGENT_RUNTIME_ID:
                    AGENT_RUNTIME_ID = meta.get("remote_agent_runtime_id")
                logger.info(
                    f"Loaded config from metadata: project={PROJECT_ID}, runtime={AGENT_RUNTIME_ID}"
                )
        except Exception as e:
            logger.warning(f"Failed to read deployment_metadata.json: {e}")

# Apply final defaults if still unconfigured
if not PROJECT_ID:
    PROJECT_ID = "gen-lang-client-0096535740"
if not AGENT_RUNTIME_ID:
    AGENT_RUNTIME_ID = "projects/204996083024/locations/us-central1/reasoningEngines/3573666227702202368"

logger.info(
    f"LUX Dashboard active: Project={PROJECT_ID}, Location={LOCATION}, AgentRuntimeID={AGENT_RUNTIME_ID}"
)

# Extract numeric ID if AGENT_RUNTIME_ID is a full resource name path
agent_engine_id = AGENT_RUNTIME_ID
if agent_engine_id and "/" in agent_engine_id:
    agent_engine_id = agent_engine_id.split("/")[-1]

# Instantiate ADK Session Service
session_service = VertexAiSessionService(
    project=PROJECT_ID, location=LOCATION, agent_engine_id=agent_engine_id
)


# Models
class AuditRequest(BaseModel):
    keyword: str = Field(description="The search term to audit")


class ActionRequest(BaseModel):
    action: str = Field(description="Action to perform: 'approve' or 'reject'")
    interruptId: str = Field(description="The ID of the interrupt/request_input state")
    notes: str = Field(default="", description="Annotations or feedback comments")


def query_remote_agent(engine, message: Any, session_id: str) -> Any:
    """Helper to query the remote reasoning engine using the execution client directly,
    bypassing the client-side method binding issue.
    """
    import json

    from google.cloud.aiplatform_v1beta1.types import (
        reasoning_engine_execution_service as aip_types,
    )

    response_stream = engine.execution_api_client.stream_query_reasoning_engine(
        request=aip_types.StreamQueryReasoningEngineRequest(
            name=engine.resource_name,
            input={
                "message": message,
                "user_id": "default-user",
                "session_id": session_id,
            },
            class_method="stream_query",
        )
    )

    last_output = None
    for chunk in response_stream:
        if getattr(chunk, "data", None):
            try:
                utf8_data = chunk.data.decode("utf-8")
                for line in utf8_data.split("\n"):
                    if line:
                        last_output = json.loads(line)
            except Exception:
                pass
    return last_output


# Endpoints
@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    """Serves the premium, responsive Manager Dashboard HTML page."""
    html_content = """<!DOCTYPE html>
<html lang="en" class="h-full">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>LUX Researcher Portal</title>
    <!-- Fonts -->
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&family=Inter:wght@300;400;500;600&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
    <!-- Tailwind CSS -->
    <script src="https://cdn.tailwindcss.com"></script>
    <!-- Marked JS for Markdown parsing -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        body {
            font-family: 'Outfit', 'Inter', sans-serif;
            background-color: #030712;
        }
        /* Custom Glowing & Glassmorphism styles */
        .glow-bg {
            position: relative;
            background-color: #030712;
            overflow: hidden;
        }
        @keyframes pulseGlow {
            0%, 100% { opacity: 0.6; transform: scale(1) translate(0, 0); }
            50% { opacity: 0.9; transform: scale(1.1) translate(20px, -20px); }
        }
        .glow-bg::before {
            content: '';
            position: absolute;
            top: -200px;
            left: 20%;
            width: 700px;
            height: 700px;
            background: radial-gradient(circle, rgba(59, 130, 246, 0.12) 0%, transparent 70%);
            filter: blur(100px);
            z-index: 0;
            animation: pulseGlow 12s infinite alternate ease-in-out;
            pointer-events: none;
        }
        .glow-bg::after {
            content: '';
            position: absolute;
            bottom: -200px;
            right: 15%;
            width: 600px;
            height: 600px;
            background: radial-gradient(circle, rgba(99, 102, 241, 0.08) 0%, transparent 70%);
            filter: blur(80px);
            z-index: 0;
            animation: pulseGlow 16s infinite alternate-reverse ease-in-out;
            pointer-events: none;
        }
        .cyber-grid {
            background-image: linear-gradient(rgba(255, 255, 255, 0.015) 1px, transparent 1px),
                              linear-gradient(90deg, rgba(255, 255, 255, 0.015) 1px, transparent 1px);
            background-size: 30px 30px;
        }
        .glass-panel {
            background: rgba(10, 15, 30, 0.55);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.4);
        }
        .glass-card {
            background: rgba(255, 255, 255, 0.02);
            backdrop-filter: blur(10px);
            -webkit-backdrop-filter: blur(10px);
            border: 1px solid rgba(255, 255, 255, 0.05);
            transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
        }
        .glass-card:hover {
            background: rgba(255, 255, 255, 0.04);
            border-color: rgba(255, 255, 255, 0.08);
            transform: translateY(-2px);
        }
        /* Markdown style customization */
        .markdown-body h1 {
            font-size: 1.5rem;
            font-weight: 700;
            color: #ffffff;
            margin-top: 1.5rem;
            margin-bottom: 0.75rem;
        }
        .markdown-body h2 {
            font-size: 1.35rem;
            font-weight: 600;
            color: #f8fafc;
            margin-top: 1.35rem;
            margin-bottom: 0.6rem;
        }
        .markdown-body h3 {
            font-size: 1.15rem;
            font-weight: 600;
            color: #60a5fa;
            margin-top: 1.25rem;
            margin-bottom: 0.5rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.08);
            padding-bottom: 0.25rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        .markdown-body p {
            margin-bottom: 0.85rem;
            font-size: 0.95rem;
            line-height: 1.6;
            color: #cbd5e1;
        }
        .markdown-body ul {
            list-style-type: disc;
            padding-left: 1.25rem;
            margin-bottom: 0.85rem;
            color: #cbd5e1;
        }
        .markdown-body li {
            margin-bottom: 0.35rem;
            line-height: 1.5;
        }
        .markdown-body strong {
            color: #ffffff;
            font-weight: 600;
        }
        .markdown-body code {
            background: rgba(255, 255, 255, 0.06);
            color: #f472b6;
            padding: 0.15rem 0.3rem;
            border-radius: 0.25rem;
            font-family: 'Fira Code', monospace;
            font-size: 0.85em;
        }
        .markdown-body pre {
            background: rgba(10, 10, 18, 0.6);
            border: 1px solid rgba(255, 255, 255, 0.06);
            padding: 1rem;
            border-radius: 0.75rem;
            margin: 1rem 0;
            overflow-x: auto;
        }
        .markdown-body pre code {
            background: transparent;
            color: #e2e8f0;
            padding: 0;
            font-size: 0.9em;
        }
        .markdown-body table {
            width: 100%;
            margin-top: 1.25rem;
            margin-bottom: 1.25rem;
            border-collapse: collapse;
            font-size: 0.875rem;
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 0.5rem;
            overflow: hidden;
        }
        .markdown-body th {
            background: rgba(99, 102, 241, 0.08);
            font-weight: 600;
            padding: 0.6rem 0.85rem;
            text-align: left;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
            color: #94a3b8;
        }
        .markdown-body td {
            padding: 0.6rem 0.85rem;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            color: #e2e8f0;
        }
        .markdown-body tr:last-child td {
            border-bottom: none;
        }
        .markdown-body blockquote {
            border-left: 4px solid #6366f1;
            background: rgba(99, 102, 241, 0.04);
            padding: 0.85rem 1.15rem;
            margin: 1.25rem 0;
            border-radius: 0 0.75rem 0.75rem 0;
            color: #94a3b8;
        }
        /* Custom scrollbar */
        ::-webkit-scrollbar {
            width: 6px;
            height: 6px;
        }
        ::-webkit-scrollbar-track {
            background: rgba(255, 255, 255, 0.01);
        }
        ::-webkit-scrollbar-thumb {
            background: rgba(255, 255, 255, 0.15);
            border-radius: 3px;
        }
        ::-webkit-scrollbar-thumb:hover {
            background: rgba(255, 255, 255, 0.25);
        }
    </style>
</head>
<body class="h-full text-slate-100 glow-bg cyber-grid overflow-hidden flex flex-col">

    <!-- Loading Overlay (Subtle translucent screen-wide blur for action execution) -->
    <div id="loading-overlay" style="opacity: 0;" class="fixed inset-0 bg-slate-950/80 backdrop-blur-md z-50 flex flex-col items-center justify-center space-y-4 transition-all duration-300 hidden">
        <div class="relative w-16 h-16 flex items-center justify-center">
            <!-- Glowing background pulse -->
            <div class="absolute inset-0 bg-blue-500/20 rounded-full blur-xl animate-pulse"></div>
            <!-- Spinner -->
            <div class="w-12 h-12 border-[3px] border-blue-500/30 border-t-blue-500 rounded-full animate-spin"></div>
        </div>
        <div class="text-center space-y-1">
            <h3 class="text-lg font-semibold tracking-tight text-slate-100" id="loading-title">Running Compliance Audit</h3>
            <p class="text-xs text-slate-400 max-w-xs px-4" id="loading-desc">Invoking ADK agent graph on Vertex AI Runtime... This may take up to 30 seconds.</p>
        </div>
    </div>

    <!-- Top Header Section -->
    <header class="flex-none glass-panel border-b border-slate-800/80 px-6 py-4 flex flex-col md:flex-row md:items-center md:justify-between space-y-4 md:space-y-0 z-10 shadow-lg shadow-black/30">
        <!-- Logo and Title -->
        <div class="flex items-center space-x-3.5">
            <div class="w-10 h-10 rounded-xl bg-gradient-to-tr from-blue-600 via-indigo-600 to-violet-500 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30 border border-blue-400/20 relative group">
                <span class="absolute inset-0 rounded-xl bg-indigo-400/25 blur-sm opacity-50 group-hover:opacity-100 transition-opacity"></span>
                <span class="relative">L</span>
            </div>
            <div>
                <div class="flex items-center space-x-2">
                    <h1 class="text-lg font-bold tracking-tight bg-gradient-to-r from-white via-slate-100 to-slate-400 bg-clip-text text-transparent">LUX Researcher Portal</h1>
                    <!-- Connection Status Badge -->
                    <span id="runtime-status-badge" class="inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                        <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1 animate-pulse"></span>
                        Live
                    </span>
                </div>
                <p class="text-[11px] text-slate-400 uppercase tracking-widest font-medium">DMA Search Compliance Engine</p>
            </div>
        </div>

        <!-- Keyword Submission Form -->
        <div class="flex items-center space-x-0.5 flex-grow max-w-lg md:mx-8 relative">
            <div class="absolute inset-0 bg-blue-500/5 rounded-xl blur-md"></div>
            <input type="text" id="keyword-input" placeholder="Enter keyword (e.g. Kindle, AA batteries)" class="relative flex-grow bg-slate-950/70 border border-slate-800/80 rounded-l-xl px-4 py-2.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/70 hover:border-slate-700 transition-all placeholder:text-slate-600">
            <button onclick="runAudit()" id="btn-run-audit" class="relative bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white rounded-r-xl px-6 py-2.5 text-sm font-semibold tracking-wide transition-all shadow-md shadow-blue-500/10 active:scale-95 flex items-center space-x-2">
                <span>Run Audit</span>
            </button>
        </div>

        <!-- Session Selector (Resume workflow functionality) -->
        <div class="flex items-center space-x-3">
            <div class="flex flex-col">
                <span class="text-[9px] uppercase tracking-wider text-slate-500 mb-0.5 font-bold">Unresolved States</span>
                <select id="session-select" onchange="loadSelectedSession()" class="bg-slate-950/70 border border-slate-800 text-slate-300 rounded-lg px-3 py-1.5 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500/20 w-52 hover:border-slate-700 transition-all cursor-pointer">
                    <option value="">-- Load Pending Session --</option>
                </select>
            </div>
            <button onclick="fetchPendingSessions()" id="btn-refresh" class="p-2.5 mt-4 rounded-lg bg-white/5 border border-white/10 hover:bg-white/10 text-slate-300 hover:text-white transition-all flex items-center justify-center hover:scale-105 active:scale-95" title="Refresh Pending Sessions">
                <svg id="refresh-icon" class="w-4 h-4 transition-transform duration-500" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 1121.21 8H18.5M7 21h10a2 2 0 002-2V9a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2z"></path></svg>
            </button>
        </div>
    </header>

    <!-- Workspace Container: Split Screen View -->
    <main class="flex-grow flex flex-col min-h-0 min-w-0 bg-slate-950/40">
        <!-- Split Panel Area -->
        <div class="flex-grow flex min-h-0 min-w-0">
            <!-- Left Panel: Raw JSON receipts -->
            <div class="w-1/2 border-r border-slate-800/60 p-6 flex flex-col min-h-0">
                <div class="flex items-center justify-between mb-3 flex-none">
                    <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400">Raw JSON Receipts (API Inspector)</span>
                    <button onclick="copyRawJson()" id="btn-copy-json" class="text-xs text-blue-400 hover:text-blue-300 font-medium transition-all hover:scale-102 flex items-center space-x-1" disabled>
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path></svg>
                        <span>Copy JSON</span>
                    </button>
                </div>
                <div class="flex-grow glass-panel rounded-2xl p-5 overflow-y-auto font-mono text-xs whitespace-pre-wrap select-all selection:bg-blue-950/80 shadow-inner flex flex-col transition-all duration-300" id="raw-json-panel">
                    <div class="h-full flex flex-col items-center justify-center text-slate-500 font-sans text-center px-4 space-y-4">
                        <div class="w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center border border-blue-500/20 text-blue-400 shadow-lg shadow-blue-500/5">
                            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                        </div>
                        <div class="space-y-1 max-w-xs">
                            <h4 class="text-sm font-semibold text-slate-300">Raw JSON Receipts</h4>
                            <p class="text-xs text-slate-500 leading-relaxed">Submit a query or load a pending session to view the extracted API search suggestions payload.</p>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Panel: Compliance Markdown Report -->
            <div class="w-1/2 p-6 flex flex-col min-h-0">
                <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-3 flex-none">AI-Drafted Compliance Report (Regulatory Analyst)</span>
                <div class="flex-grow glass-panel rounded-2xl p-6 overflow-y-auto markdown-body text-slate-200 shadow-inner flex flex-col transition-all duration-300" id="markdown-report-panel">
                    <div class="h-full flex flex-col items-center justify-center text-slate-500 font-sans text-center px-4 space-y-4">
                        <div class="w-16 h-16 rounded-2xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 text-indigo-400 shadow-lg shadow-indigo-500/5">
                            <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                        </div>
                        <div class="space-y-1 max-w-xs">
                            <h4 class="text-sm font-semibold text-slate-300">Compliance Report</h4>
                            <p class="text-xs text-slate-500 leading-relaxed">The regulatory analysis, gatekeeper audits, and decision trees will render here in structured Markdown format.</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Footer / Review Control Section -->
        <div class="p-6 border-t border-slate-800/80 bg-slate-900/20 flex flex-col space-y-4 flex-none z-10 shadow-lg">
            <div class="flex flex-col space-y-1.5">
                <div class="flex items-center justify-between">
                    <label for="review-notes" class="text-xs font-semibold text-slate-400 uppercase tracking-wider">Note / Annotation Rationale</label>
                    <span class="text-[10px] text-slate-500 italic">Captures annotations for database dispatch</span>
                </div>
                <textarea id="review-notes" placeholder="Provide compliance annotations, override justifications, or audit comments..." class="w-full bg-slate-950/50 border border-slate-800/80 rounded-xl p-3.5 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-blue-500/20 focus:border-blue-500/70 transition-all placeholder:text-slate-600 resize-none h-20 disabled:opacity-40 disabled:cursor-not-allowed" disabled></textarea>
            </div>

            <div class="flex items-center justify-between">
                <!-- Selected Session Info -->
                <div class="text-xs text-slate-500 font-mono flex items-center space-x-2" id="workspace-status">
                    <span class="w-1.5 h-1.5 rounded-full bg-slate-700 animate-pulse"></span>
                    <span>Status: Awaiting Audit Keyword</span>
                </div>
                <!-- Action Buttons -->
                <div class="flex items-center space-x-3">
                    <button onclick="submitAction('reject')" id="btn-reject" class="px-5 py-2.5 rounded-xl border border-rose-500/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-300 hover:text-rose-200 font-semibold text-sm transition-all duration-200 flex items-center space-x-2 disabled:opacity-40 disabled:pointer-events-none hover:scale-102 active:scale-98" disabled>
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        <span>Reject & Discard</span>
                    </button>
                    <button onclick="submitAction('approve')" id="btn-approve" class="px-6 py-2.5 rounded-xl bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold text-sm shadow-lg shadow-emerald-950/20 transition-all duration-200 flex items-center space-x-2 disabled:opacity-40 disabled:pointer-events-none hover:scale-102 active:scale-98" disabled>
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
                        <span>Approve & Finalize</span>
                    </button>
                </div>
            </div>
        </div>
    </main>

    <!-- Slide-Out Modal for Final Compliance Review Record -->
    <div id="modal-container" class="fixed inset-0 overflow-hidden z-50 hidden" role="dialog" aria-modal="true">
        <div class="absolute inset-0 overflow-hidden">
            <!-- Backdrop -->
            <div id="modal-backdrop" onclick="closeModal()" class="absolute inset-0 bg-slate-950/65 backdrop-blur-sm transition-opacity duration-300 opacity-0"></div>

            <div class="pointer-events-none fixed inset-y-0 right-0 flex max-w-full pl-10">
                <!-- Slide-over panel -->
                <div id="modal-panel" class="pointer-events-auto w-screen max-w-xl transform transition-transform duration-500 ease-out translate-x-full border-l border-indigo-500/20">
                    <div class="flex h-full flex-col bg-slate-900 shadow-2xl relative">
                        <!-- Top glowing border accent -->
                        <div class="absolute inset-x-0 top-0 h-[2px] bg-gradient-to-r from-blue-500 via-indigo-500 to-teal-400"></div>

                        <!-- Header -->
                        <div class="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between mt-[2px]">
                            <div>
                                <span class="text-xs text-emerald-400 font-mono font-semibold uppercase tracking-wider flex items-center gap-1.5">
                                    <span class="w-2 h-2 rounded-full bg-emerald-400 animate-ping"></span>
                                    AUDIT COMPLETED
                                </span>
                                <h3 class="text-lg font-bold text-slate-100 mt-0.5">Final Compliance Record</h3>
                            </div>
                            <button onclick="closeModal()" class="rounded-lg p-2 hover:bg-white/5 border border-white/5 text-slate-400 hover:text-white transition-all hover:scale-105 active:scale-95 hover:rotate-90 duration-200">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path></svg>
                            </button>
                        </div>

                        <!-- Content -->
                        <div class="flex-grow overflow-y-auto p-6 space-y-6">
                            <!-- Status Panel -->
                            <div class="rounded-xl border border-emerald-500/20 bg-emerald-500/5 p-4 flex items-start space-x-3 shadow-inner">
                                <svg class="w-6 h-6 text-emerald-400 flex-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path></svg>
                                <div>
                                    <h4 class="text-sm font-semibold text-emerald-300">Decision Dispatched to ADK Graph</h4>
                                    <p class="text-xs text-emerald-400/80 mt-0.5 leading-relaxed">The unpaused node was successfully resumed on Agent Runtime. The finalized compliance payload has been recorded.</p>
                                </div>
                            </div>

                            <!-- Final Database JSON Payload -->
                            <div class="space-y-2">
                                <span class="text-xs font-semibold uppercase tracking-wider text-slate-400">Final Session Record Payload</span>
                                <div class="glass-panel rounded-xl p-4 overflow-x-auto font-mono text-xs whitespace-pre-wrap select-all selection:bg-blue-950/80 shadow-inner" id="final-json-payload">
                                    <!-- Populated dynamically -->
                                </div>
                            </div>
                        </div>

                        <!-- Footer -->
                        <div class="px-6 py-4 border-t border-slate-800/80 bg-slate-950/20 flex justify-end">
                            <button onclick="closeModal()" class="px-5 py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-medium transition-all hover:scale-102 active:scale-98 shadow-lg shadow-indigo-600/20">
                                Done
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <!-- Script Section -->
    <script>
        let pendingSessions = [];
        let activeSession = null;

        // Custom Tokyo Night/One Dark JSON Syntax Highlighter
        function syntaxHighlight(json) {
            if (typeof json !== 'string') {
                json = JSON.stringify(json, undefined, 2);
            }
            json = json.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
            return json.replace(/("(\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*"(\\s*:)?|\b(true|false|null)\b|-?\\d+(?:\\.\\d*)?(?:[eE][+-]?\\d+)?)/g, function (match) {
                let cls = 'text-sky-400'; // number
                if (/^"/.test(match)) {
                    if (/:$/.test(match)) {
                        cls = 'text-indigo-400 font-semibold'; // key
                    } else {
                        cls = 'text-emerald-400'; // string
                    }
                } else if (/true|false/.test(match)) {
                    cls = 'text-amber-400 font-semibold'; // boolean
                } else if (/null/.test(match)) {
                    cls = 'text-rose-400 italic'; // null
                }
                return '<span class="' + cls + '">' + match + '</span>';
            });
        }

        // Pulse loading skeletons generator
        function getJsonSkeleton() {
            return `
            <div class="space-y-4 animate-pulse w-full">
                <div class="flex items-center space-x-2">
                    <span class="text-slate-700 font-semibold">{</span>
                </div>
                <div class="pl-4 space-y-3">
                    <div class="flex items-center space-x-2">
                        <div class="h-3.5 bg-slate-800 rounded w-1/4"></div>
                        <span class="text-slate-700">:</span>
                        <div class="h-3.5 bg-slate-800 rounded w-1/2"></div>
                    </div>
                    <div class="flex items-center space-x-2">
                        <div class="h-3.5 bg-slate-800 rounded w-1/3"></div>
                        <span class="text-slate-700">:</span>
                        <div class="h-3.5 bg-slate-800 rounded w-1/4"></div>
                    </div>
                    <div class="flex items-center space-x-2">
                        <div class="h-3.5 bg-slate-800 rounded w-1/5"></div>
                        <span class="text-slate-700">:</span>
                        <div class="h-3.5 bg-slate-800/80 rounded w-3/5"></div>
                    </div>
                    <div class="flex items-center space-x-2">
                        <div class="h-3.5 bg-slate-800 rounded w-1/4"></div>
                        <span class="text-slate-700">:</span>
                        <div class="h-3.5 bg-slate-800 rounded w-1/3"></div>
                    </div>
                    <div class="pl-4 space-y-2 border-l border-slate-800/50">
                        <div class="flex items-center space-x-2">
                            <div class="h-3 bg-slate-800/60 rounded w-1/3"></div>
                            <span class="text-slate-800">:</span>
                            <div class="h-3 bg-slate-800/60 rounded w-1/2"></div>
                        </div>
                        <div class="flex items-center space-x-2">
                            <div class="h-3 bg-slate-800/60 rounded w-1/4"></div>
                            <span class="text-slate-800">:</span>
                            <div class="h-3 bg-slate-800/60 rounded w-1/3"></div>
                        </div>
                    </div>
                </div>
                <div class="flex items-center space-x-2">
                    <span class="text-slate-700 font-semibold">}</span>
                </div>
            </div>`;
        }

        function getMarkdownSkeleton() {
            return `
            <div class="space-y-6 animate-pulse w-full">
                <div class="space-y-2">
                    <div class="h-5 bg-slate-800 rounded w-2/3"></div>
                    <div class="h-3 bg-slate-800/70 rounded w-1/3"></div>
                </div>
                <div class="space-y-3">
                    <div class="h-3.5 bg-slate-800 rounded w-full"></div>
                    <div class="h-3.5 bg-slate-800 rounded w-11/12"></div>
                    <div class="h-3.5 bg-slate-800 rounded w-4/5"></div>
                </div>
                <div class="border-t border-slate-800/60 pt-4 space-y-4">
                    <div class="h-4 bg-slate-800/90 rounded w-1/2"></div>
                    <div class="grid grid-cols-3 gap-4">
                        <div class="h-3 bg-slate-800/60 rounded col-span-1"></div>
                        <div class="h-3 bg-slate-800/60 rounded col-span-2"></div>
                        <div class="h-3 bg-slate-800/60 rounded col-span-2"></div>
                    </div>
                </div>
                <div class="border-t border-slate-800/60 pt-4 space-y-3">
                    <div class="h-4 bg-slate-800/90 rounded w-1/3"></div>
                    <div class="flex items-center space-x-2">
                        <div class="h-3.5 w-3.5 rounded-full bg-slate-800"></div>
                        <div class="h-3 bg-slate-800 rounded w-2/3"></div>
                    </div>
                </div>
            </div>`;
        }

        // Generic helper to change button states to premium loading with spinners
        function setButtonLoading(btnId, isLoading, text) {
            const btn = document.getElementById(btnId);
            if (!btn) return;

            btn.disabled = isLoading;
            if (isLoading) {
                btn.dataset.originalHtml = btn.innerHTML;
                btn.innerHTML = `
                    <svg class="animate-spin -ml-1 mr-2 h-4 w-4 text-current" fill="none" viewBox="0 0 24 24">
                        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
                        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
                    </svg>
                    <span>${text}</span>
                `;
                btn.classList.add('cursor-not-allowed', 'opacity-80');
            } else {
                if (btn.dataset.originalHtml) {
                    btn.innerHTML = btn.dataset.originalHtml;
                }
                btn.classList.remove('cursor-not-allowed', 'opacity-80');
            }
        }

        function showLoading(show, title = "Running Compliance Audit", desc = "Invoking ADK agent graph on Vertex AI Runtime...") {
            const overlay = document.getElementById('loading-overlay');
            if (show) {
                document.getElementById('loading-title').innerText = title;
                document.getElementById('loading-desc').innerText = desc;
                overlay.classList.remove('hidden');
                setTimeout(() => overlay.style.opacity = '1', 50);
            } else {
                overlay.style.opacity = '0';
                setTimeout(() => overlay.classList.add('hidden'), 300);
            }
        }

        function updateBadge(state) {
            const badge = document.getElementById('runtime-status-badge');
            if (!badge) return;

            if (state === 'idle') {
                badge.className = "inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20";
                badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-emerald-400 mr-1 animate-pulse"></span>Live`;
            } else if (state === 'running') {
                badge.className = "inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20";
                badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-blue-400 mr-1 animate-spin"></span>Processing`;
            } else if (state === 'interrupt') {
                badge.className = "inline-flex items-center px-1.5 py-0.5 rounded-full text-[9px] font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20";
                badge.innerHTML = `<span class="w-1.5 h-1.5 rounded-full bg-amber-400 mr-1 animate-ping"></span>Decision Required`;
            }
        }

        async function fetchPendingSessions() {
            const icon = document.getElementById('refresh-icon');
            if (icon) icon.classList.add('rotate-180');

            try {
                const res = await fetch('/api/pending');
                if (!res.ok) throw new Error('Failed to load pending reviews');
                pendingSessions = await res.json();

                const selector = document.getElementById('session-select');
                selector.innerHTML = '<option value="">-- Load Pending Session --</option>';

                pendingSessions.forEach(session => {
                    const option = document.createElement('option');
                    option.value = session.sessionId;
                    const keyword = session.rawReceipts?.keyword || "Generic Query";
                    option.textContent = `Audit: "${keyword}" (${session.sessionId.substring(0, 8)})`;
                    selector.appendChild(option);
                });
            } catch (err) {
                console.error(err);
            } finally {
                if (icon) setTimeout(() => icon.classList.remove('rotate-180'), 500);
            }
        }

        async function loadSelectedSession() {
            const selector = document.getElementById('session-select');
            const sessionId = selector.value;
            if (!sessionId) return;

            const selected = pendingSessions.find(s => s.sessionId === sessionId);
            if (selected) {
                displaySessionData(selected);
            }
        }

        function displaySessionData(data) {
            activeSession = data;

            // Load Raw JSON with syntax highlighting
            const jsonHtml = syntaxHighlight(data.rawReceipts || {});
            document.getElementById('raw-json-panel').innerHTML = `<pre class="font-mono text-[11px] leading-relaxed" style="font-family: 'Fira Code', monospace; color: #cbd5e1;">${jsonHtml}</pre>`;

            // Render Markdown compliance report
            const html = marked.parse(data.reportMarkdown || '');
            document.getElementById('markdown-report-panel').innerHTML = html;

            // Enable review controls
            document.getElementById('review-notes').disabled = false;
            document.getElementById('review-notes').value = '';
            document.getElementById('btn-approve').disabled = false;
            document.getElementById('btn-reject').disabled = false;
            document.getElementById('btn-copy-json').disabled = false;

            // Update status text
            document.getElementById('workspace-status').innerHTML = `
                <span class="w-1.5 h-1.5 rounded-full bg-amber-500 animate-ping"></span>
                <span>Active Session: <b class="text-slate-300 font-medium">${data.sessionId.substring(0, 8)}...</b> | Interrupt: <b class="text-slate-300 font-medium">${data.interruptId}</b></span>
            `;

            updateBadge('interrupt');
        }

        async function runAudit() {
            const keywordInput = document.getElementById('keyword-input');
            const keyword = keywordInput.value.trim();
            if (!keyword) {
                alert('Please enter a keyword query to audit.');
                return;
            }

            // Lock controls
            keywordInput.disabled = true;
            document.getElementById('session-select').disabled = true;
            document.getElementById('btn-refresh').disabled = true;

            // Set button and badge loading status
            setButtonLoading('btn-run-audit', true, 'Auditing...');
            updateBadge('running');

            // Render pulsing skeletons inside panels
            document.getElementById('raw-json-panel').innerHTML = getJsonSkeleton();
            document.getElementById('markdown-report-panel').innerHTML = getMarkdownSkeleton();

            try {
                const res = await fetch('/api/audit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ keyword: keyword })
                });

                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Audit execution failed');
                }

                const data = await res.json();
                displaySessionData({
                    sessionId: data.sessionId,
                    interruptId: data.interruptId,
                    reportMarkdown: data.reportMarkdown,
                    rawReceipts: data.rawReceipts
                });

                // Clear input
                keywordInput.value = '';

                // Refresh list in background
                await fetchPendingSessions();
            } catch (err) {
                console.error(err);
                alert(`Audit Failed: ${err.message}`);

                // Reset views to empty states
                resetWorkspace();
            } finally {
                // Unlock controls
                keywordInput.disabled = false;
                document.getElementById('session-select').disabled = false;
                document.getElementById('btn-refresh').disabled = false;
                setButtonLoading('btn-run-audit', false, 'Run Audit');
            }
        }

        function copyRawJson() {
            const jsonText = document.getElementById('raw-json-panel').textContent;
            navigator.clipboard.writeText(jsonText);

            // Temporary copy success indicator
            const copyBtn = document.getElementById('btn-copy-json');
            const originalHtml = copyBtn.innerHTML;
            copyBtn.innerHTML = `
                <svg class="w-3.5 h-3.5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"></path></svg>
                <span class="text-emerald-400">Copied!</span>
            `;
            setTimeout(() => copyBtn.innerHTML = originalHtml, 2000);
        }

        async function submitAction(action) {
            if (!activeSession) return;

            const notes = document.getElementById('review-notes').value;

            // Disable other action button and set spinner for the active button
            const activeBtnId = action === 'approve' ? 'btn-approve' : 'btn-reject';
            const inactiveBtnId = action === 'approve' ? 'btn-reject' : 'btn-approve';

            document.getElementById(inactiveBtnId).disabled = true;
            document.getElementById('review-notes').disabled = true;
            document.getElementById('session-select').disabled = true;
            document.getElementById('btn-refresh').disabled = true;

            setButtonLoading(activeBtnId, true, action === 'approve' ? 'Approving...' : 'Rejecting...');
            updateBadge('running');

            try {
                const res = await fetch(`/api/action/${activeSession.sessionId}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        action: action,
                        interruptId: activeSession.interruptId,
                        notes: notes
                    })
                });

                if (!res.ok) {
                    const errInfo = await res.json();
                    throw new Error(errInfo.detail || 'Failed to dispatch action');
                }

                const data = await res.json();

                // Show slide-out modal with syntax highlighted JSON
                const finalJsonHtml = syntaxHighlight(data.result || {});
                document.getElementById('final-json-payload').innerHTML = `<pre class="font-mono text-xs leading-relaxed" style="font-family: 'Fira Code', monospace; color: #cbd5e1;">${finalJsonHtml}</pre>`;

                openModal();

                // Clear workspace
                resetWorkspace();

                // Refresh sessions
                await fetchPendingSessions();
            } catch (err) {
                console.error(err);
                alert(`Action Failed: ${err.message}`);

                // Unlock actions on error
                document.getElementById(inactiveBtnId).disabled = false;
                document.getElementById('review-notes').disabled = false;
                document.getElementById('session-select').disabled = false;
                document.getElementById('btn-refresh').disabled = false;
                setButtonLoading(activeBtnId, false, action === 'approve' ? 'Approve & Finalize' : 'Reject & Discard');
                updateBadge('interrupt');
            } finally {
                // Remove loading states from buttons
                if (action === 'approve') {
                    setButtonLoading('btn-approve', false, 'Approve & Finalize');
                } else {
                    setButtonLoading('btn-reject', false, 'Reject & Discard');
                }
            }
        }

        function resetWorkspace() {
            activeSession = null;
            document.getElementById('raw-json-panel').innerHTML = `
                <div class="h-full flex flex-col items-center justify-center text-slate-500 font-sans text-center px-4 space-y-4">
                    <div class="w-16 h-16 rounded-2xl bg-blue-500/10 flex items-center justify-center border border-blue-500/20 text-blue-400 shadow-lg shadow-blue-500/5">
                        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z"></path></svg>
                    </div>
                    <div class="space-y-1 max-w-xs">
                        <h4 class="text-sm font-semibold text-slate-300">Raw JSON Receipts</h4>
                        <p class="text-xs text-slate-500 leading-relaxed">Submit a query or load a pending session to view the extracted API search suggestions payload.</p>
                    </div>
                </div>
            `;
            document.getElementById('markdown-report-panel').innerHTML = `
                <div class="h-full flex flex-col items-center justify-center text-slate-500 font-sans text-center px-4 space-y-4">
                    <div class="w-16 h-16 rounded-2xl bg-indigo-500/10 flex items-center justify-center border border-indigo-500/20 text-indigo-400 shadow-lg shadow-indigo-500/5">
                        <svg class="w-8 h-8" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"></path></svg>
                    </div>
                    <div class="space-y-1 max-w-xs">
                        <h4 class="text-sm font-semibold text-slate-300">Compliance Report</h4>
                        <p class="text-xs text-slate-500 leading-relaxed">The regulatory analysis, gatekeeper audits, and decision trees will render here in structured Markdown format.</p>
                    </div>
                </div>
            `;

            document.getElementById('review-notes').disabled = true;
            document.getElementById('review-notes').value = '';
            document.getElementById('btn-approve').disabled = true;
            document.getElementById('btn-reject').disabled = true;
            document.getElementById('btn-copy-json').disabled = true;

            document.getElementById('workspace-status').innerHTML = `
                <span class="w-1.5 h-1.5 rounded-full bg-slate-700 animate-pulse"></span>
                <span>Status: Awaiting Audit Keyword</span>
            `;
            document.getElementById('session-select').value = '';
            document.getElementById('session-select').disabled = false;
            document.getElementById('btn-refresh').disabled = false;

            updateBadge('idle');
        }

        function openModal() {
            const modal = document.getElementById('modal-container');
            const backdrop = document.getElementById('modal-backdrop');
            const panel = document.getElementById('modal-panel');

            // Set visible layout instantly, transition is driven by classes
            modal.classList.remove('hidden');

            // Force a browser reflow/repaint to ensure transitions animate correctly
            void modal.offsetWidth;

            backdrop.classList.replace('opacity-0', 'opacity-100');
            panel.classList.replace('translate-x-full', 'translate-x-0');
        }

        function closeModal() {
            const backdrop = document.getElementById('modal-backdrop');
            const panel = document.getElementById('modal-panel');

            backdrop.classList.replace('opacity-100', 'opacity-0');
            panel.classList.replace('translate-x-0', 'translate-x-full');

            setTimeout(() => {
                document.getElementById('modal-container').classList.add('hidden');
            }, 500); // match duration-500 ease-out on modal-panel
        }

        // Initialize pending sessions dropdown
        fetchPendingSessions();
    </script>
</body>
</html>
"""
    return HTMLResponse(content=html_content)


@app.post("/api/audit")
async def start_audit(req: AuditRequest):
    """Initializes a new audit session, queries it, and returns the response and session ID."""
    try:
        from vertexai.preview.reasoning_engines import ReasoningEngine

        # Initialize Vertex AI
        vertexai.init(project=PROJECT_ID, location=LOCATION)

        # Create session first using ADK session_service
        logger.info(f"Creating new session on Agent Runtime for keyword: {req.keyword}")
        new_session = await session_service.create_session(
            app_name=agent_engine_id, user_id="default-user"
        )
        session_id = new_session.id

        # Instantiate ReasoningEngine client
        engine = ReasoningEngine(AGENT_RUNTIME_ID)

        # Query remote agent
        message = f"Please audit the keyword: {req.keyword}"
        logger.info(
            f"Sending prompt to remote agent session={session_id} on engine={AGENT_RUNTIME_ID}"
        )
        _ = query_remote_agent(engine, message, session_id)

        # Retrieve the updated session history to parse details
        full_session = await session_service.get_session(
            app_name=agent_engine_id,
            user_id="default-user",
            session_id=session_id,
        )

        # Extract interrupt ID and details
        interrupt_id = None
        report_markdown = ""
        raw_receipts = None

        for event in full_session.events:
            if (
                event.output
                and isinstance(event.output, dict)
                and "raw_results" in event.output
            ):
                raw_receipts = event.output

            if event.content and event.content.parts:
                for part in event.content.parts:
                    if (
                        part.function_call
                        and part.function_call.name == "adk_request_input"
                    ):
                        fc = part.function_call
                        interrupt_id = getattr(fc, "id", None) or (
                            fc.args.get("interrupt_id") if fc.args else None
                        )
                        report_markdown = fc.args.get("message") if fc.args else ""

        return {
            "status": "success",
            "sessionId": session_id,
            "interruptId": interrupt_id,
            "reportMarkdown": report_markdown,
            "rawReceipts": raw_receipts,
        }
    except Exception as e:
        logger.error(f"Error starting audit: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/api/pending", response_model=list[dict])
async def get_pending():
    """Queries the Session Service and history to find unresolved RequestInput states."""
    try:
        # List all sessions associated with the deployed agent
        response = await session_service.list_sessions(app_name=agent_engine_id)
        sessions = response.sessions
        logger.info(f"Retrieved {len(sessions)} active sessions from Agent Runtime")

        pending_items = []
        for s in sessions:
            try:
                # Fetch full event history for the session
                full_session = await session_service.get_session(
                    app_name=agent_engine_id,
                    user_id=s.user_id,
                    session_id=s.id,
                )

                calls = {}  # interrupt_id -> (message, timestamp)
                responses = set()  # completed interrupt_ids
                raw_receipts = None

                # Scan session events
                for event in full_session.events:
                    # Identify raw receipts
                    if (
                        event.output
                        and isinstance(event.output, dict)
                        and "raw_results" in event.output
                    ):
                        raw_receipts = event.output

                    if not event.content or not event.content.parts:
                        continue

                    for part in event.content.parts:
                        # Find RequestInput function call events
                        if (
                            part.function_call
                            and part.function_call.name == "adk_request_input"
                        ):
                            fc = part.function_call
                            interrupt_id = getattr(fc, "id", None) or (
                                fc.args.get("interrupt_id") if fc.args else None
                            )
                            msg = fc.args.get("message") if fc.args else None
                            if interrupt_id:
                                calls[interrupt_id] = (msg, event.timestamp)

                        # Find matching function response events
                        if (
                            part.function_response
                            and part.function_response.name == "adk_request_input"
                        ):
                            fr = part.function_response
                            interrupt_id = getattr(fr, "id", None)
                            if interrupt_id:
                                responses.add(interrupt_id)

                # Check for unresolved interrupts
                for interrupt_id, (msg, ts) in calls.items():
                    if interrupt_id not in responses:
                        pending_items.append(
                            {
                                "sessionId": s.id,
                                "userId": s.user_id,
                                "interruptId": interrupt_id,
                                "reportMarkdown": msg,
                                "rawReceipts": raw_receipts,
                                "timestamp": ts,
                            }
                        )
            except Exception as e:
                logger.error(f"Error fetching details for session {s.id}: {e}")
                continue

        # Sort pending items by newest timestamp first
        pending_items.sort(key=lambda x: x["timestamp"], reverse=True)
        return pending_items
    except Exception as e:
        logger.error(f"Failed to query pending sessions: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.post("/api/action/{session_id}")
async def resume_session(session_id: str, req: ActionRequest):
    """Resumes the suspended workflow node on Agent Runtime."""
    try:
        from vertexai.preview.reasoning_engines import ReasoningEngine

        # Initialize Vertex SDK
        vertexai.init(project=PROJECT_ID, location=LOCATION)

        # Instantiate remote reasoning engine client
        engine = ReasoningEngine(AGENT_RUNTIME_ID)

        approved_bool = req.action.lower() == "approve"

        # Build the exact resume payload as specified
        resume_payload = {
            "role": "user",
            "parts": [
                {
                    "function_response": {
                        "id": req.interruptId,
                        "name": "adk_request_input",
                        "response": {
                            "approved": approved_bool,
                            "action": req.action,
                            "notes": req.notes,
                        },
                    }
                }
            ],
        }

        logger.info(
            f"Resuming session={session_id} on engine={AGENT_RUNTIME_ID} with action={req.action}"
        )

        # Query remote agent and set user_id strictly to "default-user" to avoid ownership issues
        result = query_remote_agent(engine, resume_payload, session_id)

        return {"status": "success", "result": result}
    except Exception as e:
        logger.error(f"Failed to resume session {session_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e)) from e


if __name__ == "__main__":
    import uvicorn

    # Serve locally on port 8081 (to avoid conflict with local playground on 8080)
    uvicorn.run(app, host="0.0.0.0", port=8081)
