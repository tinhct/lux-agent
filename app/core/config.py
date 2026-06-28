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

import os
import shutil
from typing import List, Optional
from pydantic import BaseModel, Field
from dotenv import load_dotenv

class Settings(BaseModel):
    gemini_api_key: Optional[str] = Field(default_factory=lambda: os.environ.get("GEMINI_API_KEY"))
    google_cloud_project: Optional[str] = Field(default_factory=lambda: os.environ.get("GOOGLE_CLOUD_PROJECT"))
    google_cloud_location: str = Field(default_factory=lambda: os.environ.get("GOOGLE_CLOUD_LOCATION", "global"))
    google_genai_use_vertexai: bool = Field(default_factory=lambda: os.environ.get("GOOGLE_GENAI_USE_VERTEXAI", "True").lower() in ("true", "1", "yes"))
    vertex_ai_search_project_id: Optional[str] = Field(default_factory=lambda: os.environ.get("VERTEX_AI_SEARCH_PROJECT_ID"))
    vertex_ai_search_location: str = Field(default_factory=lambda: os.environ.get("VERTEX_AI_SEARCH_LOCATION", "global"))
    vertex_ai_search_data_store_id: Optional[str] = Field(default_factory=lambda: os.environ.get("VERTEX_AI_SEARCH_DATA_STORE_ID"))
    agent_runtime_id: Optional[str] = Field(default_factory=lambda: os.environ.get("AGENT_RUNTIME_ID"))
    logs_bucket_name: Optional[str] = Field(default_factory=lambda: os.environ.get("LOGS_BUCKET_NAME"))
    allow_origins: List[str] = Field(
        default_factory=lambda: [
            o.strip()
            for o in os.environ.get("ALLOW_ORIGINS", "").split(",")
            if o.strip()
        ]
        if os.environ.get("ALLOW_ORIGINS")
        else []
    )

    @property
    def resolved_location(self) -> str:
        """Returns the location, resolving it from agent_runtime_id if present."""
        if self.agent_runtime_id:
            parts = self.agent_runtime_id.split("/")
            if len(parts) > 3 and parts[2] == "locations":
                return parts[3]
        return self.google_cloud_location

    @property
    def use_mcp(self) -> bool:
        """Determines if local MCP tools should be used instead of standard python functions."""
        mcp_server_dir = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "..", "mcp_server")
        )
        return (
            os.path.exists(mcp_server_dir)
            and shutil.which("uv") is not None
            and not self.agent_runtime_id
        )


def load_settings() -> Settings:
    """Loads and resolves settings from environment variables on-demand."""
    load_dotenv()

    # Set up default credentials & project if not already in env
    if not os.environ.get("GEMINI_API_KEY") and not os.environ.get("GOOGLE_CLOUD_PROJECT"):
        import google.auth
        try:
            _, project_id = google.auth.default()
            if project_id:
                os.environ["GOOGLE_CLOUD_PROJECT"] = project_id
        except Exception:
            pass

    # Resolve location overrides from runtime ID
    runtime_id = os.environ.get("AGENT_RUNTIME_ID")
    if runtime_id:
        parts = runtime_id.split("/")
        if len(parts) > 3 and parts[2] == "locations":
            os.environ["GOOGLE_CLOUD_LOCATION"] = parts[3]

    if not os.environ.get("GOOGLE_CLOUD_LOCATION"):
        os.environ["GOOGLE_CLOUD_LOCATION"] = "global"

    if not os.environ.get("GOOGLE_GENAI_USE_VERTEXAI"):
        os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

    return Settings()


def get_settings(force_reload: bool = False) -> Settings:
    """Wrapper for backwards compatibility."""
    return load_settings()
