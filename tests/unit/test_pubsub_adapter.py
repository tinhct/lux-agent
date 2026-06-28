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

from app.core.adapters.pubsub import normalize_pubsub_payload


def test_normalize_pubsub_payload_full_path():
    """Verify that a full subscription resource path is correctly normalized to its short name."""
    payload = {
        "message": {"data": "hello"},
        "subscription": "projects/my-project/subscriptions/my-sub-name"
    }
    res = normalize_pubsub_payload(payload)
    assert res["subscription"] == "my-sub-name"
    assert res["message"]["data"] == "hello"


def test_normalize_pubsub_payload_already_short():
    """Verify that an already short subscription name is untouched."""
    payload = {
        "message": {"data": "hello"},
        "subscription": "my-sub-name"
    }
    res = normalize_pubsub_payload(payload)
    assert res["subscription"] == "my-sub-name"


def test_normalize_pubsub_payload_non_dict():
    """Verify that non-dictionary inputs are returned unmodified."""
    assert normalize_pubsub_payload("not-a-dict") == "not-a-dict"
    assert normalize_pubsub_payload(None) is None
