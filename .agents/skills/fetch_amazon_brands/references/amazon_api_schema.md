# Amazon API Schema & Error Handling Guidelines
**Version:** 1.0.0
**Target Agent:** API Inspector (`fetch_amazon_brands` skill)
**System:** LUX (Legal Uncovering, eXplainable)

## Purpose
This document outlines the expected response schemas and mandatory error-handling protocols for interacting with the undocumented Amazon Search Suggestion API (`https://completion.amazon.com/api/2017/suggestions`). Because this is an undocumented endpoint, it is subject to sudden rate limits, token expirations, and transient server errors. 

The API Inspector agent and its underlying Python MCP tools MUST implement these fallback strategies to maintain research integrity and prevent system crashes.

---

## 1. HTTP Status Codes & Fallback Protocols

### 429: Too Many Requests (Rate Limiting)
* **Trigger:** The system has fired too many requests from the same IP within a narrow time window.
* **Agent Action:** 1. Immediately halt execution. Do not retry instantly.
    2. Implement an **Exponential Backoff with Jitter**:
       * *Attempt 1:* Sleep for `2.0` seconds + random jitter (0-500ms).
       * *Attempt 2:* Sleep for `4.0` seconds + random jitter.
       * *Attempt 3:* Sleep for `8.0` seconds + random jitter.
    3. If the 3rd attempt fails, gracefully exit the MCP tool, flag a `RateLimitException`, and push the Graph state to the Human-in-the-Loop (HITL) node with the message: *"Audit paused due to strict API rate limiting. Manual IP rotation or cooling period required."*

### 403 / 401: Forbidden / Unauthorized (Token or Cookie Expiry)
* **Trigger:** The endpoint detects a stale `session-id` cookie, an outdated `User-Agent` string, or flagged automated behavior.
* **Agent Action:**
    1. **Do not attempt to bypass authentication illegally.** 2. Drop the current session variables and attempt exactly *one* retry using a clean, unauthenticated session header (standard browser User-Agent without specific Amazon cookies).
    3. If the clean retry also returns 403, the endpoint structure has likely changed. Route to the HITL node with the message: *"API authentication rejected. The undocumented suggestion endpoint may have updated its security posture."*

### 502 / 503 / 504: Bad Gateway / Server Errors
* **Trigger:** Transient upstream failures from Amazon's load balancers.
* **Agent Action:** 1. Wait exactly `5.0` seconds and retry once.
    2. If the failure persists, log a `TransientServerError` and output the partial data (if any) to the Regulatory Analyst, noting the incomplete dataset.

---

## 2. "Soft Fails" (200 OK but invalid data)

Sometimes the API returns a `200 OK` status, but the payload indicates a failure or a block.

### The "Empty Suggestions" Array
* **Scenario:** Response is `{"suggestions": []}`.
* **Handling:** If a highly common keyword (e.g., "batteries") returns zero suggestions, it is highly likely that Amazon has shadow-banned the session IP, or the localization parameters (`mkt`, `mid`) are malformed. 
* **Agent Action:** Verify the parameters. If correct, flag this anomaly in the final output. Do not hallucinate data to fill the void.

### The "Generic Fallback" Payload
* **Scenario:** The API ignores the specific query and returns generic top-level categories (e.g., "Clothing", "Electronics").
* **Handling:** Compare the returned suggestion prefixes with the requested `keyword`. If the overlap is 0%, discard the data. The API Inspector must explicitly state: *"Data extraction failed: API returned generic category fallbacks rather than keyword-specific recommendations."*

---

## 3. Expected Baseline JSON Schema

When successful, the MCP Python script must ensure the raw Amazon payload is mapped to this exact schema before passing it through the prompt-injection middleware:

```json
{
  "audit_metadata": {
    "keyword": "string",
    "timestamp_utc": "ISO-8601",
    "status_code": 200
  },
  "results": [
    {
      "rank": "integer",
      "value": "string (the suggested search term)",
      "brand_type": "string ('house_brand' | 'third_party' | 'unknown')"
    }
  ],
  "error_log": null
}