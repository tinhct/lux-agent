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

import re
from typing import Any


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
