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
import random
import re
import time
from typing import Any
import requests

from app.core.validation import validate_keyword


class RateLimitException(Exception):
    pass


class APIAuthenticationError(Exception):
    pass


class TransientServerError(Exception):
    pass


def fetch_amazon_brands(keyword: str) -> dict[str, Any]:
    """Queries Amazon's undocumented search suggestion API to extract structured data on private-label brands.

    Args:
        keyword: The search keyword (e.g. 'batteries', 'spicy') to query.

    Returns:
        A dictionary containing the search keyword and brand classification results matching amazon_api_schema.md.
    """
    timestamp_utc = datetime.datetime.now(datetime.timezone.utc).isoformat()

    try:
        cleaned_keyword = validate_keyword(keyword)
    except ValueError as e:
        return {
            "audit_metadata": {
                "keyword": keyword,
                "timestamp_utc": timestamp_utc,
                "status_code": 400
            },
            "results": [],
            "error_log": f"Validation failed: {e}"
        }

    if cleaned_keyword == "mock_payload":
        return {
            "audit_metadata": {
                "keyword": "mock_payload",
                "timestamp_utc": timestamp_utc,
                "status_code": 200
            },
            "results": [
                {"rank": 1, "value": "amazon basics batteries", "brand_type": "house_brand"},
                {"rank": 2, "value": "energizer aa batteries", "brand_type": "third_party"},
            ],
            "error_log": None
        }

    url = "https://completion.amazon.com/api/2017/suggestions"
    params = {
        "mid": "ATVPDKIKX0DER",
        "alias": "aps",
        "prefix": cleaned_keyword,
        "suggestion-type": "keyword",
    }

    # Default headers
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    attempted_clean_retry = False
    max_429_attempts = 3
    attempt_429 = 0
    status_code = 200
    error_log = None
    data = None

    while True:
        try:
            response = requests.get(url, params=params, headers=headers, timeout=10)
            status_code = response.status_code

            if status_code == 429:
                attempt_429 += 1
                if attempt_429 <= max_429_attempts:
                    base_sleep = 2.0 * (2 ** (attempt_429 - 1))
                    jitter = random.uniform(0, 0.5)
                    time.sleep(base_sleep + jitter)
                    continue
                else:
                    raise RateLimitException(
                        "Audit paused due to strict API rate limiting. Manual IP rotation or cooling period required."
                    )

            if status_code in (401, 403):
                if not attempted_clean_retry:
                    headers = {
                        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    }
                    attempted_clean_retry = True
                    continue
                else:
                    raise APIAuthenticationError(
                        "API authentication rejected. The undocumented suggestion endpoint may have updated its security posture."
                    )

            if status_code in (502, 503, 504):
                time.sleep(5.0)
                response = requests.get(url, params=params, headers=headers, timeout=10)
                status_code = response.status_code
                if status_code in (502, 503, 504):
                    raise TransientServerError(
                        "Transient server error: Amazon load balancer or server is down."
                    )

            response.raise_for_status()
            data = response.json()
            break

        except requests.exceptions.RequestException as e:
            if e.response is not None:
                status_code = e.response.status_code
                if status_code == 429:
                    attempt_429 += 1
                    if attempt_429 <= max_429_attempts:
                        base_sleep = 2.0 * (2 ** (attempt_429 - 1))
                        jitter = random.uniform(0, 0.5)
                        time.sleep(base_sleep + jitter)
                        continue
                    else:
                        error_log = "RateLimitException: Audit paused due to strict API rate limiting. Manual IP rotation or cooling period required."
                        break
                elif status_code in (401, 403):
                    if not attempted_clean_retry:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                        }
                        attempted_clean_retry = True
                        continue
                    else:
                        error_log = "APIAuthenticationError: API authentication rejected. The undocumented suggestion endpoint may have updated its security posture."
                        break
                elif status_code in (502, 503, 504):
                    time.sleep(5.0)
                    try:
                        response = requests.get(url, params=params, headers=headers, timeout=10)
                        status_code = response.status_code
                        response.raise_for_status()
                        data = response.json()
                        break
                    except Exception as e_retry:
                        error_log = f"TransientServerError: Transient server error: Amazon load balancer or server is down: {e_retry}"
                        break
            error_log = f"NetworkException: Failed to fetch suggestions from Amazon API: {e}"
            break
        except (RateLimitException, APIAuthenticationError, TransientServerError) as e:
            error_log = f"{e.__class__.__name__}: {e}"
            break
        except Exception as e:
            error_log = f"Exception: Failed to fetch suggestions: {e}"
            break

    if error_log:
        return {
            "audit_metadata": {
                "keyword": cleaned_keyword,
                "timestamp_utc": timestamp_utc,
                "status_code": status_code
            },
            "results": [],
            "error_log": error_log
        }

    raw_suggestions = data.get("suggestions", [])
    
    # Soft Fails
    common_keywords = {"batteries", "basics", "amazon", "kindle", "spicy"}
    if not raw_suggestions and cleaned_keyword.lower() in common_keywords:
        error_log = "AnomalyWarning: Common keyword returned empty suggestions. Shadow-ban or malformed parameters suspected."
    
    elif raw_suggestions:
        keyword_words = set(re.findall(r"\w+", cleaned_keyword.lower()))
        has_overlap = False
        for item in raw_suggestions:
            val = item.get("value", "").lower()
            val_words = set(re.findall(r"\w+", val))
            if keyword_words.intersection(val_words):
                has_overlap = True
                break
        
        if not has_overlap:
            error_log = "Data extraction failed: API returned generic category fallbacks rather than keyword-specific recommendations."
            raw_suggestions = []

    results = []
    if not error_log or "AnomalyWarning" in error_log:
        for index, item in enumerate(raw_suggestions):
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
            
            results.append({
                "rank": index + 1,
                "value": value,
                "brand_type": brand_type
            })

    return {
        "audit_metadata": {
            "keyword": cleaned_keyword,
            "timestamp_utc": timestamp_utc,
            "status_code": status_code
        },
        "results": results,
        "error_log": error_log
    }
