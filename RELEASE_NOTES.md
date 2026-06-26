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
