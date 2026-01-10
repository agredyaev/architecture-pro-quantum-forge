"""Cross-encoder reranker service."""
from sentence_transformers import CrossEncoder

from src.core import get_logger, settings

logger = get_logger(__name__)


class Reranker:
    """Cross-encoder reranker for improving retrieval precision."""

    def __init__(self, model_name: str | None = None) -> None:
        """Initialize reranker with cross-encoder model."""
        model_name = model_name or settings.models.rerank_model_path
        logger.info("Loading reranker model: %s", model_name)
        self.model = CrossEncoder(model_name, trust_remote_code=True)

    def rerank(
        self,
        query: str,
        chunks: list[dict],
        top_k: int | None = None,
        threshold: float | None = None,
    ) -> list[dict]:
        """Rerank chunks using cross-encoder scores."""
        if not chunks:
            return []

        if top_k is None:
            top_k = settings.rag.top_k_rerank
        if threshold is None:
            threshold = settings.rag.rerank_threshold

        pairs = [(query, chunk["text"]) for chunk in chunks]

        scores = self.model.predict(pairs)

        scored_chunks = [
            {**chunk, "rerank_score": float(score)}
            for chunk, score in zip(chunks, scores, strict=True)
        ]

        scored_chunks.sort(key=lambda x: x["rerank_score"], reverse=True)

        filtered = [c for c in scored_chunks if c["rerank_score"] >= threshold]

        result = filtered[:top_k] if top_k else filtered

        logger.info(
            "Reranked %d -> %d chunks (threshold=%.2f)",
            len(chunks),
            len(result),
            threshold,
        )

        return result
