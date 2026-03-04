"""
Prime Wheels SL — Qdrant dense indexer.
Creates and manages the Qdrant collection for Gemini dense vectors.
"""

import asyncio

from qdrant_client import QdrantClient, models
from qdrant_client.models import Distance, PointStruct, VectorParams

from ingestion.embedder import embed_texts
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_qdrant_client: QdrantClient | None = None


def get_qdrant_client() -> QdrantClient:
    """Get or create a Qdrant client (singleton)."""
    global _qdrant_client
    if _qdrant_client is None:
        _qdrant_client = QdrantClient(url=settings.qdrant_url, timeout=60, check_compatibility=False)
    return _qdrant_client


def create_collection(client: QdrantClient | None = None) -> None:
    """
    Create the dense Qdrant collection.
    Idempotent — safe to call multiple times.
    """
    client = client or get_qdrant_client()
    collection_name = settings.qdrant_collection

    # Check if collection already exists
    collections = client.get_collections().collections
    if any(c.name == collection_name for c in collections):
        logger.info("collection_exists", collection=collection_name)
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(
            size=settings.embedding_dimension,
            distance=Distance.COSINE,
        )
    )

    # Create payload indexes for filtering
    for field in [
        "category", "make", "model", "yom", "price_lkr",
        "fuel_type", "transmission", "district", "province", "is_active",
    ]:
        try:
            field_type = models.PayloadSchemaType.KEYWORD
            if field in ("yom", "price_lkr", "mileage_km", "engine_cc"):
                field_type = models.PayloadSchemaType.INTEGER
                if field == "price_lkr":
                    field_type = models.PayloadSchemaType.FLOAT

            client.create_payload_index(
                collection_name=collection_name,
                field_name=field,
                field_schema=field_type,
            )
        except Exception as e:
            logger.warning("payload_index_error", field=field, error=str(e))

    logger.info("collection_created", collection=collection_name)


async def index_documents(
    texts: list[str],
    metadatas: list[dict],
    ids: list[str],
    batch_size: int = 100,
    client: QdrantClient | None = None,
) -> int:
    """
    Embed and index documents into Qdrant with dense vectors.

    Args:
        texts: Document texts to embed
        metadatas: Payload dicts for each document
        ids: Unique IDs for each point
        batch_size: Batch size for upserting

    Returns:
        Number of points indexed
    """
    client = client or get_qdrant_client()
    collection_name = settings.qdrant_collection
    total_indexed = 0

    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i : i + batch_size]
        batch_metas = metadatas[i : i + batch_size]
        batch_ids = ids[i : i + batch_size]

        # Embed asynchronously
        embeddings = await embed_texts(batch_texts)

        # Create Qdrant points
        points = []
        for j, (text, meta, doc_id) in enumerate(
            zip(batch_texts, batch_metas, batch_ids)
        ):
            point = PointStruct(
                id=abs(hash(doc_id)) % (2**63),  # Convert string ID to int
                vector=embeddings["dense"][j],
                payload={**meta, "text": text},
            )
            points.append(point)

        # Upsert batch
        client.upsert(
            collection_name=collection_name,
            points=points,
        )

        total_indexed += len(points)
        logger.info(
            "batch_indexed",
            batch=i // batch_size + 1,
            points=len(points),
            total=total_indexed,
        )

    logger.info("indexing_complete", total=total_indexed)
    return total_indexed


async def dense_search(
    query_text: str,
    top_k: int = 10,
    filters: dict | None = None,
    client: QdrantClient | None = None,
    query_vector: list[float] | None = None,
) -> list[dict]:
    """
    Perform dense search on Qdrant.

    Args:
        query_text: User query (used for embedding if query_vector not provided)
        top_k: Number of results
        filters: Qdrant payload filters (e.g., {"make": "Toyota"})
        query_vector: Pre-computed dense vector (skips re-embedding if provided)

    Returns:
        List of dicts with 'text', 'metadata', 'score'
    """
    client = client or get_qdrant_client()
    collection_name = settings.qdrant_collection

    # Use pre-computed vector or embed now
    if query_vector is not None:
        dense_vec = query_vector
    else:
        query_embeddings = await embed_texts([query_text])
        dense_vec = query_embeddings["dense"][0]

    # Build filter
    qdrant_filter = None
    if filters:
        conditions = []
        for key, value in filters.items():
            if isinstance(value, list):
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchAny(any=value),
                    )
                )
            elif isinstance(value, dict) and ("gte" in value or "lte" in value):
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        range=models.Range(
                            gte=value.get("gte"),
                            lte=value.get("lte"),
                        ),
                    )
                )
            else:
                conditions.append(
                    models.FieldCondition(
                        key=key,
                        match=models.MatchValue(value=value),
                    )
                )
        qdrant_filter = models.Filter(must=conditions)

    # Dense search (run sync client in thread to avoid blocking the event loop)
    search_response = await asyncio.to_thread(
        client.query_points,
        collection_name=collection_name,
        query=dense_vec,
        query_filter=qdrant_filter,
        limit=top_k,
        with_payload=True,
    )

    # Format results
    results = []
    for result in search_response.points:
        results.append({
            "text": result.payload.get("text", ""),
            "metadata": {k: v for k, v in result.payload.items() if k != "text"},
            "dense_score": result.score,
        })

    return results
