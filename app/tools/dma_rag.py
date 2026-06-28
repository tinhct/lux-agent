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

from typing import Any
from app.core.config import get_settings


def query_dma_rag(query: str) -> dict[str, Any]:
    """Searches indexed Digital Markets Act (DMA) documents via a simulated vector search endpoint.

    Args:
        query: The semantic search query or regulatory concept (e.g. 'self-preferencing', 'Article 6(5)') to look up.

    Returns:
        A dictionary containing the list of matching document chunks, including sources and relevance.
    """
    settings = get_settings()
    project_id = settings.vertex_ai_search_project_id
    location = settings.vertex_ai_search_location
    data_store_id = settings.vertex_ai_search_data_store_id
    
    def get_simulated_chunks(q: str):
        q_lower = q.lower()
        chunks = []
        if "prefer" in q_lower or "rank" in q_lower:
            chunks.append({
                "content": "Under the DMA, self-preferencing occurs when a gatekeeper treats its own services or products more favorably in ranking and related indexing and crawling than similar third-party services.",
                "source": "Digital Markets Act, Article 6, Paragraph 5",
                "relevance": 0.95
            })
        if "search" in q_lower or "core platform" in q_lower:
            chunks.append({
                "content": "Online search engines are defined as 'core platform services' subject to gatekeeper obligations if they meet the quantitative thresholds.",
                "source": "Digital Markets Act, Article 2, Paragraph 2(b)",
                "relevance": 0.90
            })
        if "gdpr" in q_lower or "article 5" in q_lower or "prejudice" in q_lower:
            chunks.append({
                "content": "This is without prejudice to obligations under Regulation (EU) 2016/679 (GDPR). Under DMA Article 5(2), gatekeepers face specific restrictions, though the text notes this is without prejudice to the GDPR.",
                "source": "Digital Markets Act, Article 5, Paragraph 2",
                "relevance": 0.88
            })
        if "gatekeeper" in q_lower or "threshold" in q_lower:
            chunks.append({
                "content": "A provider of core platform services shall be designated as a gatekeeper if it has a significant impact on the internal market, operates a core platform service which serves as an important gateway for business users to reach end users, and enjoys an established and durable position.",
                "source": "Digital Markets Act, Article 3, Paragraph 1",
                "relevance": 0.85
            })
        return chunks

    if not all([project_id, data_store_id]):
        chunks = get_simulated_chunks(query)
        if not chunks:
            return {
                "status": "no_match",
                "message": f"No relevant definitions or restrictions matching '{query}' were found in the indexed DMA documentation. The system cannot perform a compliance mapping for this specific query.",
                "chunks": []
            }
        return {
            "status": "success",
            "chunks": chunks
        }

    try:
        from google.cloud import discoveryengine_v1 as discoveryengine
        
        client = discoveryengine.SearchServiceClient()
        serving_config = (
            f"projects/{project_id}/locations/{location}"
            f"/collections/default_collection/dataStores/{data_store_id}"
            f"/servingConfigs/default_search"
        )

        extractive_spec = discoveryengine.SearchRequest.ContentSearchSpec.ExtractiveContentSpec(
            max_extractive_segment_count=3,
            return_extractive_segment_score=True,
        )

        request = discoveryengine.SearchRequest(
            serving_config=serving_config,
            query=query,
            content_search_spec=discoveryengine.SearchRequest.ContentSearchSpec(
                extractive_content_spec=extractive_spec,
            ),
        )

        response = client.search(request)
        chunks = []

        for result in response.results:
            doc_data = result.document.derived_struct_data
            segments = doc_data.get("extractive_segments", [])
            title = doc_data.get("title", "Digital Markets Act")
            
            for segment in segments:
                chunks.append({
                    "content": segment.get("content", ""),
                    "source": f"{title}, Segment {segment.get('pageNumber', 'N/A')}",
                    "relevance": segment.get("relevanceScore", 0.0),
                })

        if not chunks:
            return {
                "status": "no_match",
                "message": f"No relevant definitions or restrictions matching '{query}' were found in the indexed DMA documentation.",
                "chunks": []
            }

        chunks.sort(key=lambda x: x["relevance"], reverse=True)
        return {
            "status": "success",
            "chunks": chunks[:5]
        }

    except Exception as e:
        simulated_chunks = get_simulated_chunks(query)
        if simulated_chunks:
            return {
                "status": "success",
                "warning": f"Vertex AI Search failed ({e}). Fell back to simulated local database.",
                "chunks": simulated_chunks
            }
        return {
            "status": "error",
            "message": f"Vertex AI Search failed and no local fallback matches were found: {str(e)}",
            "chunks": []
        }
