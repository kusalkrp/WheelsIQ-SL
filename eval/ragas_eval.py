"""
Prime Wheels SL — RAGAS Evaluation Runner.
Evaluates the CRAG pipeline against the test question set.
"""

import json
import time
from pathlib import Path

from rag.crag_workflow import run_crag_pipeline
from shared.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def run_evaluation(
    questions_file: str = "eval/questions.json",
    output_file: str = "eval/results.json",
    skip_cache: bool = True,
) -> dict:
    """
    Run the CRAG pipeline against all test questions and collect metrics.

    Args:
        questions_file: Path to the test questions JSON
        output_file: Path to save results
        skip_cache: Bypass cache for honest evaluation

    Returns:
        Summary statistics dict
    """
    # Load questions
    with open(questions_file) as f:
        questions = json.load(f)

    logger.info("evaluation_start", total_questions=len(questions))

    results = []
    total_time = 0
    confidence_scores = []
    relevance_scores = []
    cache_hits = 0
    crag_rewrites = 0

    for i, q in enumerate(questions):
        query = q["question"]
        expected_type = q["type"]

        logger.info(f"evaluating", question=i+1, total=len(questions), type=expected_type)

        start = time.time()
        response = run_crag_pipeline(query=query, skip_cache=skip_cache)
        elapsed = (time.time() - start) * 1000

        total_time += elapsed

        result = {
            "question_id": i + 1,
            "question": query,
            "expected_type": expected_type,
            "detected_type": response.get("query_type", "unknown"),
            "answer": response.get("answer", ""),
            "confidence": response.get("confidence", 0),
            "avg_relevance": response.get("avg_relevance", 0),
            "num_docs": response.get("num_docs_retrieved", 0),
            "crag_rewrite": response.get("crag_rewrite", False),
            "cache_hit": response.get("cache_hit", False),
            "response_time_ms": int(elapsed),
            "vehicles_mentioned": len(response.get("vehicles_mentioned", [])),
            "has_error": "error" in response,
        }

        results.append(result)
        confidence_scores.append(result["confidence"])
        relevance_scores.append(result["avg_relevance"] or 0)
        if result["cache_hit"]:
            cache_hits += 1
        if result["crag_rewrite"]:
            crag_rewrites += 1

    # Calculate summary stats
    summary = {
        "total_questions": len(questions),
        "avg_confidence": round(sum(confidence_scores) / len(confidence_scores), 3),
        "avg_relevance": round(sum(relevance_scores) / len(relevance_scores), 3),
        "avg_response_time_ms": round(total_time / len(questions)),
        "total_time_seconds": round(total_time / 1000, 1),
        "cache_hit_rate": round(cache_hits / len(questions) * 100, 1),
        "crag_rewrite_rate": round(crag_rewrites / len(questions) * 100, 1),
        "error_count": sum(1 for r in results if r["has_error"]),
        "type_accuracy": sum(
            1 for r in results
            if r["detected_type"] == r["expected_type"]
        ) / len(results) * 100,
        "by_type": {},
    }

    # Per-type breakdown
    for qtype in ["clear", "vague", "complex", "comparison", "edge"]:
        type_results = [r for r in results if r["expected_type"] == qtype]
        if type_results:
            summary["by_type"][qtype] = {
                "count": len(type_results),
                "avg_confidence": round(
                    sum(r["confidence"] for r in type_results) / len(type_results), 3
                ),
                "avg_relevance": round(
                    sum(r["avg_relevance"] for r in type_results) / len(type_results), 3
                ),
                "avg_time_ms": round(
                    sum(r["response_time_ms"] for r in type_results) / len(type_results)
                ),
            }

    # Save results
    output = {"summary": summary, "results": results}
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2, default=str)

    logger.info("evaluation_complete", **summary)
    print("\n" + "=" * 60)
    print("RAGAS EVALUATION RESULTS")
    print("=" * 60)
    print(f"Questions:          {summary['total_questions']}")
    print(f"Avg Confidence:     {summary['avg_confidence']}")
    print(f"Avg Relevance:      {summary['avg_relevance']}")
    print(f"Avg Response Time:  {summary['avg_response_time_ms']}ms")
    print(f"CRAG Rewrite Rate:  {summary['crag_rewrite_rate']}%")
    print(f"Errors:             {summary['error_count']}")
    print(f"Type Accuracy:      {summary['type_accuracy']:.1f}%")
    print("=" * 60)

    return summary


if __name__ == "__main__":
    run_evaluation()
