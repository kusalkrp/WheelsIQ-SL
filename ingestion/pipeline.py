"""
Prime Wheels SL — End-to-end ingestion pipeline.
Loads vehicles from PostgreSQL → chunks → embeds → indexes in Qdrant.
"""

from ingestion.chunkers import get_chunker
from ingestion.document_builder import load_vehicles_as_documents
from ingestion.qdrant_indexer import create_collection, index_documents
from shared.logging import get_logger

logger = get_logger(__name__)


def run_ingestion(
    category: str | None = None,
    chunking_strategy: str = "per_vehicle",
    limit: int | None = None,
) -> dict:
    """
    Full ingestion pipeline:
    1. Load vehicles from PostgreSQL
    2. Convert to LlamaIndex Documents
    3. Chunk using selected strategy
    4. Embed and index in Qdrant

    Args:
        category: Vehicle category (None = all)
        chunking_strategy: One of: fixed_size, sliding_window, semantic, parent_child, per_vehicle
        limit: Max vehicles to process

    Returns:
        Stats dict
    """
    logger.info(
        "ingestion_start",
        category=category,
        strategy=chunking_strategy,
        limit=limit,
    )

    # Step 1: Load from PostgreSQL
    documents = load_vehicles_as_documents(
        category=category,
        active_only=True,
        limit=limit,
    )
    logger.info("documents_loaded", count=len(documents))

    if not documents:
        return {"status": "no_documents", "count": 0}

    # Step 2: Chunk
    chunker = get_chunker(chunking_strategy)
    nodes = chunker(documents)
    logger.info("chunks_created", count=len(nodes), strategy=chunking_strategy)

    # Step 3: Prepare for Qdrant
    texts = [node.get_content() for node in nodes]
    metadatas = [node.metadata for node in nodes]
    ids = [node.node_id for node in nodes]

    import asyncio

    # Step 4: Ensure collection exists
    create_collection()

    # Step 5: Index
    indexed = asyncio.run(index_documents(texts, metadatas, ids))

    stats = {
        "status": "completed",
        "vehicles_loaded": len(documents),
        "chunks_created": len(nodes),
        "chunks_indexed": indexed,
        "strategy": chunking_strategy,
        "category": category,
    }
    logger.info("ingestion_complete", **stats)
    return stats
