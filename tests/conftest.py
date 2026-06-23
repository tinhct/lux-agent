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

from unittest.mock import MagicMock, patch
import pytest

@pytest.fixture(autouse=True)
def mock_vertex_search():
    """Automatically mock Discovery Engine search client calls during test execution."""
    with patch("google.cloud.discoveryengine_v1.SearchServiceClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client_cls.return_value = mock_client
        
        # Setup mock return value with search results
        mock_result = MagicMock()
        mock_result.document.derived_struct_data = {
            "title": "Digital Markets Act",
            "extractive_segments": [
                {
                    "content": "Under the DMA, self-preferencing occurs when a gatekeeper treats its own services or products more favorably...",
                    "relevanceScore": 0.95,
                    "pageNumber": 12
                }
            ]
        }
        
        mock_response = MagicMock()
        mock_response.results = [mock_result]
        mock_client.search.return_value = mock_response
        
        yield mock_client
