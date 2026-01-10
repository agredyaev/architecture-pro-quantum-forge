"""Automated evaluation script for RAG bot quality assessment."""

from __future__ import annotations

import json
import time

import torch

from src.core import EvaluationError, get_logger, settings, setup_logging
from src.rag.domain import (
    EvaluationMetrics,
    EvaluationReport,
    EvaluationResult,
)
from src.rag.infrastructure.chroma_repository import ChromaRepository
from src.rag.services.embeddings import EmbeddingService
from src.rag.services.evaluation import (
    EvaluationLogger,
    calculate_hallucination_rate,
    calculate_mrr,
    create_query_log,
    determine_response_type,
    evaluate_faithfulness_llm,
    evaluate_relevance_llm,
    is_successful_response,
)
from src.rag.services.rag_service import RAGService

logger = get_logger(__name__)




def load_golden_questions() -> list[dict]:
    """Load golden questions from JSON file."""
    if not settings.paths.golden_questions_file.exists():
        msg = f"Golden questions file not found: {settings.paths.golden_questions_file}"
        raise FileNotFoundError(msg)

    with settings.paths.golden_questions_file.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("questions", [])


def evaluate_single_question(
    rag: RAGService,
    question_data: dict,
    eval_logger: EvaluationLogger,
) -> EvaluationResult:
    """Evaluate a single golden question against the RAG bot."""
    question_id = question_data["id"]
    question = question_data["question"]
    expected_success = question_data["expected_success"]
    expected_sources = question_data.get("expected_sources", [])

    logger.info("Evaluating [%s]: %s", question_id, question[:50])

    start_time = time.perf_counter()

    try:
        response = rag.generate(
            query=question,
            use_few_shot=True,
            use_cot=True,
            top_k=settings.rag.top_k_rerank,
        )
    except EvaluationError as e:
        logger.exception("Error evaluating question %s", question_id)
        return EvaluationResult(
            question_id=question_id,
            question=question,
            expected_success=expected_success,
            actual_success=False,
            correct=not expected_success,
            response_preview=f"ERROR: {e!s}",
        )

    latency_ms = (time.perf_counter() - start_time) * 1000
    response_type = determine_response_type(response)
    actual_success = is_successful_response(response, response_type)

    correct = actual_success == expected_success

    actual_sources = response.sources if response.sources else []
    source_match = False
    if expected_sources and actual_sources:
        source_match = any(
            exp in act or act in exp
            for exp in expected_sources
            for act in actual_sources
        )
    elif not expected_sources and not actual_sources:
        source_match = True

    retrieved_context = ""
    if hasattr(response, "context") and response.context:
        retrieved_context = str(response.context)
    elif actual_sources:
        retrieved_context = f"Sources: {', '.join(actual_sources)}"

    faithfulness_score = 0.0
    faithfulness_reason = ""
    is_hallucination = False
    if actual_success and response.response and retrieved_context:
        faithfulness_score, is_hallucination, faithfulness_reason = evaluate_faithfulness_llm(
            question=question,
            answer=response.response,
            context=retrieved_context,
        )

    relevance_score = 0.0
    if response.response:
        relevance_score = evaluate_relevance_llm(
            question=question,
            answer=response.response,
            should_answer=expected_success,
        )

    log_context = retrieved_context
    if not settings.evaluation.log_full_context:
        log_limit = settings.evaluation.log_context_chars
        if log_limit > 0:
            log_context = retrieved_context[:log_limit]
        else:
            log_context = ""

    response_full = (
        response.response if settings.evaluation.log_full_response else ""
    )
    if not settings.evaluation.log_faithfulness_reason:
        faithfulness_reason = ""

    result = EvaluationResult(
        question_id=question_id,
        question=question,
        expected_success=expected_success,
        actual_success=actual_success,
        correct=correct,
        expected_sources=expected_sources,
        actual_sources=actual_sources,
        source_match=source_match,
        response_preview=response.response[:200] if response.response else "",
        response_full=response_full,
        response_type=response_type,
        latency_ms=latency_ms,
        faithfulness_score=faithfulness_score,
        faithfulness_reason=faithfulness_reason,
        relevance_score=relevance_score,
        is_hallucination=is_hallucination,
        retrieved_context=log_context,
    )

    eval_logger.log_evaluation(result)

    query_log = create_query_log(question, response)
    eval_logger.log_query(query_log)

    return result


def calculate_metrics(results: list[EvaluationResult]) -> EvaluationMetrics:
    """Calculate aggregated evaluation metrics."""
    if not results:
        return EvaluationMetrics()

    total = len(results)
    expected_success = [r for r in results if r.expected_success]
    expected_failure = [r for r in results if not r.expected_success]

    if expected_success:
        answer_rate = sum(1 for r in expected_success if r.actual_success) / len(expected_success)
    else:
        answer_rate = 0.0

    if expected_failure:
        rejection_count = sum(1 for r in expected_failure if not r.actual_success)
        correct_rejection_rate = rejection_count / len(expected_failure)
    else:
        correct_rejection_rate = 1.0

    answered = [r for r in results if r.actual_success]
    if answered:
        source_accuracy = sum(1 for r in answered if r.source_match) / len(answered)
    else:
        source_accuracy = 0.0

    coverage_score = (answer_rate * 0.4 + correct_rejection_rate * 0.3 + source_accuracy * 0.3)

    avg_latency = sum(r.latency_ms for r in results) / total

    precision_at_k = source_accuracy
    recall_at_k = answer_rate

    mrr = calculate_mrr(results)

    faithfulness = (
        sum(r.faithfulness_score for r in answered) / len(answered)
        if answered
        else 0.0
    )

    relevance = sum(r.relevance_score for r in results) / total

    hallucination_rate = calculate_hallucination_rate(results)

    return EvaluationMetrics(
        total_questions=total,
        answer_rate=round(answer_rate, 4),
        correct_rejection_rate=round(correct_rejection_rate, 4),
        source_accuracy=round(source_accuracy, 4),
        coverage_score=round(coverage_score, 4),
        avg_latency_ms=round(avg_latency, 2),
        precision_at_k=round(precision_at_k, 4),
        recall_at_k=round(recall_at_k, 4),
        mrr=round(mrr, 4),
        faithfulness=round(faithfulness, 4),
        relevance=round(relevance, 4),
        hallucination_rate=round(hallucination_rate, 4),
    )


def identify_gaps(results: list[EvaluationResult]) -> list[str]:
    """Identify topics with poor coverage."""
    gaps = []

    for r in results:
        if r.expected_success and not r.actual_success:
            gaps.append(f"Missing coverage: {r.question[:60]}...")
        elif r.actual_success and not r.correct:
            gaps.append(f"Unexpected answer (possible hallucination): {r.question[:40]}...")

    return gaps





def generate_recommendations(
    results: list[EvaluationResult],
    metrics: EvaluationMetrics,
) -> list[str]:
    """Generate recommendations based on evaluation results."""
    _ = results  # Not used in current implementation
    recs = []

    if metrics.answer_rate < settings.evaluation.min_answer_rate:
        threshold_pct = f"{settings.evaluation.min_answer_rate:.0%}"
        recs.append(
            f"Answer rate ({metrics.answer_rate:.0%}) is below {threshold_pct}. "
            "Consider expanding knowledge base documentation."
        )

    if metrics.correct_rejection_rate < settings.evaluation.min_rejection_rate:
        threshold_pct = f"{settings.evaluation.min_rejection_rate:.0%}"
        rejection_pct = f"{metrics.correct_rejection_rate:.0%}"
        recs.append(
            f"Correct rejection rate ({rejection_pct}) is below {threshold_pct}. "
            "Review prompting strategy to better handle out-of-domain questions."
        )

    if metrics.source_accuracy < settings.evaluation.min_source_accuracy:
        threshold_pct = f"{settings.evaluation.min_source_accuracy:.0%}"
        recs.append(
            f"Source accuracy ({metrics.source_accuracy:.0%}) is below {threshold_pct}. "
            "Consider improving chunking strategy and retrieval parameters."
        )

    if metrics.avg_latency_ms > settings.evaluation.max_latency_ms:
        threshold = settings.evaluation.max_latency_ms
        recs.append(
            f"Average latency ({metrics.avg_latency_ms:.0f}ms) exceeds {threshold}ms threshold. "
            "Consider optimizing retrieval or using smaller embedding model."
        )

    if not recs:
        recs.append("All metrics are within acceptable ranges. No immediate improvements needed.")

    return recs


def run_evaluation(rag: RAGService) -> EvaluationReport:
    """Run full evaluation on golden questions set."""
    eval_logger = EvaluationLogger(
        log_path="logs/query_logs.jsonl",
        evaluation_log_path=settings.paths.evaluation_log_file,
    )

    eval_logger.clear_logs()

    questions = load_golden_questions()
    logger.info("Loaded %d golden questions", len(questions))

    question_filter = {q.strip() for q in settings.evaluation.question_ids if q.strip()}
    if question_filter:
        questions = [q for q in questions if q.get("id") in question_filter]
        logger.info(
            "Filtered to %d questions: %s",
            len(questions),
            ", ".join(sorted(question_filter)),
        )

    results: list[EvaluationResult] = []
    delay = settings.evaluation.question_delay_seconds
    for i, q in enumerate(questions):
        result = evaluate_single_question(rag, q, eval_logger)
        results.append(result)

        status = "✓" if result.correct else "✗"
        print(f"  [{status}] {result.question_id}: {result.question[:50]}...")

        if delay > 0 and i < len(questions) - 1:
            time.sleep(delay)

    metrics = calculate_metrics(results)
    gaps = identify_gaps(results)
    recommendations = generate_recommendations(results, metrics)

    report = EvaluationReport(
        metrics=metrics,
        results=results,
        gaps_identified=gaps,
        recommendations=recommendations,
    )

    eval_logger.save_report(report, settings.paths.evaluation_report_file)

    return report


def print_report(report: EvaluationReport) -> None:
    """Print evaluation report to console."""
    print("\n" + "=" * 70)
    print("EVALUATION REPORT")
    print("=" * 70)

    m = report.metrics
    print(f"\nTotal Questions: {m.total_questions}")
    print(f"Answer Rate: {m.answer_rate:.1%}")
    print(f"Correct Rejection Rate: {m.correct_rejection_rate:.1%}")
    print(f"Source Accuracy: {m.source_accuracy:.1%}")
    print(f"Coverage Score: {m.coverage_score:.1%}")
    print(f"MRR: {m.mrr:.3f}")
    print(f"Faithfulness: {m.faithfulness:.1%}")
    print(f"Relevance: {m.relevance:.1%}")
    print(f"Hallucination Rate: {m.hallucination_rate:.1%}")
    print(f"Average Latency: {m.avg_latency_ms:.0f}ms")

    if report.gaps_identified:
        print("\n" + "-" * 40)
        print("GAPS IDENTIFIED:")
        for gap in report.gaps_identified:
            print(f"  • {gap}")

    if report.recommendations:
        print("\n" + "-" * 40)
        print("RECOMMENDATIONS:")
        for rec in report.recommendations:
            print(f"  • {rec}")

    print("\n" + "=" * 70)
    print(f"Report saved to: {settings.paths.evaluation_report_file}")
    print(f"Logs saved to: {settings.paths.evaluation_log_file}")


def main() -> None:
    """Run RAG evaluation."""
    setup_logging()

    if not settings.models.gemini_api_key:
        print("ERROR: Set GEMINI_API_KEY in .env file")
        return

    device = "mps" if torch.backends.mps.is_available() else "cpu"
    print(f"Initializing RAG service on {device}...")

    repository = ChromaRepository(persist_path=settings.vector_db.chroma_db_path)
    embedding_service = EmbeddingService(device=device)
    rag = RAGService(
        repository=repository,
        embedding_service=embedding_service,
    )

    print(f"Loaded index with {repository.count()} vectors")
    print("\nRunning evaluation on golden questions...")
    print("-" * 70)

    report = run_evaluation(rag)
    print_report(report)


if __name__ == "__main__":
    main()
