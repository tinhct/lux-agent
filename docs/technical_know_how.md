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

## 3. Tool Execution Sequence (Local vs. Cloud)

When the Gemini model decides to execute a skill, the framework routes the call dynamically based on the active profile:

```mermaid
sequenceDiagram
    autonumber
    actor User as Researcher Portal
    participant Node as LLM Agent Node
    participant ADK as ADK Framework
    participant MCP as Local MCP Server
    participant Native as Native Python Tool
    participant API as External Service

    User->>Node: Input Keyword
    Node->>ADK: Issue Tool Call JSON (fetch_amazon_brands)
    
    alt Local Mode (settings.use_mcp == True)
        ADK->>MCP: JSON-RPC over stdio
        MCP->>API: HTTP GET suggestions
        API-->>MCP: Raw Suggestions JSON
        MCP-->>ADK: Parse & format results
    else Production Mode (settings.use_mcp == False)
        ADK->>Native: Call python function directly
        Native->>API: HTTP GET suggestions
        API-->>Native: Raw Suggestions JSON
        Native-->>ADK: Validate schema & map fields
    end

    ADK->>Node: Return formatted tool output
    Node->>User: Yield final report predictions
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
