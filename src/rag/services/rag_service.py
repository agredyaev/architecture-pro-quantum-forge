"""RAG Service for query processing and response generation."""
from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np

from google import genai
from google.genai import types

from src.core import (
    APIKeyMissingError,
    GenerationError,
    GreetingResponse,
    InjectionBlockedResponse,
    NoContextResponse,
    RAGResponse,
    get_logger,
    settings,
)
from src.rag.prompts import build_system_prompt, build_user_prompt
from src.rag.services.query import expand_query, needs_retrieval
from src.rag.services.reranker import Reranker
from src.rag.services.security import (
    get_canary_instruction,
    reset_canary,
    sanitize_context,
    sanitize_query,
    validate_output,
)

if TYPE_CHECKING:
    from src.rag.infrastructure.chroma_repository import VectorRepository
    from src.rag.services.cache import SemanticCache
    from src.rag.services.colbert import ColBERTRetriever
    from src.rag.services.embeddings import EmbeddingService

logger = get_logger(__name__)


def rrf_score(rank: int) -> float:
    """Calculate Reciprocal Rank Fusion score."""
    return 1.0 / (settings.rag.rrf_k + rank)


class RAGService:
    """RAG service for retrieval-augmented generation."""

    def __init__(
        self,
        repository: VectorRepository,
        embedding_service: EmbeddingService,
        colbert_retriever: ColBERTRetriever | None = None,
        cache: SemanticCache | None = None,
    ) -> None:
        """Initialize RAG service with dependencies."""
        self.repository = repository
        self.embedding_service = embedding_service
        self.colbert_retriever = colbert_retriever
        self.cache = cache

        if settings.rag.use_colbert and colbert_retriever is None:
            try:
                from src.rag.services.colbert import ColBERTRetriever as ColBERT

                self.colbert_retriever = ColBERT(
                    index_path=Path(settings.rag.colbert_index_path)
                )
            except ImportError:
                logger.warning("ColBERT not available, using dense retrieval only")
                self.colbert_retriever = None

        if self.cache is None and settings.rag.use_semantic_cache:
            from src.rag.services.cache import SemanticCache
            self.cache = SemanticCache()
            self.cache.connect()

        self.reranker = Reranker()

        if not settings.models.gemini_api_key:
            raise APIKeyMissingError("GEMINI_API_KEY")

        self.client = genai.Client(api_key=settings.models.gemini_api_key)
        self.model_name = settings.models.gemini_model
        logger.info("RAGService initialized with %s", self.model_name)

    def retrieve_dense(self, query: str, top_k: int = 50) -> list[dict]:
        """Retrieve using dense embeddings (ChromaDB)."""
        query_embedding = self.embedding_service.embed_query(query, settings.rag.vector_size)
        results = self.repository.query(
            query_embedding=query_embedding,
            n_results=top_k,
        )

        chunks = []
        if results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0],
                results["distances"][0],
                strict=True,
            ):
                chunks.append({
                    "text": doc,
                    "source": meta.get("filename", "unknown"),
                    "score": 1 - dist,
                })
        return chunks

    def retrieve_colbert(self, query: str, top_k: int = 50) -> list[dict]:
        """Retrieve using ColBERT late interaction."""
        if not self.colbert_retriever or not self.colbert_retriever.is_indexed():
            return []

        return self.colbert_retriever.search(query, top_k=top_k)

    def retrieve_hybrid(self, query: str, top_k: int = 50) -> list[dict]:
        """Hybrid retrieval: Dense + ColBERT with RRF fusion."""
        dense_results = self.retrieve_dense(query, top_k=top_k)

        if not settings.rag.use_colbert:
            return dense_results

        colbert_results = self.retrieve_colbert(query, top_k=top_k)

        if not colbert_results:
            return dense_results

        all_chunks: dict[str, dict] = {}
        rank_scores: dict[str, float] = {}

        for rank, chunk in enumerate(dense_results):
            chunk_id = chunk["text"][:100]
            all_chunks[chunk_id] = chunk
            rank_scores[chunk_id] = rrf_score(rank)

        for rank, chunk in enumerate(colbert_results):
            chunk_id = chunk["text"][:100]
            if chunk_id not in all_chunks:
                all_chunks[chunk_id] = chunk
                rank_scores[chunk_id] = 0.0
            rank_scores[chunk_id] += rrf_score(rank)

        sorted_ids = sorted(rank_scores.keys(), key=lambda x: rank_scores[x], reverse=True)
        return [all_chunks[cid] for cid in sorted_ids[:top_k]]

    def retrieve_with_expansion(self, query: str, top_k: int = 50) -> list[dict]:
        """Retrieve with query expansion and RRF fusion."""
        queries = expand_query(query)
        logger.info("Query expansion: %d variations", len(queries))

        all_chunks: dict[str, dict] = {}
        rank_scores: dict[str, float] = {}

        for q in queries:
            chunks = self.retrieve_hybrid(q, top_k=top_k)
            for rank, chunk in enumerate(chunks):
                chunk_id = chunk["text"][:100]
                if chunk_id not in all_chunks:
                    all_chunks[chunk_id] = chunk
                    rank_scores[chunk_id] = 0.0
                rank_scores[chunk_id] += rrf_score(rank)

        sorted_ids = sorted(rank_scores.keys(), key=lambda x: rank_scores[x], reverse=True)
        return [all_chunks[cid] for cid in sorted_ids[:top_k]]

    def _check_cache(
        self, sanitized_query: str, query_embedding: list[float]
    ) -> RAGResponse | None:
        """Check semantic cache for existing response."""
        if not self.cache or not self.cache.is_connected:
            return None

        embedding_array = np.array(query_embedding, dtype=np.float32)
        cached_response = self.cache.get(sanitized_query, embedding_array)
        if cached_response:
            logger.info("Cache hit for query: %s", sanitized_query[:50])
            return RAGResponse(
                response=cached_response.get("response", ""),
                sources=cached_response.get("sources", []),
                blocked=cached_response.get("blocked", False),
            )
        return None

    def _sanitize_chunks(self, chunks: list[dict]) -> tuple[list[str], list[dict], bool]:
        """Sanitize retrieved chunks and detect injection attempts.

        Returns:
            tuple: (context_parts, safe_chunks, injection_detected)
        """
        context_parts = []
        safe_chunks = []
        injection_detected = False

        for i, chunk in enumerate(chunks):
            safe_text, is_chunk_safe = sanitize_context(chunk["text"])

            if is_chunk_safe:
                subject_line = ""
                if settings.rag.annotate_context_subjects:
                    subject = self._source_subject(chunk.get("source", ""))
                    if subject:
                        subject_line = settings.rag.context_subject_format.format(
                            subject=subject
                        )
                if subject_line:
                    context_parts.append(
                        f"[{i+1}] Source: {chunk['source']}\n{subject_line}\n{safe_text}"
                    )
                else:
                    context_parts.append(
                        f"[{i+1}] Source: {chunk['source']}\n{safe_text}"
                    )
                safe_chunks.append(chunk)
            else:
                injection_detected = True
                logger.warning(
                    "Filtered chunk from %s due to injection pattern",
                    chunk["source"],
                )

        return context_parts, safe_chunks, injection_detected

    def _source_subject(self, source: str) -> str:
        """Derive a subject label from a source filename."""
        if not source:
            return ""
        subject = Path(source).stem.replace("_", " ").replace("-", " ").strip()
        return re.sub(r"\s+", " ", subject)

    def generate(
        self,
        query: str,
        use_few_shot: bool = True,
        use_cot: bool = True,
        top_k: int = 5,
    ) -> RAGResponse:
        """Generate response using RAG pipeline with security layers."""
        if not needs_retrieval(query):
            return GreetingResponse(response=settings.responses.greeting)

        reset_canary()

        sanitized_query, is_safe = sanitize_query(query)

        if not is_safe:
            logger.warning("Query blocked due to injection attempt")
            return InjectionBlockedResponse(response=settings.responses.injection_blocked)

        query_embedding = self.embedding_service.embed_query(
            sanitized_query, settings.rag.vector_size
        )

        cached = self._check_cache(sanitized_query, query_embedding)
        if cached:
            return cached

        chunks = self.retrieve_with_expansion(
            sanitized_query,
            top_k=settings.rag.top_k_retrieval,
        )

        chunks = self.reranker.rerank(
            query=sanitized_query,
            chunks=chunks,
            top_k=top_k,
        )

        if not chunks:
            return NoContextResponse(response=settings.responses.no_context)

        context_parts, safe_chunks, injection_detected = self._sanitize_chunks(chunks)

        if not context_parts:
            return InjectionBlockedResponse(
                response=settings.responses.context_injection_blocked
            )

        context = "\n\n".join(context_parts)

        system_prompt = build_system_prompt(context)
        system_prompt += get_canary_instruction()

        user_prompt = build_user_prompt(
            query=sanitized_query,
            use_few_shot=use_few_shot,
            use_cot=use_cot,
        )

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=system_prompt + "\n\n" + user_prompt,
                config=types.GenerateContentConfig(
                    temperature=0.3,
                    max_output_tokens=1024,
                ),
            )

            raw_answer = response.text if response.text else settings.responses.no_context

            answer, is_output_safe = validate_output(raw_answer)

            if not is_output_safe:
                logger.warning("Output validation failed - potential injection")
                injection_detected = True

        except Exception as e:
            logger.exception("Error generating response")
            raise GenerationError(str(e)) from e

        sources = list({chunk["source"] for chunk in safe_chunks})
        rerank_scores: list[float] = [
            c["rerank_score"] for c in safe_chunks
            if "rerank_score" in c and c["rerank_score"] is not None
        ]

        result = RAGResponse(
            response=answer,
            sources=sources,
            blocked=injection_detected,
            rerank_scores=rerank_scores if rerank_scores else None,
            context=context,
        )

        if self.cache and self.cache.is_connected and not injection_detected:
            embedding_array = np.array(query_embedding, dtype=np.float32)
            self.cache.set(
                query=sanitized_query,
                query_embedding=embedding_array,
                response={
                    "response": answer,
                    "sources": sources,
                    "blocked": False,
                },
            )

        return result
