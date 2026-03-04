"""
Prime Wheels SL — Embedding module using Google Gemini API.
Provides dense embeddings for Qdrant search.
"""

from llama_index.embeddings.google_genai import GoogleGenAIEmbedding

from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

# Singleton model instance
_model: GoogleGenAIEmbedding | None = None


def get_embedding_model() -> GoogleGenAIEmbedding:
    """Get or create the Gemini embedding model (singleton)."""
    global _model
    if _model is None:
        logger.info("loading_embedding_model", model=settings.embedding_model)
        _model = GoogleGenAIEmbedding(
            model_name=settings.embedding_model,
            api_key=settings.gemini_api_key,
        )
        logger.info("embedding_model_loaded")
    return _model


async def embed_texts(
    texts: list[str],
    batch_size: int = 32, # Batch size used loosely, mostly for compat
) -> dict:
    """
    Embed a list of texts using Gemini API.
    
    Args:
        texts: List of strings to embed
        batch_size: Not strictly used for Gemini as much as local models, 
                    but kept for signature compatibility.

    Returns:
        Dict with keys: 'dense'
        - dense: list of list[float] (768-dim)
    """
    model = get_embedding_model()

    # LlamaIndex Gemini wrapper handles async batching usually well.
    # We await the text embeddings
    dense_vecs = await model.aget_text_embedding_batch(texts)

    output = {"dense": dense_vecs}

    logger.info("texts_embedded", count=len(texts), dense=True, sparse=False)
    return output


async def embed_query(query: str) -> dict:
    """Embed a single query for retrieval. Returns dict with 'dense'."""
    model = get_embedding_model()
    dense_vec = await model.aget_query_embedding(query)
    return {"dense": [dense_vec]}
