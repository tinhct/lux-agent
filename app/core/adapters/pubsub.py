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

import json
import logging
from typing import Any
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

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


class NormalizePubSubSubscriptionMiddleware(BaseHTTPMiddleware):
    """Middleware to normalize Pub/Sub subscription path to keep session IDs clean."""

    async def dispatch(self, request: Request, call_next):
        if "/trigger/pubsub" in request.url.path and request.method == "POST":
            try:
                body = await request.json()
                normalized_body = normalize_pubsub_payload(body)
                if normalized_body is not body:
                    modified_body = json.dumps(normalized_body).encode("utf-8")

                    # Explicitly set Starlette cached body and json
                    request._body = modified_body
                    request._json = normalized_body

                    async def receive():
                        return {
                            "type": "http.request",
                            "body": modified_body,
                            "more_body": False,
                        }

                    request._receive = receive
            except Exception as e:
                logger.warning("Failed to normalize subscription body: %s", e)

        return await call_next(request)
