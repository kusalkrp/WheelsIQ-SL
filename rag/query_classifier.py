"""
Prime Wheels SL — Query classifier.
Lightweight classification for cache routing and query-specific handling.
"""

import json

from google import genai
from google.genai import types

from rag.constraint_extractor import format_constraints_text
from rag.prompts import QUERY_CLASSIFY_PROMPT, QUERY_REWRITE_PROMPT
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client = genai.Client(api_key=settings.gemini_api_key)


def classify_query(query: str) -> str:
    """
    Classify a query into a predefined category.

    Returns one of: PRICE_CHECK, COMPARISON, RECOMMENDATION,
    MARKET_TREND, SPECS_LOOKUP, AVAILABILITY, GENERAL
    """
    prompt = QUERY_CLASSIFY_PROMPT.format(query=query)

    try:
        response = _client.models.generate_content(
            model=settings.gemini_flash_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                max_output_tokens=20,
            ),
        )
        category = response.text.strip().upper()
        valid = {
            "PRICE_CHECK", "COMPARISON", "RECOMMENDATION",
            "MARKET_TREND", "SPECS_LOOKUP", "AVAILABILITY", "GENERAL",
        }
        return category if category in valid else "GENERAL"
    except Exception as e:
        logger.warning("classify_error", error=str(e))
        return "GENERAL"


def rewrite_query(original_query: str, avg_relevance: float, constraints: dict | None = None) -> str:
    """
    Rewrite a query that didn't retrieve relevant results.

    Args:
        original_query: The original user query
        avg_relevance: Average relevance score of retrieved docs

    Returns:
        Rewritten query string
    """
    constraints_block = format_constraints_text(constraints or {})
    prompt = QUERY_REWRITE_PROMPT.format(
        original_query=original_query,
        avg_relevance=avg_relevance,
        constraints_block=constraints_block,
    )

    try:
        response = _client.models.generate_content(
            model=settings.gemini_flash_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=100,
            ),
        )
        rewritten = response.text.strip().strip('"').strip("'")
        logger.info(
            "query_rewritten",
            original=original_query,
            rewritten=rewritten,
        )
        return rewritten
    except Exception as e:
        logger.warning("rewrite_error", error=str(e))
        return original_query  # Fallback to original
