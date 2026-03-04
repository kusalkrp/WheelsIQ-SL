"""
Prime Wheels SL — Redis CAG (Cache-Augmented Generation).
Provides exact-match and semantic cache for query results.
"""

import hashlib
import json
import time

import numpy as np
import redis

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# ── Redis connection pool ──
_redis_client: redis.Redis | None = None


def get_redis_client() -> redis.Redis:
    """Get or create Redis client (singleton)."""
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.Redis.from_url(
            settings.redis_url,
            decode_responses=True,
        )
    return _redis_client


def _query_hash(query: str) -> str:
    """Generate a deterministic hash for exact-match cache."""
    normalized = query.strip().lower()
    return f"cag:exact:{hashlib.sha256(normalized.encode()).hexdigest()}"


def _semantic_key_prefix() -> str:
    return "cag:semantic:"


# ── Exact-Match Cache ──
def get_exact_cache(query: str) -> dict | None:
    """Check for an exact-match cached response."""
    client = get_redis_client()
    key = _query_hash(query)
    cached = client.get(key)
    if cached:
        logger.info("cache_hit_exact", query=query[:50])
        return json.loads(cached)
    return None


def set_exact_cache(query: str, response: dict, ttl: int | None = None) -> None:
    """Store an exact-match cache entry."""
    client = get_redis_client()
    key = _query_hash(query)
    ttl = ttl or settings.cache_ttl_seconds
    client.setex(key, ttl, json.dumps(response, default=str))


# ── Semantic Cache ──
def get_semantic_cache(query_embedding: list[float]) -> dict | None:
    """
    Check for a semantically similar cached response.
    Uses cosine similarity against stored query embeddings.
    Returns cached response if similarity > threshold.
    """
    client = get_redis_client()
    prefix = _semantic_key_prefix()

    # Get all semantic cache keys (cap to 100 most recent to prevent O(n) growth)
    keys = client.keys(f"{prefix}*:embedding")
    keys = keys[:100]
    if not keys:
        return None

    query_vec = np.array(query_embedding)
    best_match = None
    best_score = 0.0

    for key in keys:
        try:
            stored_vec = np.array(json.loads(client.get(key)))
            # Cosine similarity
            similarity = float(
                np.dot(query_vec, stored_vec)
                / (np.linalg.norm(query_vec) * np.linalg.norm(stored_vec) + 1e-10)
            )
            if similarity > best_score:
                best_score = similarity
                best_match = key
        except Exception:
            continue

    if best_score >= settings.semantic_cache_threshold and best_match:
        # Get the response for this match
        response_key = best_match.replace(":embedding", ":response")
        cached = client.get(response_key)
        if cached:
            logger.info(
                "cache_hit_semantic",
                similarity=f"{best_score:.4f}",
                threshold=settings.semantic_cache_threshold,
            )
            return json.loads(cached)

    return None


def set_semantic_cache(
    query: str,
    query_embedding: list[float],
    response: dict,
    ttl: int | None = None,
) -> None:
    """Store a semantic cache entry (embedding + response)."""
    client = get_redis_client()
    prefix = _semantic_key_prefix()
    ttl = ttl or settings.cache_ttl_seconds
    cache_id = hashlib.md5(query.encode()).hexdigest()[:12]

    # Store embedding
    client.setex(
        f"{prefix}{cache_id}:embedding",
        ttl,
        json.dumps(query_embedding),
    )
    # Store response
    client.setex(
        f"{prefix}{cache_id}:response",
        ttl,
        json.dumps(response, default=str),
    )


# ── Combined Cache Check ──
def check_cache(
    query: str,
    query_embedding: list[float] | None = None,
    skip_semantic: bool = False,
) -> tuple[dict | None, str]:
    """
    Check both exact and semantic caches.

    Args:
        skip_semantic: When True, only check exact cache. Use this for queries with
            numeric constraints (price, year) where semantically similar queries can
            have completely different correct answers.

    Returns:
        (cached_response, cache_type) where cache_type is 'exact', 'semantic', or 'miss'
    """
    start = time.time()

    # 1. Exact match first (fastest)
    result = get_exact_cache(query)
    if result:
        return result, "exact"

    # 2. Semantic match — skip when query has numeric constraints
    if query_embedding and not skip_semantic:
        result = get_semantic_cache(query_embedding)
        if result:
            return result, "semantic"

    latency = (time.time() - start) * 1000
    logger.debug("cache_miss", query=query[:50], latency_ms=f"{latency:.1f}")
    return None, "miss"


def store_cache(
    query: str,
    query_embedding: list[float] | None,
    response: dict,
    skip_semantic: bool = False,
) -> None:
    """Store response in both exact and semantic caches."""
    set_exact_cache(query, response)
    if query_embedding and not skip_semantic:
        set_semantic_cache(query, query_embedding, response)


# ── Cache Stats ──
def get_cache_stats() -> dict:
    """Get cache statistics."""
    client = get_redis_client()
    exact_keys = client.keys("cag:exact:*")
    semantic_keys = client.keys("cag:semantic:*:response")
    info = client.info("memory")

    return {
        "exact_entries": len(exact_keys),
        "semantic_entries": len(semantic_keys),
        "memory_used_mb": round(info.get("used_memory", 0) / 1024 / 1024, 2),
        "ttl_seconds": settings.cache_ttl_seconds,
        "semantic_threshold": settings.semantic_cache_threshold,
    }


def flush_cache() -> int:
    """Clear all CAG cache entries. Returns count of deleted keys."""
    client = get_redis_client()
    keys = client.keys("cag:*")
    if keys:
        return client.delete(*keys)
    return 0
