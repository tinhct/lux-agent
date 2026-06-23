import json

import requests
from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
mcp = FastMCP("lux_audit_sandbox")


@mcp.tool()
def fetch_amazon_brands(keyword: str) -> str:
    """Queries Amazon's undocumented search suggestion API to extract structured data on private-label brands.

    Args:
        keyword: The search keyword (e.g. 'batteries', 'spicy') to query.

    Returns:
        A JSON string containing the search keyword and brand classification results.
    """
    if keyword == "mock_payload":
        result = {
            "keyword": "mock_payload",
            "suggestions": [
                {"value": "amazon basics batteries", "brand_type": "house_brand"},
                {"value": "energizer aa batteries", "brand_type": "third_party"},
            ],
        }
        return json.dumps(result, indent=2)

    url = "https://completion.amazon.com/api/2017/suggestions"
    params = {
        "mid": "ATVPDKIKX0DER",  # Amazon US Marketplace ID
        "alias": "aps",  # Search alias (aps = all departments)
        "prefix": keyword,
        "suggestion-type": "keyword",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        suggestions = []
        # Parse suggestions and classify brand type
        for item in data.get("suggestions", []):
            value = item.get("value", "")
            # Classify brand type (simulated logic for private-label vs third-party)
            if (
                "amazon" in value.lower()
                or "basics" in value.lower()
                or "solimo" in value.lower()
                or "presto" in value.lower()
            ):
                brand_type = "house_brand"
            else:
                brand_type = "third_party"

            suggestions.append({"value": value, "brand_type": brand_type})

        result = {"keyword": keyword, "suggestions": suggestions}
        return json.dumps(result, indent=2)

    except Exception as e:
        error_result = {
            "keyword": keyword,
            "error": f"Failed to fetch suggestions from Amazon API: {e}",
            "suggestions": [],
        }
        return json.dumps(error_result, indent=2)


@mcp.tool()
def query_saved_reports(keyword: str = None) -> str:
    """Reads the saved compliance audit reports from the database file and optionally filters them by keyword.

    Args:
        keyword: Optional search keyword to filter reports by.

    Returns:
        A JSON string containing the list of matching saved audit reports.
    """
    import os
    db_path = "audit_db.json"
    if not os.path.exists(db_path):
        return json.dumps({"status": "empty", "message": f"No reports saved yet at {os.path.abspath(db_path)}.", "reports": []})

    try:
        with open(db_path, "r") as f:
            reports = json.load(f)
        
        if keyword:
            keyword_lower = keyword.lower()
            filtered_reports = []
            for r in reports:
                # Search keyword in notes, report title, summary, etc.
                notes = r.get("notes", "").lower()
                report_data = r.get("report", {})
                title = report_data.get("title", "").lower()
                summary = report_data.get("extracted_receipts_summary", "").lower()
                mapping = report_data.get("dma_compliance_mapping", "").lower()
                
                if (keyword_lower in notes or 
                    keyword_lower in title or 
                    keyword_lower in summary or 
                    keyword_lower in mapping):
                    filtered_reports.append(r)
            reports = filtered_reports

        return json.dumps({"status": "success", "reports": reports}, indent=2)
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)})
@mcp.tool()
def query_dma_rag(query: str) -> str:
    """Searches indexed Digital Markets Act (DMA) documents via a simulated vector search endpoint.

    Args:
        query: The semantic search query or regulatory concept (e.g. 'self-preferencing', 'Article 6(5)') to look up.

    Returns:
        A JSON string containing the list of matching document chunks, including sources and relevance.
    """
    import os
    
    project_id = os.environ.get("VERTEX_AI_SEARCH_PROJECT_ID")
    location = os.environ.get("VERTEX_AI_SEARCH_LOCATION", "global")
    data_store_id = os.environ.get("VERTEX_AI_SEARCH_DATA_STORE_ID")
    
    # Simple semantic keyword matching mock/simulated fallback if config is missing
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
        # No config, run the simulated RAG search
        chunks = get_simulated_chunks(query)
        if not chunks:
            return json.dumps({
                "status": "no_match",
                "message": f"No relevant definitions or restrictions matching '{query}' were found in the indexed DMA documentation. The system cannot perform a compliance mapping for this specific query.",
                "chunks": []
            }, indent=2)
        return json.dumps({
            "status": "success",
            "chunks": chunks
        }, indent=2)

    # Production Vertex AI Search flow
    try:
        from google.cloud import discoveryengine_v1 as discoveryengine
        
        client = discoveryengine.SearchServiceClient()
        
        # Build serving config path
        serving_config = (
            f"projects/{project_id}/locations/{location}"
            f"/collections/default_collection/dataStores/{data_store_id}"
            f"/servingConfigs/default_search"
        )

        # Configure extractive segments to retrieve clean quotes and relevance scores
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
            return json.dumps({
                "status": "no_match",
                "message": f"No relevant definitions or restrictions matching '{query}' were found in the indexed DMA documentation.",
                "chunks": []
            }, indent=2)

        # Sort chunks by relevance
        chunks.sort(key=lambda x: x["relevance"], reverse=True)
        return json.dumps({
            "status": "success",
            "chunks": chunks[:5]  # Limit to top 5 chunks
        }, indent=2)

    except Exception as e:
        # Fallback to simulated chunks if API fails (as a safety measure)
        simulated_chunks = get_simulated_chunks(query)
        if simulated_chunks:
            return json.dumps({
                "status": "success",
                "warning": f"Vertex AI Search failed ({e}). Fell back to simulated local database.",
                "chunks": simulated_chunks
            }, indent=2)
        return json.dumps({
            "status": "error",
            "message": f"Vertex AI Search failed and no local fallback matches were found: {str(e)}",
            "chunks": []
        }, indent=2)


if __name__ == "__main__":
    # Start the FastMCP server using stdio transport
    mcp.run()
