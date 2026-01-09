"""Evaluation service for RAG quality assessment and query logging."""

from __future__ import annotations

import json
from pathlib import Path

from src.core import get_logger
from src.rag.domain import (
    EvaluationReport,
    EvaluationResult,
    QueryLog,
    ResponseType,
)

logger = get_logger(__name__)


class EvaluationLogger:
    """Logger for RAG query evaluation and analytics."""

    def __init__(
        self,
        log_path: Path | str = "logs/query_logs.jsonl",
        evaluation_log_path: Path | str = "logs/evaluation_logs.jsonl",
    ) -> None:
        """Initialize logger with file paths."""
        self.log_path = Path(log_path)
        self.evaluation_log_path = Path(evaluation_log_path)
        self._ensure_log_dirs()

    def _ensure_log_dirs(self) -> None:
        """Ensure log directories exist."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.evaluation_log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_query(self, log_entry: QueryLog) -> None:
        """Append a query log entry to the JSONL file."""
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(log_entry.model_dump_json() + "\n")
        logger.debug("Logged query: %s", log_entry.query[:50])

    def log_evaluation(self, result: EvaluationResult) -> None:
        """Append an evaluation result to the evaluation log."""
        with self.evaluation_log_path.open("a", encoding="utf-8") as f:
            f.write(result.model_dump_json() + "\n")
        logger.debug("Logged evaluation: %s", result.question_id)

    def read_logs(self) -> list[QueryLog]:
        """Read all query logs from file."""
        if not self.log_path.exists():
            return []

        with self.log_path.open("r", encoding="utf-8") as f:
            return [
                QueryLog.model_validate_json(line)
                for line in f
                if line.strip()
            ]

    def read_evaluation_logs(self) -> list[EvaluationResult]:
        """Read all evaluation results from file."""
        if not self.evaluation_log_path.exists():
            return []

        with self.evaluation_log_path.open("r", encoding="utf-8") as f:
            return [
                EvaluationResult.model_validate_json(line)
                for line in f
                if line.strip()
            ]

    def save_report(
        self, report: EvaluationReport, path: Path | str = "logs/evaluation_report.json"
    ) -> None:
        """Save evaluation report to JSON file."""
        report_path = Path(path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            f.write(report.model_dump_json(indent=2))
        logger.info("Saved evaluation report to %s", report_path)

    def clear_logs(self) -> None:
        """Clear all log files."""
        if self.log_path.exists():
            self.log_path.unlink()
        if self.evaluation_log_path.exists():
            self.evaluation_log_path.unlink()
        logger.info("Cleared all logs")


def determine_response_type(response) -> ResponseType:
    """Determine the type of RAG response."""
    from src.core import (
        GreetingResponse,
        InjectionBlockedResponse,
        NoContextResponse,
    )

    if isinstance(response, GreetingResponse):
        return ResponseType.GREETING
    if isinstance(response, InjectionBlockedResponse):
        return ResponseType.BLOCKED
    if isinstance(response, NoContextResponse):
        return ResponseType.NO_CONTEXT
    return ResponseType.NORMAL


def is_successful_response(response, response_type: ResponseType) -> bool:
    """Determine if a response indicates successful knowledge retrieval."""
    if response_type in (ResponseType.BLOCKED, ResponseType.GREETING, ResponseType.ERROR):
        return False
    if response_type == ResponseType.NO_CONTEXT:
        return False
    return bool(response.sources)


def create_query_log(query: str, response) -> QueryLog:
    """Create a QueryLog from a RAG response."""
    response_type = determine_response_type(response)
    success = is_successful_response(response, response_type)

    return QueryLog(
        query=query,
        chunks_found=len(response.sources) if response.sources else 0,
        response_length=len(response.response),
        success=success,
        sources=response.sources if response.sources else [],
        response_type=response_type,
        response_preview=response.response[:200] if response.response else "",
    )


def calculate_mrr(results: list[EvaluationResult]) -> float:
    """Calculate Mean Reciprocal Rank.

    MRR = (1/|Q|) x Sum(1/rank_i) where rank_i is position of first relevant result.
    For simplicity, we use source_match as relevance indicator.
    """
    if not results:
        return 0.0

    reciprocal_ranks = []
    for r in results:
        if r.expected_success and r.actual_sources:
            if r.source_match:
                reciprocal_ranks.append(1.0)
            else:
                reciprocal_ranks.append(0.0)

    if not reciprocal_ranks:
        return 0.0

    return sum(reciprocal_ranks) / len(reciprocal_ranks)


def evaluate_faithfulness_llm(
    question: str,
    answer: str,
    context: str,
    model_name: str = "gemini-2.0-flash",
) -> tuple[float, bool]:
    """Evaluate faithfulness using LLM-as-Judge.

    Returns:
        tuple: (faithfulness_score 0-1, is_hallucination bool)
    """
    import google.generativeai as genai

    from src.core import settings

    if not context or not answer:
        return 0.0, False

    genai.configure(api_key=settings.models.gemini_api_key)
    model = genai.GenerativeModel(model_name)

    prompt = f"""You are an expert evaluator for RAG systems.

Evaluate the FAITHFULNESS of the Answer based ONLY on the provided Context.

Question: {question}

Context:
{context[:2000]}

Answer: {answer}

Instructions:
1. Check if EVERY claim in the Answer is supported by the Context.
2. Identify any information in the Answer that is NOT in the Context (hallucination).
3. Score from 0.0 to 1.0 where:
   - 1.0 = All claims are fully supported by context
   - 0.5 = Some claims are supported, some are not
   - 0.0 = Answer contradicts context or has no support

Respond ONLY with JSON:
{{"faithfulness": 0.X, "is_hallucination": true/false, "reason": "brief reason"}}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        import json
        import re

        json_match = re.search(r"\{[^}]+\}", text)
        if json_match:
            data = json.loads(json_match.group())
            faithfulness = float(data.get("faithfulness", 0.0))
            is_hallucination = bool(data.get("is_hallucination", False))
            return faithfulness, is_hallucination
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        logger.warning("Faithfulness evaluation failed: %s", e)

    return 0.0, False


def evaluate_relevance_llm(
    question: str,
    answer: str,
    should_answer: bool = True,
    model_name: str = "gemini-2.0-flash",
) -> float:
    """Evaluate answer relevance using LLM-as-Judge.

    Args:
        question: User question
        answer: RAG response
        should_answer: Whether the system IS EXPECTED to answer this question.
                       If False, a refusal ("I don't know") is considered RELEVANT (1.0).
        model_name: Gemini model to use

    Returns:
        float: relevance_score (0-1)
    """
    import re

    import google.generativeai as genai

    from src.core import settings

    if not answer:
        return 0.0

    genai.configure(api_key=settings.models.gemini_api_key)
    model = genai.GenerativeModel(model_name)

    expectation_instr = (
        "The system IS EXPECTED to answer this question."
        if should_answer
        else "The system is EXPECTED TO REFUSE due to lack of knowledge or being out of domain."
    )

    prompt = f"""You are an expert evaluator for RAG systems.

Evaluate the RELEVANCE of the Answer to the Question.
Does the Answer actually address what was asked, considering the system's knowledge constraints?

Question: {question}

Answer: {answer}

Expected Behavior: {expectation_instr}

Instructions:
1. If 'Expected Behavior' is TO ANSWER:
   - 1.0 = Directly answers the question
   - 0.5 = Partially answers or drifts
   - 0.0 = Completely irrelevant or "I don't know"

2. If 'Expected Behavior' is TO REFUSE:
   - 1.0 = Politely refuses, states "I don't know", or explains why it can't answer.
   - 0.0 = Attempts to answer with hallucinated or irrelevant information.

Respond ONLY with JSON:
{{"relevance": 0.X, "reason": "brief reason"}}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()
        json_match = re.search(r"\{[^}]+\}", text)
        if json_match:
            data = json.loads(json_match.group())
            return float(data.get("relevance", 0.0))
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        logger.warning("Relevance evaluation failed: %s", e)

    return 0.0


def calculate_hallucination_rate(results: list[EvaluationResult]) -> float:
    """Calculate rate of hallucinated responses."""
    answered = [r for r in results if r.actual_success]
    if not answered:
        return 0.0

    hallucinations = sum(1 for r in answered if r.is_hallucination)
    return hallucinations / len(answered)

