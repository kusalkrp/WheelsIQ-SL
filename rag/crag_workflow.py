"""
Prime Wheels SL — Full CRAG (Corrective RAG) Workflow.
Orchestrates: CAG cache → hybrid retrieval → reranking → grading → correction → synthesis.
"""

import asyncio
import time
from datetime import datetime, timezone

from ingestion.embedder import embed_query
from ingestion.qdrant_indexer import dense_search
from rag.cag_cache import check_cache, store_cache
from rag.constraint_extractor import extract_constraints
from rag.grader import grade_documents
from rag.query_classifier import rewrite_query
from rag.synthesizer import synthesize_answer
from shared.config import get_settings
from shared.database import SyncSessionLocal
from shared.logging import get_logger
from shared.models import QueryLog

logger = get_logger(__name__)
settings = get_settings()

# Relevance threshold for CRAG correction
RELEVANCE_THRESHOLD = 0.4
MAX_REWRITES = 1


def _empty_response(query: str, start_time: float) -> dict:
    """Generate response when no documents are found."""
    return {
        "answer": "I couldn't find any vehicle listings matching your query. "
                  "Try broadening your search or check back after the next data refresh.",
        "vehicles_mentioned": [],
        "confidence": 0.0,
        "follow_up_suggestions": [
            "Try searching for a specific make like Toyota or Suzuki",
            "Ask about popular vehicle types in Sri Lanka",
        ],
        "num_docs_retrieved": 0,
        "cache_hit": False,
        "response_time_ms": int((time.time() - start_time) * 1000),
    }


async def run_crag_pipeline(
    query: str,
    filters: dict | None = None,
    top_k: int = 20,
    skip_cache: bool = False,
) -> dict:
    """
    Full CRAG pipeline:
    1. Check CAG cache (exact → semantic)
    2. Embed query → dense Qdrant search
    3. Grade with Gemini Pro
    5. If low relevance → rewrite query → re-retrieve
    6. Synthesize answer with Gemini Flash
    7. Cache result

    Args:
        query: User's natural language question
        filters: Optional Qdrant payload filters
        top_k: Number of docs to retrieve

        skip_cache: Bypass cache for fresh results

    Returns:
        Structured response dict
    """
    start_time = time.time()
    query_type = None
    cache_type = "miss"
    crag_rewrite = False
    model_used = settings.gemini_flash_model
    num_docs = 0
    avg_relevance = 0.0

    try:
        # ── Step 1: Embed query (needed for semantic cache + retrieval) ──
        query_embeddings = await embed_query(query)
        query_dense = query_embeddings["dense"][0]

        # ── Step 2: Check CAG cache ──
        # Extract constraints early so we know whether to skip semantic cache.
        # Queries with price/year constraints must NOT match semantically similar
        # queries with different numbers (e.g. "5M" vs "10M" queries are semantically
        # near-identical but need completely different answers).
        auto_filters = extract_constraints(query) if not filters else {}
        # _ranking is not a Qdrant filter — extract before search
        ranking = auto_filters.pop("_ranking", None)
        # Skip semantic cache whenever ANY constraint or ranking intent is detected:
        # semantically similar queries with different numbers/ordering give different answers
        skip_semantic_cache = bool(auto_filters) or bool(ranking)

        if not skip_cache:
            cached, cache_type = await asyncio.to_thread(
                check_cache, query, query_dense, skip_semantic_cache
            )
            if cached:
                response_time = int((time.time() - start_time) * 1000)
                asyncio.create_task(asyncio.to_thread(
                    _log_query,
                    query,
                    cached.get("query_type", "cached"),
                    True,
                    cache_type,
                    response_time,
                ))
                cached["cache_hit"] = True
                cached["cache_type"] = cache_type
                cached["response_time_ms"] = response_time
                return cached

        # ── Step 3: Dense retrieval from Qdrant with auto-extracted constraints ──
        effective_filters = {**auto_filters, **(filters or {})} or None

        logger.info(
            "retrieving_documents",
            query=query[:80],
            top_k=top_k,
            filters=effective_filters,
        )
        documents = await dense_search(
            query, top_k=top_k, filters=effective_filters, query_vector=query_dense
        )

        # Graceful fallback: relax location filter, then all filters
        if not documents and auto_filters:
            no_location = {k: v for k, v in auto_filters.items() if k != "district"}
            if no_location:
                logger.info("retrieval_fallback", removed="district")
                documents = await dense_search(
                    query, top_k=top_k, filters=no_location, query_vector=query_dense
                )
            if not documents:
                logger.info("retrieval_fallback", removed="all_filters")
                documents = await dense_search(
                    query, top_k=top_k, filters=None, query_vector=query_dense
                )

        if not documents:
            return _empty_response(query, start_time)

        # ── Step 4: Grade documents with Gemini Pro ──
        graded_docs = await asyncio.to_thread(grade_documents, query, documents, auto_filters)
        num_docs = len(graded_docs)

        # Calculate average relevance
        avg_relevance = (
            sum(d["grade"]["relevance"] for d in graded_docs) / len(graded_docs)
            if graded_docs
            else 0.0
        )

        query_type = graded_docs[0]["grade"]["query_type"] if graded_docs else "unknown"

        # ── Step 6: CRAG Correction (if relevance too low) ──
        if avg_relevance < RELEVANCE_THRESHOLD and not crag_rewrite:
            logger.info(
                "crag_correction_triggered",
                avg_relevance=f"{avg_relevance:.3f}",
                threshold=RELEVANCE_THRESHOLD,
            )
            crag_rewrite = True

            # Rewrite query
            rewritten_query = await asyncio.to_thread(rewrite_query, query, avg_relevance, auto_filters)

            # Re-embed and re-retrieve (pass vector to avoid double embedding)
            rewritten_embeddings = await embed_query(rewritten_query)
            rewritten_dense = rewritten_embeddings["dense"][0]
            documents = await dense_search(
                rewritten_query, top_k=top_k, filters=filters, query_vector=rewritten_dense
            )

            if documents:
                graded_docs = await asyncio.to_thread(grade_documents, rewritten_query, documents, auto_filters)
                avg_relevance = (
                    sum(d["grade"]["relevance"] for d in graded_docs) / len(graded_docs)
                    if graded_docs
                    else 0.0
                )
                num_docs = len(graded_docs)

        # ── Step 7: Filter to relevant docs only ──
        relevant_docs = [
            d for d in graded_docs if d["grade"]["relevance"] >= 0.3
        ]
        if not relevant_docs:
            relevant_docs = graded_docs[:5]  # Fallback: use top 5 anyway

        # ── Step 7b: Sort by ranking intent if detected ──
        if ranking:
            field = ranking["field"]
            reverse = ranking["order"] == "desc"
            # Docs missing the field go to the end
            sentinel = 0 if reverse else float("inf")
            relevant_docs.sort(
                key=lambda d: d.get("metadata", {}).get(field) or sentinel,
                reverse=reverse,
            )
            logger.info(
                "ranking_sort_applied",
                field=field,
                order=ranking["order"],
                docs=len(relevant_docs),
            )

        # ── Step 8: Synthesize answer with Gemini Flash ──
        # Pass ranking in constraints so synthesizer knows the intended order
        synthesis_constraints = {**auto_filters, **({"_ranking": ranking} if ranking else {})}
        response = await asyncio.to_thread(synthesize_answer, query, relevant_docs, synthesis_constraints)
        response["query_type"] = query_type
        response["avg_relevance"] = avg_relevance
        response["num_docs_retrieved"] = num_docs
        response["crag_rewrite"] = crag_rewrite
        response["cache_hit"] = False
        response["cache_type"] = "miss"

        response_time = int((time.time() - start_time) * 1000)
        response["response_time_ms"] = response_time

        # ── Step 9: Cache the result (fire-and-forget) ──
        # Skip semantic cache for price-constrained queries to prevent a "5M" answer
        # from being served to a "10M" query (same embedding, different correct answer).
        if "error" not in response:
            asyncio.create_task(asyncio.to_thread(
                store_cache, query, query_dense, response, skip_semantic_cache
            ))

        # ── Step 10: Log the query (fire-and-forget) ──
        asyncio.create_task(asyncio.to_thread(
            _log_query,
            query,
            query_type,
            False,
            "miss",
            response_time,
            num_docs,
            avg_relevance,
            crag_rewrite,
            model_used,
        ))

        logger.info(
            "crag_pipeline_complete",
            response_time_ms=response_time,
            avg_relevance=f"{avg_relevance:.3f}",
            docs_used=len(relevant_docs),
            crag_rewrite=crag_rewrite,
            confidence=response.get("confidence", 0),
        )

        return response

    except Exception as e:
        logger.error("crag_pipeline_error", error=str(e), query=query[:80])
        return {
            "answer": "I'm sorry, I encountered an error processing your question. Please try again.",
            "vehicles_mentioned": [],
            "confidence": 0.0,
            "follow_up_suggestions": ["Try rephrasing your question"],
            "error": str(e),
            "response_time_ms": int((time.time() - start_time) * 1000),
            "cache_hit": False,
        }





def _log_query(
    query: str,
    query_type: str = "unknown",
    cache_hit: bool = False,
    cache_type: str = "miss",
    response_time_ms: int = 0,
    num_docs: int = 0,
    avg_relevance: float = 0.0,
    crag_rewrite: bool = False,
    model_used: str = "",
    tokens_used: int = 0,
    cost_usd: float = 0.0,
) -> None:
    """Log query to PostgreSQL for analytics."""
    try:
        session = SyncSessionLocal()
        log = QueryLog(
            query_text=query,
            query_type=query_type,
            cache_hit=cache_hit,
            cache_type=cache_type,
            response_time_ms=response_time_ms,
            num_docs_retrieved=num_docs,
            avg_relevance_score=avg_relevance,
            crag_rewrite=crag_rewrite,
            model_used=model_used,
            tokens_used=tokens_used,
            cost_usd=cost_usd,
        )
        session.add(log)
        session.commit()
        session.close()
    except Exception as e:
        logger.warning("query_log_error", error=str(e))
