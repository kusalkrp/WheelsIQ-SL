"""
Prime Wheels SL — Multi-strategy chunking for vehicle documents.
Implements 5 chunking strategies and lets RAGAS evaluation pick the best.
"""

from llama_index.core import Document
from llama_index.core.node_parser import (
    HierarchicalNodeParser,
    SentenceSplitter,
    SentenceWindowNodeParser,
    SemanticSplitterNodeParser,
)
from llama_index.core.schema import BaseNode

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


def chunk_fixed_size(
    documents: list[Document],
    chunk_size: int = 512,
    chunk_overlap: int = 50,
) -> list[BaseNode]:
    """
    Strategy 1: Fixed-size sentence splitting.
    Best for: Uniform processing, predictable chunk sizes.
    """
    splitter = SentenceSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    logger.info("chunking_fixed_size", nodes=len(nodes), chunk_size=chunk_size)
    return nodes


def chunk_sliding_window(
    documents: list[Document],
    window_size: int = 3,
    chunk_size: int = 512,
) -> list[BaseNode]:
    """
    Strategy 2: Sliding window with sentence context.
    Best for: Preserving surrounding context for each chunk.
    """
    parser = SentenceWindowNodeParser.from_defaults(
        window_size=window_size,
        window_metadata_key="window",
        original_text_metadata_key="original_text",
    )
    nodes = parser.get_nodes_from_documents(documents)
    logger.info("chunking_sliding_window", nodes=len(nodes), window_size=window_size)
    return nodes


def chunk_semantic(
    documents: list[Document],
    breakpoint_percentile: int = 85,
) -> list[BaseNode]:
    """
    Strategy 3: Semantic splitting using embeddings.
    Best for: Grouping semantically related content together.
    Requires embedding model to detect topic boundaries.
    """
    from llama_index.embeddings.huggingface import HuggingFaceEmbedding

    embed_model = HuggingFaceEmbedding(model_name=settings.embedding_model)
    splitter = SemanticSplitterNodeParser(
        buffer_size=1,
        breakpoint_percentile_threshold=breakpoint_percentile,
        embed_model=embed_model,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    logger.info("chunking_semantic", nodes=len(nodes))
    return nodes


def chunk_parent_child(
    documents: list[Document],
    parent_chunk_size: int = 2048,
    child_chunk_size: int = 256,
) -> list[BaseNode]:
    """
    Strategy 4: Hierarchical parent-child nodes.
    Best for: Retrieval on fine-grained child, synthesis on parent context.
    This is expected to perform best for the vehicle data.
    """
    parser = HierarchicalNodeParser.from_defaults(
        chunk_sizes=[parent_chunk_size, child_chunk_size],
    )
    nodes = parser.get_nodes_from_documents(documents)
    logger.info(
        "chunking_parent_child",
        nodes=len(nodes),
        parent_size=parent_chunk_size,
        child_size=child_chunk_size,
    )
    return nodes


def chunk_per_vehicle(documents: list[Document]) -> list[BaseNode]:
    """
    Strategy 5: One chunk per vehicle listing (no splitting).
    Best for: Short vehicle listings that are already self-contained.
    Works well when individual listings are < 512 tokens.
    """
    splitter = SentenceSplitter(
        chunk_size=4096,  # Large enough to keep whole listing intact
        chunk_overlap=0,
    )
    nodes = splitter.get_nodes_from_documents(documents)
    logger.info("chunking_per_vehicle", nodes=len(nodes))
    return nodes


# ── Factory ──
CHUNKING_STRATEGIES = {
    "fixed_size": chunk_fixed_size,
    "sliding_window": chunk_sliding_window,
    "semantic": chunk_semantic,
    "parent_child": chunk_parent_child,
    "per_vehicle": chunk_per_vehicle,
}


def get_chunker(strategy: str):
    """Get a chunking function by name."""
    if strategy not in CHUNKING_STRATEGIES:
        raise ValueError(
            f"Unknown strategy '{strategy}'. "
            f"Available: {list(CHUNKING_STRATEGIES.keys())}"
        )
    return CHUNKING_STRATEGIES[strategy]
