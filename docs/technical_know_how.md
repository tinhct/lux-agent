# Technical Know-How: Agent Nodes & Skills Orchestration

This guide describes the technical connection, reference resources, execution routing, and architectural data flows between **Agent Nodes** and **Skills (Tools)** within the LUX workflow.

---

## 1. Architectural Concepts

In the Google ADK (Agent Development Kit) framework, the workflow is defined as a directed graph where work is distributed between code-based nodes, model-based agents, and local/remote reference files:

*   **Workflow Node (`@node`)**: A stateless Python function that mutates state or routes control flow (e.g., input validation, security screening).
*   **LLM Agent Node (`LlmAgent`)**: A model-driven node (Gemini) that receives system instructions and uses natural language reasoning to solve a task.
*   **Agent Skill/Tool (`McpTool` / native function)**: Extends the capabilities of an LLM agent by allowing it to execute deterministic actions (e.g., calling APIs, querying databases, running semantic search).
*   **Reference Resources (`references/`)**: Markdown guides, JSON schemas, or text corpora packaged within the skills folder. They serve as authoritative sources of truth for compliance checks, API schemas, and citation standards.

---

## 2. Structural Binding & Reference Resource Diagram

The following diagram illustrates how the workflow, LLM agents, tools, and their respective reference resources are bound together at runtime:

```mermaid
graph TD
    subgraph ADK_Workflow ["ADK Graph Workflow (create_workflow)"]
        START[START Node] --> VAL[validate_prompt_node]
        VAL --> API_NODE[api_inspector LlmAgent Node]
        API_NODE --> DEFENSE[defense_middleware_node]
        DEFENSE --> REG_NODE[regulatory_analyst LlmAgent Node]
    end

    subgraph API_Inspector_Context ["API Inspector Scope"]
        API_NODE_INSTRUCTIONS["System Instructions"]
        SKILL_API_INSTRUCTIONS["fetch_amazon_brands/SKILL.md"]
        
        subgraph API_References ["Reference Resources"]
            API_SCHEMA["references/amazon_api_schema.md<br/>(Retry limits, Error codes, Backoffs)"]
        end
    end

    subgraph Regulatory_Analyst_Context ["Regulatory Analyst Scope"]
        REG_NODE_INSTRUCTIONS["System Instructions"]
        SKILL_RAG_INSTRUCTIONS["query_dma_rag/SKILL.md"]
        
        subgraph RAG_References ["Reference Resources"]
            CITATION_GUIDE["references/citation_rules.md<br/>(Article mapping & legal quotes)"]
        end
    end

    API_NODE -.->|Context Binding| API_Inspector_Context
    SKILL_API_INSTRUCTIONS -.->|Governed by| API_SCHEMA
    
    REG_NODE -.->|Context Binding| Regulatory_Analyst_Context
    SKILL_RAG_INSTRUCTIONS -.->|Cites via| CITATION_GUIDE
```

---

## 3. Tool Execution Sequences

### A. Local Mode Sequence (Development & Local Testing)
In local development, the entry point is the local playground UI or terminal CLI. Tool calls route securely via JSON-RPC to the local MCP server running as a subprocess:

```mermaid
sequenceDiagram
    autonumber
    actor User as Developer (Local Playground UI)
    participant ADK as Local ADK Graph Runtime
    participant MCP as Local MCP Server (Subprocess)
    participant API as External Service (Amazon / Mock Search)

    User->>ADK: 1. Inputs keyword (e.g. Kindle)
    ADK->>ADK: 2. Runs validate & defense nodes
    ADK->>MCP: 3. Sends tool call JSON-RPC over stdio (fetch_amazon_brands)
    MCP->>API: 4. Executes HTTP suggestion request
    API-->>MCP: 5. Returns suggestion payload JSON
    MCP-->>ADK: 6. Returns structured results
    ADK->>User: 7. Renders output in local playground
```

### B. Production Mode Sequence (Deployed Cloud Environment)
In production, the entry point is the user-facing Researcher Portal. The portal initiates a session, and the deployed Vertex AI Reasoning Engine executes the graph nodes and calls tools directly as native Python functions:

```mermaid
sequenceDiagram
    autonumber
    actor User as Researcher (Web Portal Dashboard)
    participant Portal as Researcher Portal Service
    participant Engine as Vertex AI Reasoning Engine (Agent Runtime)
    participant Tool as Native Python Tool (amazon_brands.py / dma_rag.py)
    participant API as External Service (Amazon API / Vertex RAG Search)

    User->>Portal: 1. Inputs keyword
    Portal->>Engine: 2. Starts/Resumes Session (VertexAiSessionService)
    Engine->>Engine: 3. Runs graph validation & defense nodes
    Engine->>Tool: 4. Invokes Python function directly
    Tool->>API: 5. Sends API request (HTTPS suggestions / Discovery Engine client)
    API-->>Tool: 6. Returns results payload
    Tool-->>Engine: 7. Returns validated python dict
    Engine-->>Portal: 8. Streams workflow events & audit records
    Portal->>User: 9. Displays finalized compliance report
```

---

## 4. Key Architectural Connection Points

### A. Context Injection
When the graph executes an `LlmAgent` node:
1. The framework reads the agent's core `instruction`.
2. It fetches instructions from the configured `.agents/skills/<skill_name>/SKILL.md` file.
3. It merges these instructions and appends them to the system prompt of the Gemini model. This ensures the model understands **when** and **how** to invoke the corresponding tool.

### B. Tool Schema Binding
During workflow setup (inside `create_workflow(settings)` in [app/agent.py](file:///Users/tinhct/Documents/AI%20PM%20Knowledge/5%20Day%20AI%20Agents%20/capstone-project/lux-agent/app/agent.py)):
*   If `settings.use_mcp` is active, the agent is bound to `McpToolset`. The tool signatures are discovered dynamically from the MCP server.
*   If `use_mcp` is inactive, the agent is bound to standard Python functions (`fetch_amazon_brands`, `query_dma_rag`). The Python function's docstring and type hints serve as the tool schema exposed to Gemini.

### C. Reference Resource Integration
Reference resources play two distinct roles in the connection lifecycle:
*   **Static Reference (Design time / Agent System Instructions)**: 
    *   Files like `references/amazon_api_schema.md` define exact compliance schemas (e.g., retries on 429 backoffs, authentication cookies cleansing). The tool code (`amazon_brands.py`) imports and implements these rules deterministically.
*   **Dynamic Reference (Runtime Context)**:
    *   Files inside the RAG `references/` directory govern how the `regulatory_analyst_node` outputs its results. The model reads the legal citation guidelines at execution time to format direct quotes and append the required legal disclaimers.
