# Release Notes - LUX Agent v1.3.0

## Features & Improvements

### Refactoring Backlog Implementation
* **Stateless & Explicit App Construction**: Refactored `app/core/config.py` to move environment variables loading and dotenv resolving inside `load_settings()`. Created dynamic factory functions `create_workflow` and `create_app` in `app/agent.py`, removing all import-time side-effects and singleton state.
* **Isolated Runtime Replicas**: Fixed the runtime cloning boundary in `app/agent_runtime_app.py` by implementing a real `clone()` factory that returns a separate, clean instance of `AgentEngineApp` using the stateless factory.
* **GCS Production Storage Adapter**: Implemented `GcsAuditRepository` inside `app/core/persistence.py`, enabling safe, concurrency-proof writes directly to Google Cloud Storage (GCS) in production while preserving local JSON for local dev.
* **Transport-Decoupled Middleware**: Moved Starlette request stream body rewriting middleware completely out of `app/fast_api_app.py` to `app/core/adapters/pubsub.py`, making FastAPI transport purely thin.
* **Dashboard Bootstrap & CORS Hardening**: Extracted duplicate metadata/config lookups from `frontend/main.py` into a new `frontend/config.py` helper. Restructured CORS posture to use configurable settings allowed origins, dropping the permissive default wildcard `*`.
* **Toolchain Alignment**: Synchronized the static type checker `ty` Python environment target in `pyproject.toml` to Python `3.12`.
* **Testing Expansion**: Added unit tests for the dynamic GCS repository, repository routing factory, and cloned replica isolation, verifying all 32 tests in the suite pass.

---

# Release Notes - LUX Agent v1.2.0

## Features & Improvements

### Architectural Refactoring & Decompounding
* **Centralized Configuration**: Introduced `app/core/config.py` with an on-demand `Settings` model, eliminating import-time environment variable branching. Exposes dynamic properties for location routing and MCP detection.
* **Isolated Persistence Adapter**: Decoupled database state operations. Replaced direct file reads/writes with the `AuditRepository` abstraction inside `app/core/persistence.py`.
* **Monolithic Cleanliness**: Decomposed `agent.py` into isolated modules for validation (`app/core/validation.py`), security/redaction (`app/core/security.py`), and tools (`app/tools/amazon_brands.py`, `app/tools/dma_rag.py`).
* **Harden HTTP Boundaries**: Migrated Starlette request stream body rewrite mutations into a dedicated Pub/Sub payload adapter (`app/core/adapters/pubsub.py`).
* **Tightened Test Architecture**: Disabled global `autouse=True` mock side-effects in `tests/conftest.py`. Added unit tests for config, persistence, and pubsub adapter boundaries.

---

# Release Notes - LUX Agent v1.1.0

## Features & Improvements

### Amazon Search Suggestion API Compliance
Implemented the retry policies, error handling flows, and soft-fail fallback requirements outlined in `amazon_api_schema.md`:
* **Exponential Backoff on 429**: Automatic retry up to 3 times (Sleep: 2.0s, 4.0s, 8.0s) with randomized 0-500ms jitter. Halts and raises a `RateLimitException` if the third retry fails.
* **Clean Session Retry on 403 / 401**: Drops cookies/headers and attempts exactly one unauthenticated retry with a clean User-Agent header before raising `APIAuthenticationError`.
* **Retry on 502 / 503 / 504**: Waits exactly 5.0 seconds and retries once before raising `TransientServerError`.
* **Soft-Fail Flags**:
  - Detects and logs an `AnomalyWarning` if a highly common keyword returns zero suggestions (suspected shadow ban).
  - Detects and discards fallback results if suggestion values have 0% overlap with the queried keyword words, logging the generic category fallback error.
* **Metadata Mapping**: Both local tool and FastMCP server map suggestions payload to the baseline JSON schema containing `audit_metadata`, `results` (with `rank`, `value`, `brand_type`), and `error_log`.
* **Error-Routing and HITL Integrations**: Updated `security_checkpoint_node` and `hitl_pause_node` in the workflow to route Rate-Limit and Authentication failures directly to the Human-in-the-Loop approval node with user-friendly error messages.

### Session Cleanup Data Fix
* Fixed a bug in `scripts/reject_pending_sessions.py` where `user_id` was hardcoded to `"default-user"`. Correctly propagated the session's actual `user_id` to make sure session resume/rejections are correctly registered by the deployed Session Service.
* Executed the script to resolve both pending HITL interrupts on the deployed Agent Runtime.

## Test Coverage
* Added `tests/unit/test_amazon_api.py` covering standard success response, rate-limiting, authentication re-tries, server failure, common keyword anomalies, and generic fallbacks.
* Verified that all unit and integration tests (22 total) pass successfully without regressions.
