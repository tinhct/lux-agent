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


def validate_keyword(keyword: Any) -> str:
    """Validates and sanitizes a keyword input for fetch_amazon_brands.

    Raises ValueError with a clear user-facing explanation if validation fails.
    Returns the cleaned (trimmed and normalized) keyword string.
    """
    if not isinstance(keyword, str):
        raise ValueError("Keyword must be a string.")

    # Whitespace Trimming & Normalization
    cleaned = keyword.strip()
    cleaned = re.sub(r"\s+", " ", cleaned)

    if not cleaned:
        raise ValueError("Keyword cannot be empty.")

    # Length Boundaries
    if len(cleaned) < 2:
        raise ValueError("Keyword is too short (minimum length is 2 characters).")
    if len(cleaned) > 50:
        raise ValueError("Keyword is too long (maximum length is 50 characters).")

    # Security: Illegal Character Rejection
    illegal_chars = ["<", ">", "{", "}", "[", "]", "\\", "/", ";", "=", "*"]
    for char in illegal_chars:
        if char in cleaned:
            raise ValueError(f"Keyword contains illegal character: '{char}'")

    # Security: Anti-Prompt Injection Signatures
    injection_patterns = ["ignore", "instructions", "system prompt", "bypass", "print"]
    cleaned_lower = cleaned.lower()
    for pattern in injection_patterns:
        if pattern in cleaned_lower:
            raise ValueError(f"Keyword contains blocked word signature: '{pattern}'")

    # Domain: ASIN Rejection (10-character alphanumeric starting with B0)
    if re.match(r"(?i)^B0[A-Z0-9]{8}$", cleaned):
        raise ValueError("ASINs (Amazon Standard Identification Numbers) are not allowed as search keywords.")

    # Domain: URL Rejection (containing http, www, or .com)
    url_patterns = ["http", "www", ".com"]
    for pattern in url_patterns:
        if pattern in cleaned_lower:
            raise ValueError("URLs/links are not allowed as search keywords.")

    # Ethical: PII Block (email, phone, SSN)
    email_regex = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
    phone_regex = r"\+?\d[\d\-\s\(\)]{8,}\d"
    ssn_regex = r"\d{3}-\d{2}-\d{4}"

    if re.search(email_regex, cleaned):
        raise ValueError("Input contains a pattern formatted like an email address (blocked for PII protection).")
    if re.search(ssn_regex, cleaned):
        raise ValueError("Input contains a pattern formatted like a Social Security Number (blocked for PII protection).")
    if re.search(phone_regex, cleaned):
        raise ValueError("Input contains a pattern formatted like a phone number (blocked for PII protection).")

    # Ethical: NSFW / Harmful Content Filter (Basic blocklist)
    harmful_terms = [
        "porn", "nsfw", "xxx", "sex", "drugs", "weapons", "bomb", "kill", "suicide", "gamble"
    ]
    for term in harmful_terms:
        if term in cleaned_lower:
            raise ValueError(f"Keyword contains restricted term: '{term}'")

    # Security: Character Allowlist (catch-all at the end)
    if not re.match(r"^[\w\s\-\']+$", cleaned):
        raise ValueError("Keyword contains invalid characters. Only alphanumeric, spaces, hyphens, and apostrophes are allowed.")

    return cleaned
