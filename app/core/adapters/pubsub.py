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

import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def normalize_pubsub_payload(body: Any) -> Any:
    """Normalizes the Pub/Sub request payload.

    Extracts the short subscription name from a full resource path to prevent
    unclean session IDs (e.g. 'projects/p/subscriptions/sub' -> 'sub').
    """
    if not isinstance(body, dict):
        return body

    subscription = body.get("subscription")
    if isinstance(subscription, str) and "/" in subscription:
        short_name = subscription.split("/")[-1]
        normalized = body.copy()
        normalized["subscription"] = short_name
        logger.info(
            "Normalized Pub/Sub subscription path: %s -> %s",
            subscription,
            short_name,
        )
        return normalized

    return body
