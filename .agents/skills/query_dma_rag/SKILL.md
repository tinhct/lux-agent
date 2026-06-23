---
name: query_dma_rag
description: Searches indexed Digital Markets Act (DMA) documents via Vertex AI Search to retrieve precise legal definitions and compliance constraints regarding algorithmic self-preferencing. Use this skill when the user asks to cross-reference findings with the DMA, needs to check gatekeeper obligations, or requests the legal definition of self-preferencing. Do NOT use for searching the open web or providing binding legal advice.
version: 1.0.0
license: MIT
allowed-tools: Read
metadata:
  author: LUX System Admin 
---
# Query DMA RAG

## When to use
- Cross-referencing technical data (e.g., scraped Amazon search results) against EU Digital Markets Act (DMA) gatekeeper rules.
- Retrieving precise legal definitions of "self-preferencing," "core platform services," or "gatekeeper" from official regulatory texts.
- Drafting the regulatory analysis portion of a compliance report that requires exact legal citations.

## When NOT to use
- Conducting general open-web searches or querying regulatory frameworks outside the indexed knowledge base (e.g., US antitrust law, unless explicitly indexed).
- Generating definitive legal rulings, corporate liability verdicts, or binding legal counsel.

## Workflow
1. Receive the target legal concept or analysis parameter from the state graph (e.g., "DMA Article 6 rules on ranking").
2. Execute a semantic search query against the Vertex AI Vector Search endpoint containing the indexed DMA documents.
3. Retrieve the top-K relevant text chunks, isolating the associated article numbers, paragraphs, and document metadata.
4. See `references/rag_citation_guidelines.md` for handling edge cases where retrieved chunks contain ambiguous language or cross-reference other un-indexed EU directives.

## Examples
- Input: `"Define self-preferencing under the DMA."` → Output: `"Under the DMA, self-preferencing occurs when a gatekeeper treats its own services or products more favorably in ranking and related indexing and crawling than similar third-party services. (Source: DMA Article 6(5))"`
- Input: `"Are search engines covered by gatekeeper rules?"` → Output: `"Yes, online search engines are defined as 'core platform services' subject to gatekeeper obligations if they meet the quantitative thresholds. (Source: DMA Article 2(2)(b))"`

## Output format
- Use `assets/regulatory_citation_template.md` to format the response. 
- Always include the exact legal Article, Paragraph, and source document name directly alongside the extracted text. 
- You must automatically append the immutable disclaimer footer: `***Disclaimer: This analysis is for research purposes only. This is NOT legal advice.***`

## Anti-patterns to avoid
- Don't hallucinate or heavily paraphrase legal definitions; rely on direct quotes from the Vertex AI Search chunks whenever possible.
- Don't omit the source citations (Article and Paragraph numbers) in the final output.
- Don't state that a specific company is definitively guilty of a legal violation; use investigative, objective language (e.g., "This technical observation intersects with restrictions outlined in...").
