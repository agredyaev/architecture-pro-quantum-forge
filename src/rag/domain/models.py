"""Domain models for evaluation and metrics."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field


class ResponseType(str, Enum):
    """Types of RAG responses."""

    NORMAL = "normal"
    NO_CONTEXT = "no_context"
    BLOCKED = "blocked"
    GREETING = "greeting"
    ERROR = "error"


class QueryLog(BaseModel):
    """Model for logging RAG queries and responses."""

    query: str = Field(..., description="User query text")
    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat(),
        description="ISO format timestamp",
    )
    chunks_found: int = Field(default=0, description="Number of retrieved chunks")
    response_length: int = Field(default=0, description="Length of generated response")
    success: bool = Field(default=False, description="Whether query was answered")
    sources: list[str] = Field(default_factory=list, description="Source documents")
    response_type: ResponseType = Field(
        default=ResponseType.NORMAL, description="Type of response"
    )
    response_preview: str = Field(
        default="", description="First 200 chars of response"
    )


class EvaluationResult(BaseModel):
    """Result of evaluating a single golden question."""

    question_id: str
    question: str
    expected_success: bool
    actual_success: bool
    correct: bool = Field(
        default=False, description="Whether actual matches expected"
    )
    expected_sources: list[str] = Field(default_factory=list)
    actual_sources: list[str] = Field(default_factory=list)
    source_match: bool = Field(
        default=False, description="Whether sources match expectations"
    )
    response_preview: str = Field(default="")
    response_type: ResponseType = ResponseType.NORMAL
    latency_ms: float = Field(default=0.0, description="Response latency in ms")
    faithfulness_score: float = Field(
        default=0.0, description="LLM-judged faithfulness (0-1)"
    )
    relevance_score: float = Field(
        default=0.0, description="LLM-judged relevance (0-1)"
    )
    is_hallucination: bool = Field(
        default=False, description="Whether response contains hallucination"
    )
    retrieved_context: str = Field(
        default="", description="Context used for generation"
    )


class EvaluationMetrics(BaseModel):
    """Aggregated evaluation metrics."""

    total_questions: int = 0
    answer_rate: float = Field(
        default=0.0, description="% of questions with successful answers"
    )
    correct_rejection_rate: float = Field(
        default=0.0, description="% of correct 'I don't know' responses"
    )
    source_accuracy: float = Field(
        default=0.0, description="% of correct source matches"
    )
    coverage_score: float = Field(
        default=0.0, description="Overall coverage score (0-1)"
    )
    avg_latency_ms: float = Field(default=0.0, description="Average response latency")
    precision_at_k: float = Field(default=0.0, description="Precision@k for retrieval")
    recall_at_k: float = Field(default=0.0, description="Recall@k for retrieval")
    mrr: float = Field(default=0.0, description="Mean Reciprocal Rank")
    faithfulness: float = Field(
        default=0.0, description="LLM-judged faithfulness to context (0-1)"
    )
    relevance: float = Field(
        default=0.0, description="LLM-judged relevance to question (0-1)"
    )
    hallucination_rate: float = Field(
        default=0.0, description="Rate of hallucinated responses"
    )


class EvaluationReport(BaseModel):
    """Full evaluation report."""

    timestamp: str = Field(
        default_factory=lambda: datetime.now(UTC).isoformat()
    )
    metrics: EvaluationMetrics = Field(default_factory=EvaluationMetrics)
    results: list[EvaluationResult] = Field(default_factory=list)
    gaps_identified: list[str] = Field(
        default_factory=list, description="Topics with poor coverage"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="Improvement recommendations"
    )


class UpdateStats(BaseModel):
    """Statistics from an index update run."""

    status: str
    files_scanned: int
    files_added: int
    files_updated: int
    files_deleted: int
    chunks_indexed: int
    index_size: int
    duration: float
    errors: list[str]


class RAGResponse(BaseModel):
    """Standard RAG response model."""

    response: str = Field(..., description="The generated answer")
    sources: list[str] = Field(default_factory=list, description="Source filenames")
    blocked: bool = Field(default=False, description="Security blocked the request")
    rerank_scores: list[float] | None = Field(
        default=None, description="Reranker scores"
    )


class GreetingResponse(RAGResponse):
    """Response for greeting queries (no RAG needed)."""

    blocked: bool = False
    sources: list[str] = []


class InjectionBlockedResponse(RAGResponse):
    """Response when injection is detected."""

    blocked: bool = True
    sources: list[str] = []


class NoContextResponse(RAGResponse):
    """Response when no relevant context found."""

    blocked: bool = False
    sources: list[str] = []


class ErrorResponse(RAGResponse):
    """Response when an error occurred."""

    blocked: bool = False
    sources: list[str] = []
    error_type: str | None = Field(default=None, description="Exception class name")

