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
import os

from fastapi import FastAPI, Request
from google.adk.cli.fast_api import get_fast_api_app
from starlette.middleware.base import BaseHTTPMiddleware

from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback
from app.core.config import get_settings
from app.core.adapters.pubsub import normalize_pubsub_payload

# Setup standard Python logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize settings
settings = get_settings()

setup_telemetry()

allow_origins = settings.allow_origins if settings.allow_origins else None
logs_bucket_name = settings.logs_bucket_name

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# In-memory session configuration - no persistent storage
session_service_uri = None

artifact_service_uri = f"gs://{logs_bucket_name}" if logs_bucket_name else None

app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=artifact_service_uri,
    allow_origins=allow_origins,
    session_service_uri=session_service_uri,
    otel_to_cloud=False,  # Set otel_to_cloud=False as requested
    trigger_sources=["pubsub"],  # Expose Pub/Sub trigger endpoint
)
app.title = "lux-agent"
app.description = "API for interacting with the Agent lux-agent"


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


# Add the normalization middleware to the app
app.add_middleware(NormalizePubSubSubscriptionMiddleware)


@app.post("/feedback")
def collect_feedback(feedback: Feedback) -> dict[str, str]:
    """Collect and log feedback.

    Args:
        feedback: The feedback data to log

    Returns:
        Success message
    """
    logger.info("Feedback received: %s", feedback.model_dump())
    return {"status": "success"}


# Main execution
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8080)
