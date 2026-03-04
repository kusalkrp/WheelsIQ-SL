"""
Prime Wheels SL — Gemini Flash answer synthesizer.
Generates structured responses from graded vehicle documents.
"""

import json

import dirtyjson
from google import genai
from google.genai import types

from rag.constraint_extractor import format_constraints_text
from rag.prompts import SYNTHESIS_PROMPT
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()

_client = genai.Client(api_key=settings.gemini_api_key)


from pydantic import BaseModel, Field

class VehicleMention(BaseModel):
    make: str
    model: str
    year: int
    price_lkr: int
    url: str | None = None

class SynthesisResult(BaseModel):
    answer: str
    vehicles_mentioned: list[VehicleMention]
    confidence: float
    follow_up_suggestions: list[str]

def synthesize_answer(query: str, graded_documents: list[dict], constraints: dict | None = None) -> dict:
    """
    Synthesize a final answer from graded documents using Gemini Flash.

    Args:
        query: User's question
        graded_documents: List of graded documents (sorted by relevance)

    Returns:
        Structured response dict with 'answer', 'vehicles_mentioned',
        'confidence', 'follow_up_suggestions'
    """
    # Format documents for the prompt
    doc_texts = []
    for i, doc in enumerate(graded_documents[:10]):  # Top 10 only
        relevance = doc.get("grade", {}).get("relevance") or 0
        relevance = float(relevance)
        meta = doc.get("metadata", {})
        doc_texts.append(
            f"[Document {i+1} | Relevance: {relevance:.2f} | "
            f"{meta.get('make', '?')} {meta.get('model', '')} "
            f"{meta.get('yom', '')}]\n{doc['text']}"
        )

    documents_str = "\n\n".join(doc_texts) if doc_texts else "No relevant listings found."

    constraints_block = format_constraints_text(constraints or {})
    prompt = SYNTHESIS_PROMPT.format(
        query=query,
        constraints_block=constraints_block,
        documents=documents_str,
    )

    try:
        response = _client.models.generate_content(
            model=settings.gemini_flash_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=SynthesisResult,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        parsed = response.parsed
        if not parsed:
            try:
                parsed_dict = json.loads(response.text)
            except json.JSONDecodeError:
                parsed_dict = dict(dirtyjson.loads(response.text))
        else:
            parsed_dict = {"answer": parsed.answer, "vehicles_mentioned": [v.model_dump() for v in getattr(parsed, "vehicles_mentioned", [])], "confidence": getattr(parsed, "confidence", 0.5), "follow_up_suggestions": getattr(parsed, "follow_up_suggestions", [])}

        # Ensure all expected keys exist
        return {
            "answer": parsed_dict.get("answer", "I couldn't generate a response."),
            "vehicles_mentioned": parsed_dict.get("vehicles_mentioned", []),
            "confidence": float(parsed_dict.get("confidence", 0.5)),
            "follow_up_suggestions": parsed_dict.get("follow_up_suggestions", []),
            "model_used": settings.gemini_flash_model,
            "docs_used": len(graded_documents),
        }
    except Exception as e:
        logger.error("synthesis_error", error=str(e))
        return {
            "answer": f"I encountered an error generating the response. Please try again.",
            "vehicles_mentioned": [],
            "confidence": 0.0,
            "follow_up_suggestions": ["Try rephrasing your question"],
            "model_used": settings.gemini_flash_model,
            "error": str(e),
        }
