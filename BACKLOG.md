# LUX Agent Product Backlog

This document maintains the active product features, descriptions, status, and future backlog items for the **LUX compliance agent**.

---

## Active Product Features

### 1. Amazon Search Suggestion Audit
*   **Description**: Queries the Amazon search suggestion endpoint to retrieve auto-complete proposals for keywords. Classifies results dynamically into `house_brand` or `third_party` listings.
*   **Compliance Schema**: Adheres to rate-limiting retry rules (backoff on 429), clean-session cookie/headers drops (on 401/403), and soft-fail fallbacks (common keyword anomaly flags, overlap filters).
*   **Status**: Deployed & Active.

### 2. DMA Regulatory Mapping (RAG)
*   **Description**: Connects to the Digital Markets Act (DMA) documentation store via Vertex AI Search (RAG). Maps brand audits directly to specific EU antitrust regulations.
*   **Offline Fallback**: Automatically simulates database chunks when Vertex AI Search is unconfigured.
*   **Status**: Deployed & Active.

### 3. Multi-Agent Orchestration Workflow
*   **Description**: A Google ADK graph coordinating specialized nodes:
    *   `validate_prompt_node`: Validates keyword syntax.
    *   `api_inspector_node`: Coordinates search brand lookup.
    *   `defense_middleware_node`: Protects context size and filters inputs.
    *   `security_checkpoint_node`: Identifies prompt injections and redacts PII.
    *   `regulatory_analyst_node`: Compiles legal analysis with mandatory EU antitrust disclaimers.
*   **Status**: Deployed & Active.

### 4. Human-In-The-Loop (HITL) Approvals
*   **Description**: Pauses compliance runs upon security alerts, Rate Limits, or when reports require human legal review. Exposes endpoints to register approvals, rejections, and annotating notes.
*   **Status**: Deployed & Active.

### 5. Researcher Dashboard Portal
*   **Description**: Standalone portal service allowing legal auditors to view active sessions, fetch pending interrupts, read generated reports, and submit HITL approval decisions.
*   **Status**: Active (Local & Deployable).

### 6. Production GCS Logging Adapter
*   **Description**: Concurrency-safe, distributed persistence adapter writing finished audit records directly to Cloud Storage buckets, bypassing local single-file locking issues.
*   **Status**: Deployed & Active.

---

## Pending Backlog Items

| ID | Title | Priority | Description | Target Component |
|---|---|---|---|---|
| **LUX-001** | Multi-region Session Service | **Medium** | Deploy Session database replication across multiple GCP locations to survive regional failovers. | Session Service |
| **LUX-002** | Automated IP Rotation | **Low** | Introduce proxy or IP rotation inside `fetch_amazon_brands` to handle rate-limiting limits under high-volume crawls. | API Inspector |
| **LUX-003** | OAuth2 Portal Authentication | **High** | Secure the Researcher Dashboard with Google Identity-Aware Proxy (IAP) or explicit OAuth login. | Frontend Portal |
| **LUX-004** | LLM-as-a-Judge Eval Auto-suite | **Medium** | Implement continuous automated playground evaluations matching synthetic digital compliance test runs. | SDK Evaluations |
