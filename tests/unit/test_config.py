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
import pytest
from app.core.config import get_settings


def test_config_location_derived_from_runtime_id(monkeypatch):
    """Verify that location is derived from AGENT_RUNTIME_ID if set."""
    monkeypatch.setenv("AGENT_RUNTIME_ID", "projects/12345/locations/us-east4/reasoningEngines/678")
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")

    settings = get_settings(force_reload=True)
    assert settings.resolved_location == "us-east4"
    assert os.environ.get("GOOGLE_CLOUD_LOCATION") == "us-east4"


def test_config_location_override_when_global(monkeypatch):
    """Verify runtime ID location overrides global even when set."""
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "global")
    monkeypatch.setenv("AGENT_RUNTIME_ID", "projects/12345/locations/europe-west1/reasoningEngines/678")

    settings = get_settings(force_reload=True)
    assert settings.resolved_location == "europe-west1"
    assert os.environ.get("GOOGLE_CLOUD_LOCATION") == "europe-west1"


def test_config_location_preserved_when_no_runtime_id(monkeypatch):
    """Verify that if no AGENT_RUNTIME_ID is present, the location default/env is preserved."""
    monkeypatch.delenv("AGENT_RUNTIME_ID", raising=False)
    monkeypatch.setenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    settings = get_settings(force_reload=True)
    assert settings.resolved_location == "us-central1"
    assert os.environ.get("GOOGLE_CLOUD_LOCATION") == "us-central1"
