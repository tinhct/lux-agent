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
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

logger = logging.getLogger("lux_researcher_portal.config")


class DashboardSettings(BaseModel):
    project_id: Optional[str] = Field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT")
    )
    location: str = Field(
        default_factory=lambda: os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
    )
    agent_runtime_id: Optional[str] = Field(
        default_factory=lambda: os.environ.get("AGENT_RUNTIME_ID")
    )
    allow_origins: List[str] = Field(
        default_factory=lambda: [
            o.strip()
            for o in os.environ.get("ALLOW_ORIGINS", "").split(",")
            if o.strip()
        ]
        if os.environ.get("ALLOW_ORIGINS")
        else ["http://localhost:8080", "http://localhost:8081"]
    )

    @property
    def resolved_location(self) -> str:
        """Derive region directly from runtime resource name if available."""
        if self.agent_runtime_id:
            parts = self.agent_runtime_id.split("/")
            if len(parts) > 3 and parts[2] == "locations":
                return parts[3]
        return self.location


def load_dashboard_settings() -> DashboardSettings:
    """Loads and resolves dashboard configuration settings from environment or metadata."""
    root_dotenv = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", ".env")
    )
    load_dotenv(root_dotenv)

    project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")
    agent_runtime_id = os.environ.get("AGENT_RUNTIME_ID")

    # Fallback to local deployment_metadata.json if variables are not in env
    if not project_id or not agent_runtime_id:
        meta_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "deployment_metadata.json")
        )
        if os.path.exists(meta_path):
            try:
                with open(meta_path) as f:
                    meta = json.load(f)
                    if not agent_runtime_id:
                        agent_runtime_id = meta.get("remote_agent_runtime_id")
                        if agent_runtime_id:
                            os.environ["AGENT_RUNTIME_ID"] = agent_runtime_id

                    # Extract project_id from AGENT_RUNTIME_ID if not already set
                    if not project_id and agent_runtime_id:
                        parts = agent_runtime_id.split("/")
                        if len(parts) > 1 and parts[0] == "projects":
                            project_id = parts[1]
                            os.environ["GOOGLE_CLOUD_PROJECT"] = project_id

                    logger.info(
                        f"Loaded config from metadata: project={project_id}, runtime={agent_runtime_id}"
                    )
            except Exception as e:
                logger.warning(f"Failed to read deployment_metadata.json: {e}")

    # Set authoritative location if agent_runtime_id is set
    if agent_runtime_id:
        parts = agent_runtime_id.split("/")
        if len(parts) > 3 and parts[2] == "locations":
            os.environ["GOOGLE_CLOUD_LOCATION"] = parts[3]

    # Dynamic fallback via google.auth if project_id still empty
    if not project_id:
        try:
            import google.auth
            _, auth_project = google.auth.default()
            if auth_project:
                project_id = auth_project
                os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        except Exception as e:
            logger.warning(f"Failed to load project ID from google.auth: {e}")

    if not project_id:
        logger.error(
            "GOOGLE_CLOUD_PROJECT environment variable is not set and could not be detected."
        )

    if not os.environ.get("GOOGLE_CLOUD_LOCATION"):
        os.environ["GOOGLE_CLOUD_LOCATION"] = "us-central1"

    return DashboardSettings()
