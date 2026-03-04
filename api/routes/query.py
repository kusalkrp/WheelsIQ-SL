"""
Prime Wheels SL — RAG query endpoint.
Connects the CRAG pipeline to the API.
"""

import asyncio

from fastapi import APIRouter, HTTPException

from api.models import QueryRequest, QueryResponse
from rag.crag_workflow import run_crag_pipeline
from shared.logging import get_logger

logger = get_logger(__name__)
router = APIRouter()


@router.post("/query", response_model=QueryResponse)
async def rag_query(request: QueryRequest):
    """
    Execute a natural language query against the vehicle RAG system.
    Uses the full CRAG pipeline: cache → retrieval → reranking → grading → synthesis.
    """
    logger.info("api_query", query=request.query[:80])

    try:
        result = await asyncio.wait_for(
            run_crag_pipeline(
                query=request.query,
                filters=request.filters,
                top_k=request.top_k,
                skip_cache=request.skip_cache,
            ),
            timeout=55.0,
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Query timed out. Try a more specific question.")

    return QueryResponse(
        answer=result.get("answer", ""),
        vehicles_mentioned=result.get("vehicles_mentioned", []),
        confidence=result.get("confidence", 0.0),
        follow_up_suggestions=result.get("follow_up_suggestions", []),
        query_type=result.get("query_type"),
        avg_relevance=result.get("avg_relevance"),
        num_docs_retrieved=result.get("num_docs_retrieved"),
        crag_rewrite=result.get("crag_rewrite", False),
        cache_hit=result.get("cache_hit", False),
        cache_type=result.get("cache_type", "miss"),
        response_time_ms=result.get("response_time_ms", 0),
        model_used=result.get("model_used"),
    )
