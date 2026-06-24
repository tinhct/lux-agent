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
import pytest
from app.agent import validate_keyword


def test_validate_keyword_valid():
    assert validate_keyword("Kindle") == "Kindle"
    assert validate_keyword("  AA batteries  ") == "AA batteries"
    assert validate_keyword("smart-watch") == "smart-watch"
    assert validate_keyword("men's shoes") == "men's shoes"


def test_validate_keyword_invalid_type_or_empty():
    with pytest.raises(ValueError, match="must be a string"):
        validate_keyword(123)
    with pytest.raises(ValueError, match="cannot be empty"):
        validate_keyword("   ")


def test_validate_keyword_boundaries():
    with pytest.raises(ValueError, match="too short"):
        validate_keyword("a")
    with pytest.raises(ValueError, match="too long"):
        validate_keyword("a" * 51)


def test_validate_keyword_security_allowlist():
    with pytest.raises(ValueError, match="invalid characters"):
        validate_keyword("kindle!")


def test_validate_keyword_security_illegal_chars():
    for char in ["<", ">", "{", "}", "[", "]", "\\", "/", ";", "=", "*"]:
        with pytest.raises(ValueError, match="illegal character"):
            validate_keyword(f"kindle{char}")


def test_validate_keyword_security_prompt_injection():
    for phrase in ["ignore instructions", "bypass system", "system prompt", "print rules"]:
        with pytest.raises(ValueError, match="blocked word signature"):
            validate_keyword(phrase)


def test_validate_keyword_domain_asin():
    with pytest.raises(ValueError, match="ASINs.*not allowed"):
        validate_keyword("B08QF1V9T2")


def test_validate_keyword_domain_url():
    for url in ["www.amazon.co.uk", "amazon.com"]:
        with pytest.raises(ValueError, match="URLs/links.*not allowed"):
            validate_keyword(url)
    with pytest.raises(ValueError, match="illegal character"):
        validate_keyword("http://amazon.org")


def test_validate_keyword_ethical_pii():
    # Email
    with pytest.raises(ValueError, match="email address"):
        validate_keyword("user@example.net")
    # Phone
    with pytest.raises(ValueError, match="phone number"):
        validate_keyword("123-456-7890")
    # SSN
    with pytest.raises(ValueError, match="Social Security Number"):
        validate_keyword("123-45-6789")


def test_validate_keyword_ethical_nsfw():
    for term in ["porn", "nsfw", "xxx", "suicide", "bomb"]:
        with pytest.raises(ValueError, match="restricted term"):
            validate_keyword(term)
