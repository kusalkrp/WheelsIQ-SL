"""
Prime Wheels SL — Gemini Pro document grader for CRAG.
Grades each retrieved document for relevance to the query.
"""

import json

import dirtyjson
from google import genai
from google.genai import types

from rag.constraint_extractor import format_constraints_text
from rag.prompts import GRADING_PROMPT
from shared.config import get_settings
from shared.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()
_client = genai.Client(api_key=settings.gemini_api_key)

# Configure Gemini
from pydantic import BaseModel
from typing import List, Literal

class DocumentGrade(BaseModel):
    document_id: int
    relevance: float
    reasoning: str

class BatchGradingResult(BaseModel):
    query_type: Literal["clear", "vague", "complex", "edge"]
    grades: List[DocumentGrade]

def grade_documents(query: str, documents: list[dict], constraints: dict | None = None) -> list[dict]:
    """
    Grade multiple documents and return sorted by relevance.

    Args:
        query: User's question
        documents: List of dicts with 'text' and 'metadata'

    Returns:
        Same documents with added 'grade' field, sorted by relevance DESC
    """
    graded = []
    
    # We only grade the top 5 documents via the LLM to save tokens and time
    docs_to_grade = documents[:5]
    docs_fallback = documents[5:]
    
    if docs_to_grade:
        doc_texts = []
        for i, doc in enumerate(docs_to_grade):
            doc_texts.append(f"--- Document {i} ---\n{doc['text'][:1500]}")
        
        constraints_block = format_constraints_text(constraints or {})
        prompt = GRADING_PROMPT.format(
            query=query,
            constraints_block=constraints_block,
            documents="\n\n".join(doc_texts)
        )
        
        try:
            response = _client.models.generate_content(
                model=settings.gemini_flash_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                    response_mime_type="application/json",
                    response_schema=BatchGradingResult,
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
                parsed_dict = {
                    "query_type": getattr(parsed, "query_type", "clear"),
                    "grades": [g.model_dump() for g in getattr(parsed, "grades", [])]
                }
            
            # Map grades back to documents
            q_type = parsed_dict.get("query_type", "clear")
            grades = {g.get("document_id", -1): g for g in parsed_dict.get("grades", [])}
            
            for i, doc in enumerate(docs_to_grade):
                g = grades.get(i, {})
                doc["grade"] = {
                    "relevance": float(g.get("relevance", 0.5)),
                    "query_type": q_type,
                    "reasoning": g.get("reasoning", "")
                }
                graded.append(doc)
                logger.debug("document_graded", relevance=doc["grade"]["relevance"], vehicle=doc.get("metadata", {}).get("make", "?"))
                
        except Exception as e:
            logger.error("grading_error", error=str(e))
            for i, doc in enumerate(docs_to_grade):
                doc["grade"] = {"relevance": 0.0, "query_type": "clear", "reasoning": f"Grading failed: {e}"}
                graded.append(doc)

    # Apply fallback to remaining documents
    for doc in docs_fallback:
        doc["grade"] = {"relevance": 0.5, "query_type": "clear", "reasoning": "Fallback (Rate limit prevention)"}
        graded.append(doc)

    # Sort by relevance descending
    graded.sort(key=lambda x: x["grade"]["relevance"], reverse=True)

    avg_relevance = (
        sum(d["grade"]["relevance"] for d in graded) / len(graded) if graded else 0
    )
    logger.info(
        "grading_complete",
        total_docs=len(graded),
        avg_relevance=f"{avg_relevance:.3f}",
        query_type=graded[0]["grade"]["query_type"] if graded else "unknown",
    )

    return graded
